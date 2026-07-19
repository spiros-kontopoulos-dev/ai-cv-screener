"""Orchestrate the complete idempotent CV PDF ingestion workflow.

The service composes the independently tested PDF, chunking, embedding, and
Chroma repository layers. The current administrator CLI and a future upload
endpoint can call the same service without duplicating pipeline logic.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.cv_ingestion.chroma_store import (
    CvChromaRepository,
    CvVectorStoreError,
    VectorIndexCoverage,
)
from app.cv_ingestion.chunking import (
    CvChunkingConfig,
    CvChunkingError,
    chunk_cv_document,
)
from app.cv_ingestion.embeddings import (
    CvEmbeddingError,
    EmbeddedCvChunk,
    SentenceTransformerEmbeddingProvider,
)
from app.cv_ingestion.extraction import (
    CvDocumentExtractionError,
    calculate_pdf_sha256,
    load_cv_document,
)
from app.cv_ingestion.models import CvChunk, ExtractedCvDocument


class CvIngestionError(RuntimeError):
    """Raised when the complete ingestion workflow cannot continue safely."""


@dataclass(frozen=True, slots=True)
class CvMetadataOverrides:
    """Optional caller-supplied identity for one arbitrary uploaded-style PDF."""

    candidate_id: str | None = None
    candidate_name: str | None = None
    professional_title: str | None = None


@dataclass(frozen=True, slots=True)
class CvIngestionFailure:
    """One document-level failure retained while later documents continue."""

    source_path: Path
    stage: str
    message: str


@dataclass(frozen=True, slots=True)
class CvIngestionDocumentResult:
    """One selected PDF's terminal ingestion state."""

    source_path: Path
    document_hash: str
    candidate_id: str | None
    status: Literal[
        "indexed",
        "skipped",
        "metadata_refreshed",
        "duplicate_input",
        "failed",
    ]
    page_count: int = 0
    chunk_count: int = 0


@dataclass(frozen=True, slots=True)
class CvIngestionSummary:
    """Complete shell- and API-friendly result for one ingestion request."""

    selected_pdf_count: int
    unique_pdf_count: int
    indexed_document_count: int
    skipped_document_count: int
    metadata_refreshed_count: int
    duplicate_input_count: int
    failed_document_count: int
    pages_extracted: int
    chunks_generated: int
    chunks_embedded: int
    records_upserted: int
    records_deleted: int
    collection_count: int
    rebuilt: bool
    results: tuple[CvIngestionDocumentResult, ...]
    failures: tuple[CvIngestionFailure, ...]
    coverage: VectorIndexCoverage


@dataclass(frozen=True, slots=True)
class _PendingDocument:
    path: Path
    document_hash: str
    document: ExtractedCvDocument
    chunks: tuple[CvChunk, ...]


class CvIngestionService:
    """Run select-path PDFs through extraction, chunking, embedding, and storage."""

    def __init__(
        self,
        *,
        chunking_config: CvChunkingConfig,
        embedding_provider: SentenceTransformerEmbeddingProvider,
        repository: CvChromaRepository,
    ) -> None:
        self._chunking_config = chunking_config
        self._embedding_provider = embedding_provider
        self._repository = repository

    def ingest(
        self,
        paths: Sequence[Path],
        *,
        rebuild: bool = False,
        replace_existing: bool = False,
        metadata_overrides: CvMetadataOverrides | None = None,
    ) -> CvIngestionSummary:
        """Ingest selected PDFs and skip byte-identical complete documents."""

        if not paths:
            raise CvIngestionError("At least one PDF path is required for ingestion.")
        if metadata_overrides is not None and len(paths) != 1:
            raise CvIngestionError(
                "Metadata overrides may be applied only to one selected PDF."
            )

        ordered_paths = tuple(
            sorted(
                paths,
                key=lambda path: (
                    path.name.casefold(),
                    path.as_posix().casefold(),
                ),
            )
        )
        if rebuild:
            self._repository.reset_collection()

        failures: list[CvIngestionFailure] = []
        results: list[CvIngestionDocumentResult] = []
        unique_sources: dict[str, Path] = {}
        duplicate_input_count = 0

        for path in ordered_paths:
            try:
                document_hash = calculate_pdf_sha256(path)
            except (CvDocumentExtractionError, OSError, ValueError) as error:
                failures.append(
                    CvIngestionFailure(path, "fingerprint", str(error))
                )
                results.append(
                    CvIngestionDocumentResult(path, "", None, "failed")
                )
                continue

            if document_hash in unique_sources:
                duplicate_input_count += 1
                results.append(
                    CvIngestionDocumentResult(
                        path,
                        document_hash,
                        None,
                        "duplicate_input",
                    )
                )
                continue
            unique_sources[document_hash] = path

        try:
            existing_by_hash = {
                summary.document_hash: summary
                for summary in self._repository.get_document_summaries(
                    tuple(unique_sources)
                )
            }
        except CvVectorStoreError as error:
            raise CvIngestionError(str(error)) from error

        pending_paths: list[tuple[Path, str]] = []
        metadata_refreshed_count = 0
        skipped_document_count = 0
        for document_hash, path in unique_sources.items():
            existing = existing_by_hash.get(document_hash)
            if existing is None or not existing.complete or replace_existing:
                pending_paths.append((path, document_hash))
                continue

            stored_path = Path(existing.source_path) if existing.source_path else None
            if (
                stored_path is not None
                and stored_path.resolve() != path.resolve()
                and not stored_path.exists()
            ):
                try:
                    self._repository.refresh_document_source_metadata(
                        document_hash=document_hash,
                        source_filename=path.name,
                        source_path=path,
                    )
                except CvVectorStoreError as error:
                    failures.append(
                        CvIngestionFailure(path, "metadata", str(error))
                    )
                    results.append(
                        CvIngestionDocumentResult(
                            path,
                            document_hash,
                            existing.candidate_id,
                            "failed",
                        )
                    )
                    continue
                metadata_refreshed_count += 1
                results.append(
                    CvIngestionDocumentResult(
                        path,
                        document_hash,
                        existing.candidate_id,
                        "metadata_refreshed",
                        chunk_count=existing.stored_chunk_count,
                    )
                )
            else:
                skipped_document_count += 1
                results.append(
                    CvIngestionDocumentResult(
                        path,
                        document_hash,
                        existing.candidate_id,
                        "skipped",
                        chunk_count=existing.stored_chunk_count,
                    )
                )

        pending: list[_PendingDocument] = []
        for path, expected_hash in pending_paths:
            overrides = metadata_overrides or CvMetadataOverrides()
            try:
                document = load_cv_document(
                    path,
                    candidate_id=overrides.candidate_id,
                    candidate_name=overrides.candidate_name,
                    professional_title=overrides.professional_title,
                )
                if document.source.document_hash != expected_hash:
                    raise CvIngestionError(
                        "PDF content changed between fingerprinting and extraction."
                    )
                chunks = chunk_cv_document(
                    document,
                    config=self._chunking_config,
                )
            except (
                CvDocumentExtractionError,
                CvChunkingError,
                CvIngestionError,
            ) as error:
                failures.append(CvIngestionFailure(path, "processing", str(error)))
                results.append(
                    CvIngestionDocumentResult(
                        path,
                        expected_hash,
                        None,
                        "failed",
                    )
                )
                continue
            pending.append(
                _PendingDocument(path, expected_hash, document, chunks)
            )

        embedded_by_hash: dict[str, tuple[EmbeddedCvChunk, ...]] = {}
        if pending:
            all_chunks = tuple(
                chunk for item in pending for chunk in item.chunks
            )
            try:
                all_embedded = self._embedding_provider.embed_chunks(all_chunks)
            except CvEmbeddingError as error:
                for item in pending:
                    failures.append(
                        CvIngestionFailure(item.path, "embedding", str(error))
                    )
                    results.append(
                        CvIngestionDocumentResult(
                            item.path,
                            item.document_hash,
                            item.document.source.candidate_id,
                            "failed",
                            page_count=item.document.page_count,
                            chunk_count=len(item.chunks),
                        )
                    )
                pending = []
            else:
                grouped: dict[str, list[EmbeddedCvChunk]] = defaultdict(list)
                for embedded in all_embedded:
                    grouped[embedded.chunk.source.document_hash].append(embedded)
                embedded_by_hash = {
                    document_hash: tuple(items)
                    for document_hash, items in grouped.items()
                }

        indexed_document_count = 0
        records_upserted = 0
        records_deleted = 0
        pages_extracted = 0
        chunks_generated = 0
        chunks_embedded = 0

        for item in pending:
            embedded = embedded_by_hash.get(item.document_hash, ())
            try:
                existing = self._repository.get_document_summary(
                    item.document_hash
                )
                if existing is not None and not existing.complete:
                    records_deleted += self._repository.delete_document_records(
                        item.document_hash
                    )
                if replace_existing:
                    records_deleted += (
                        self._repository.delete_replaced_document_records(
                            source_path=item.path,
                            candidate_id=item.document.source.candidate_id,
                            current_document_hash=item.document_hash,
                        )
                    )
                upsert = self._repository.upsert_embeddings(embedded)
                stored = self._repository.get_document_summary(item.document_hash)
                if stored is None or not stored.complete:
                    raise CvIngestionError(
                        "Stored document failed post-ingestion completeness validation."
                    )
            except (CvVectorStoreError, CvIngestionError) as error:
                failures.append(CvIngestionFailure(item.path, "storage", str(error)))
                results.append(
                    CvIngestionDocumentResult(
                        item.path,
                        item.document_hash,
                        item.document.source.candidate_id,
                        "failed",
                        page_count=item.document.page_count,
                        chunk_count=len(item.chunks),
                    )
                )
                continue

            indexed_document_count += 1
            pages_extracted += item.document.page_count
            chunks_generated += len(item.chunks)
            chunks_embedded += len(embedded)
            records_upserted += upsert.records_submitted
            results.append(
                CvIngestionDocumentResult(
                    item.path,
                    item.document_hash,
                    item.document.source.candidate_id,
                    "indexed",
                    page_count=item.document.page_count,
                    chunk_count=len(item.chunks),
                )
            )

        try:
            coverage = self._repository.get_index_coverage()
        except CvVectorStoreError as error:
            raise CvIngestionError(str(error)) from error

        ordered_results = tuple(
            sorted(
                results,
                key=lambda result: (
                    result.source_path.name.casefold(),
                    result.source_path.as_posix().casefold(),
                    result.status,
                ),
            )
        )
        return CvIngestionSummary(
            selected_pdf_count=len(ordered_paths),
            unique_pdf_count=len(unique_sources),
            indexed_document_count=indexed_document_count,
            skipped_document_count=skipped_document_count,
            metadata_refreshed_count=metadata_refreshed_count,
            duplicate_input_count=duplicate_input_count,
            failed_document_count=len(failures),
            pages_extracted=pages_extracted,
            chunks_generated=chunks_generated,
            chunks_embedded=chunks_embedded,
            records_upserted=records_upserted,
            records_deleted=records_deleted,
            collection_count=coverage.record_count,
            rebuilt=rebuild,
            results=ordered_results,
            failures=tuple(failures),
            coverage=coverage,
        )
