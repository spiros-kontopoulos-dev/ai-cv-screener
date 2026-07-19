"""Persistent ChromaDB storage for explicitly generated CV embeddings.

The repository receives vectors from ``embeddings.py`` and always supplies
them explicitly to Chroma. Collection metadata records compatibility-critical
settings so incompatible models or chunking strategies are never mixed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.cv_ingestion.embeddings import EmbeddedCvChunk


class CvVectorStoreError(RuntimeError):
    """Raised when persistent vector records cannot be created or validated."""


class ChromaCollection(Protocol):
    """Subset of the Chroma collection API used by the repository."""

    metadata: dict[str, Any] | None
    configuration: dict[str, Any]

    def upsert(
        self,
        *,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str],
    ) -> None:
        """Create or update vector records by stable chunk ID."""

    def update(
        self,
        *,
        ids: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Update metadata for existing records without regenerating vectors."""

    def get(self, **kwargs: Any) -> dict[str, Any]:
        """Read records and metadata from the collection."""

    def query(self, **kwargs: Any) -> dict[str, Any]:
        """Return nearest records for an explicit query vector."""

    def delete(self, **kwargs: Any) -> None:
        """Delete records by IDs or metadata filter."""

    def count(self) -> int:
        """Return the number of records in the collection."""


class ChromaClient(Protocol):
    """Subset of the persistent Chroma client used by the repository."""

    def get_or_create_collection(self, **kwargs: Any) -> ChromaCollection:
        """Return a compatible collection or create it."""

    def delete_collection(self, name: str) -> None:
        """Delete a collection by name."""


ClientFactory = Callable[[Path], ChromaClient]


@dataclass(frozen=True, slots=True)
class CvVectorStoreConfig:
    """Compatibility and persistence settings for one Chroma collection."""

    persist_directory: Path = Path("storage/chroma")
    collection_name: str = "cv_chunks"
    index_version: str = "cv-index-v1"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    chunking_version: str = "cv-sections-v1"
    distance_metric: str = "cosine"
    upsert_batch_size: int = 100

    def __post_init__(self) -> None:
        """Reject invalid collection settings before touching persistent data."""

        if not self.collection_name.strip():
            raise CvVectorStoreError("Chroma collection name cannot be empty.")
        if not self.index_version.strip():
            raise CvVectorStoreError("Vector index version cannot be empty.")
        if not self.embedding_model.strip():
            raise CvVectorStoreError("Embedding model cannot be empty.")
        if self.embedding_dimension < 1:
            raise CvVectorStoreError("Embedding dimension must be positive.")
        if not self.chunking_version.strip():
            raise CvVectorStoreError("Chunking version cannot be empty.")
        if self.distance_metric not in {"cosine", "l2", "ip"}:
            raise CvVectorStoreError(
                "Distance metric must be one of: cosine, l2, ip."
            )
        if self.upsert_batch_size < 1:
            raise CvVectorStoreError("Chroma upsert batch size must be positive.")

    @property
    def collection_metadata(self) -> dict[str, Any]:
        """Return persisted compatibility metadata for collection validation."""

        return {
            "index_version": self.index_version,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "chunking_version": self.chunking_version,
            "distance_metric": self.distance_metric,
        }


@dataclass(frozen=True, slots=True)
class VectorUpsertSummary:
    """Storage-level result for one explicit upsert operation."""

    collection_name: str
    records_submitted: int
    collection_count: int
    batches_written: int


@dataclass(frozen=True, slots=True)
class VectorCollectionInfo:
    """Read-only summary of one persistent Chroma collection."""

    collection_name: str
    record_count: int
    metadata: dict[str, Any]
    distance_metric: str


@dataclass(frozen=True, slots=True)
class IndexedDocumentSummary:
    """Document-level completeness inferred from persisted chunk metadata."""

    document_hash: str
    document_id: str
    candidate_id: str
    candidate_name: str
    source_filename: str
    source_path: str
    stored_chunk_count: int
    expected_chunk_count: int | None
    complete: bool


@dataclass(frozen=True, slots=True)
class VectorIndexCoverage:
    """Collection coverage used by ingestion validation and diagnostics."""

    record_count: int
    document_count: int
    candidate_count: int
    source_count: int
    complete_document_count: int
    incomplete_document_count: int
    documents: tuple[IndexedDocumentSummary, ...]


@dataclass(frozen=True, slots=True)
class RawVectorMatch:
    """One ungrouped nearest-neighbour result for semantic smoke testing."""

    chunk_id: str
    distance: float
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RawStoredChunk:
    """One persisted chunk loaded without embeddings for exact text assistance."""

    chunk_id: str
    text: str
    metadata: dict[str, Any]


class CvChromaRepository:
    """Persist validated CV vectors with stable IDs and complete metadata."""

    def __init__(
        self,
        config: CvVectorStoreConfig,
        *,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._config = config
        self._client_factory = client_factory or _create_persistent_client
        self._client: ChromaClient | None = None
        self._collection: ChromaCollection | None = None

    @property
    def config(self) -> CvVectorStoreConfig:
        """Return immutable vector-store settings."""

        return self._config

    @property
    def client(self) -> ChromaClient:
        """Create one persistent client lazily and reuse it."""

        if self._client is None:
            try:
                self._config.persist_directory.mkdir(parents=True, exist_ok=True)
                self._client = self._client_factory(
                    self._config.persist_directory
                )
            except CvVectorStoreError:
                raise
            except Exception as error:  # pragma: no cover - provider-specific
                raise CvVectorStoreError(
                    f"Unable to initialize persistent ChromaDB: {error}"
                ) from error
        return self._client

    @property
    def collection(self) -> ChromaCollection:
        """Create or load one collection and verify compatibility metadata."""

        if self._collection is None:
            try:
                self._collection = self.client.get_or_create_collection(
                    name=self._config.collection_name,
                    metadata=self._config.collection_metadata,
                    configuration={
                        "hnsw": {"space": self._config.distance_metric},
                    },
                )
            except Exception as error:  # pragma: no cover - provider-specific
                raise CvVectorStoreError(
                    f"Unable to open Chroma collection "
                    f"'{self._config.collection_name}': {error}"
                ) from error
            self._validate_collection_compatibility(self._collection)
        return self._collection

    def upsert_embeddings(
        self,
        embedded_chunks: Sequence[EmbeddedCvChunk],
    ) -> VectorUpsertSummary:
        """Upsert explicit vectors in bounded batches by stable chunk ID."""

        if not embedded_chunks:
            raise CvVectorStoreError(
                "At least one embedded CV chunk is required for persistence."
            )

        chunk_ids = [item.chunk.chunk_id for item in embedded_chunks]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise CvVectorStoreError(
                "Cannot persist duplicate chunk IDs in one operation."
            )

        for item in embedded_chunks:
            self._validate_embedded_chunk(item)

        chunk_counts_by_document = Counter(
            item.chunk.source.document_hash for item in embedded_chunks
        )
        batches_written = 0
        for start in range(0, len(embedded_chunks), self._config.upsert_batch_size):
            batch = embedded_chunks[
                start : start + self._config.upsert_batch_size
            ]
            try:
                self.collection.upsert(
                    ids=[item.chunk.chunk_id for item in batch],
                    embeddings=[list(item.embedding) for item in batch],
                    metadatas=[
                        _serialize_chunk_metadata(
                            item,
                            document_chunk_count=chunk_counts_by_document[
                                item.chunk.source.document_hash
                            ],
                        )
                        for item in batch
                    ],
                    documents=[item.chunk.text for item in batch],
                )
            except Exception as error:  # pragma: no cover - provider-specific
                raise CvVectorStoreError(
                    f"Chroma upsert failed after {batches_written} batches: "
                    f"{error}"
                ) from error
            batches_written += 1

        return VectorUpsertSummary(
            collection_name=self._config.collection_name,
            records_submitted=len(embedded_chunks),
            collection_count=self.collection.count(),
            batches_written=batches_written,
        )

    def get_collection_info(self) -> VectorCollectionInfo:
        """Return a read-only collection summary without exposing Chroma types."""

        collection = self.collection
        configuration = getattr(collection, "configuration", {}) or {}
        hnsw = configuration.get("hnsw") or {}
        return VectorCollectionInfo(
            collection_name=self._config.collection_name,
            record_count=collection.count(),
            metadata=dict(collection.metadata or {}),
            distance_metric=str(
                hnsw.get("space", self._config.distance_metric)
            ),
        )

    def get_document_summaries(
        self,
        document_hashes: Sequence[str] | None = None,
    ) -> tuple[IndexedDocumentSummary, ...]:
        """Group persisted records by PDF content hash and validate completeness."""

        selected_hashes = set(document_hashes or ())
        result = self.collection.get(include=["metadatas"])
        record_ids = list(result.get("ids") or ())
        metadatas = list(result.get("metadatas") or ())

        grouped: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for record_id, metadata in zip(record_ids, metadatas, strict=True):
            metadata = dict(metadata or {})
            document_hash = str(metadata.get("document_hash", ""))
            if not document_hash:
                continue
            if selected_hashes and document_hash not in selected_hashes:
                continue
            grouped.setdefault(document_hash, []).append((record_id, metadata))

        summaries = [
            _build_document_summary(document_hash, records)
            for document_hash, records in grouped.items()
        ]
        return tuple(
            sorted(
                summaries,
                key=lambda item: (
                    item.source_filename.casefold(),
                    item.document_hash,
                ),
            )
        )

    def get_document_summary(
        self,
        document_hash: str,
    ) -> IndexedDocumentSummary | None:
        """Return one indexed-document summary when the hash exists."""

        summaries = self.get_document_summaries((document_hash,))
        return summaries[0] if summaries else None

    def delete_document_records(self, document_hash: str) -> int:
        """Delete all chunks for one exact PDF revision and return their count."""

        summary = self.get_document_summary(document_hash)
        if summary is None:
            return 0
        try:
            self.collection.delete(where={"document_hash": document_hash})
        except Exception as error:  # pragma: no cover - provider-specific
            raise CvVectorStoreError(
                f"Unable to delete vector records for document {document_hash}: "
                f"{error}"
            ) from error
        return summary.stored_chunk_count

    def delete_replaced_document_records(
        self,
        *,
        source_path: Path,
        candidate_id: str,
        current_document_hash: str,
    ) -> int:
        """Delete older revisions sharing source path or candidate identity."""

        result = self.collection.get(include=["metadatas"])
        record_ids = list(result.get("ids") or ())
        metadatas = list(result.get("metadatas") or ())
        resolved_source_path = source_path.resolve().as_posix()
        delete_ids = [
            record_id
            for record_id, metadata in zip(record_ids, metadatas, strict=True)
            if str((metadata or {}).get("document_hash", ""))
            != current_document_hash
            and (
                str((metadata or {}).get("source_path", ""))
                == resolved_source_path
                or str((metadata or {}).get("candidate_id", ""))
                == candidate_id
            )
        ]
        if not delete_ids:
            return 0
        try:
            self.collection.delete(ids=delete_ids)
        except Exception as error:  # pragma: no cover - provider-specific
            raise CvVectorStoreError(
                f"Unable to delete replaced CV revisions: {error}"
            ) from error
        return len(delete_ids)

    def refresh_document_source_metadata(
        self,
        *,
        document_hash: str,
        source_filename: str,
        source_path: Path,
    ) -> int:
        """Refresh path metadata for a byte-identical PDF after rename or move."""

        result = self.collection.get(
            where={"document_hash": document_hash},
            include=["metadatas"],
        )
        record_ids = list(result.get("ids") or ())
        metadatas = [dict(item or {}) for item in result.get("metadatas") or ()]
        if not record_ids:
            return 0
        resolved_path = source_path.resolve().as_posix()
        updated_metadatas = []
        for metadata in metadatas:
            metadata["source_filename"] = source_filename
            metadata["source_path"] = resolved_path
            updated_metadatas.append(metadata)
        try:
            self.collection.update(ids=record_ids, metadatas=updated_metadatas)
        except Exception as error:  # pragma: no cover - provider-specific
            raise CvVectorStoreError(
                f"Unable to refresh CV source metadata: {error}"
            ) from error
        return len(record_ids)

    def get_index_coverage(self) -> VectorIndexCoverage:
        """Return document, candidate, source, and completeness coverage."""

        documents = self.get_document_summaries()
        complete_count = sum(document.complete for document in documents)
        return VectorIndexCoverage(
            record_count=self.collection.count(),
            document_count=len(documents),
            candidate_count=len(
                {document.candidate_id for document in documents}
            ),
            source_count=len(
                {document.source_filename for document in documents}
            ),
            complete_document_count=complete_count,
            incomplete_document_count=len(documents) - complete_count,
            documents=documents,
        )

    def get_all_chunks(self) -> tuple[RawStoredChunk, ...]:
        """Return every stored chunk without loading embeddings into memory."""

        try:
            result = self.collection.get(include=["documents", "metadatas"])
        except Exception as error:  # pragma: no cover - provider-specific
            raise CvVectorStoreError(
                f"Unable to scan persisted CV chunks: {error}"
            ) from error

        ids = list(result.get("ids") or ())
        documents = list(result.get("documents") or ())
        metadatas = list(result.get("metadatas") or ())
        return tuple(
            RawStoredChunk(
                chunk_id=str(chunk_id),
                text=str(document or ""),
                metadata=dict(metadata or {}),
            )
            for chunk_id, document, metadata in zip(
                ids,
                documents,
                metadatas,
                strict=True,
            )
        )

    def query_nearest(
        self,
        query_embedding: Sequence[float],
        *,
        n_results: int = 5,
    ) -> tuple[RawVectorMatch, ...]:
        """Return raw nearest chunks for smoke testing, without candidate ranking."""

        if n_results < 1:
            raise CvVectorStoreError("Query result count must be positive.")
        if len(query_embedding) != self._config.embedding_dimension:
            raise CvVectorStoreError(
                "Query embedding dimension does not match the collection."
            )
        if self.collection.count() == 0:
            return ()
        try:
            result = self.collection.query(
                query_embeddings=[list(query_embedding)],
                n_results=min(n_results, self.collection.count()),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as error:  # pragma: no cover - provider-specific
            raise CvVectorStoreError(
                f"Chroma semantic query failed: {error}"
            ) from error

        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        return tuple(
            RawVectorMatch(
                chunk_id=str(chunk_id),
                distance=float(distance),
                text=str(document or ""),
                metadata=dict(metadata or {}),
            )
            for chunk_id, distance, document, metadata in zip(
                ids,
                distances,
                documents,
                metadatas,
                strict=True,
            )
        )

    def reset_collection(self) -> None:
        """Delete the configured collection and recreate it lazily on next use."""

        try:
            self.client.delete_collection(self._config.collection_name)
        except Exception as error:
            if "does not exist" not in str(error).casefold():
                raise CvVectorStoreError(
                    f"Unable to reset Chroma collection: {error}"
                ) from error
        self._collection = None

    def _validate_collection_compatibility(
        self,
        collection: ChromaCollection,
    ) -> None:
        """Reject silent mixing of incompatible vectors or chunk contracts."""

        actual_metadata = dict(collection.metadata or {})
        expected_metadata = self._config.collection_metadata
        mismatches = {
            key: (expected_value, actual_metadata.get(key))
            for key, expected_value in expected_metadata.items()
            if actual_metadata.get(key) != expected_value
        }
        if mismatches:
            details = ", ".join(
                f"{key}: expected {expected!r}, got {actual!r}"
                for key, (expected, actual) in sorted(mismatches.items())
            )
            raise CvVectorStoreError(
                "Existing Chroma collection is incompatible; rebuild it "
                f"explicitly. {details}."
            )

        configuration = getattr(collection, "configuration", {}) or {}
        hnsw = configuration.get("hnsw") or {}
        actual_metric = hnsw.get("space")
        if actual_metric and actual_metric != self._config.distance_metric:
            raise CvVectorStoreError(
                "Existing Chroma distance metric is incompatible: expected "
                f"{self._config.distance_metric}, got {actual_metric}."
            )

    def _validate_embedded_chunk(self, item: EmbeddedCvChunk) -> None:
        """Ensure every vector matches the configured collection contract."""

        if item.embedding_model != self._config.embedding_model:
            raise CvVectorStoreError(
                f"Embedding model mismatch for {item.chunk.chunk_id}."
            )
        if item.embedding_dimension != self._config.embedding_dimension:
            raise CvVectorStoreError(
                f"Embedding dimension mismatch for {item.chunk.chunk_id}."
            )
        if len(item.embedding) != self._config.embedding_dimension:
            raise CvVectorStoreError(
                f"Vector length mismatch for {item.chunk.chunk_id}."
            )
        if item.chunk.chunking_version != self._config.chunking_version:
            raise CvVectorStoreError(
                f"Chunking version mismatch for {item.chunk.chunk_id}."
            )


def _build_document_summary(
    document_hash: str,
    records: Sequence[tuple[str, dict[str, Any]]],
) -> IndexedDocumentSummary:
    """Build one deterministic completeness summary from chunk metadata."""

    first_metadata = records[0][1]
    expected_values = {
        int(metadata["document_chunk_count"])
        for _, metadata in records
        if metadata.get("document_chunk_count") is not None
    }
    expected_chunk_count = (
        next(iter(expected_values)) if len(expected_values) == 1 else None
    )
    stored_chunk_count = len(records)
    return IndexedDocumentSummary(
        document_hash=document_hash,
        document_id=str(first_metadata.get("document_id", "")),
        candidate_id=str(first_metadata.get("candidate_id", "")),
        candidate_name=str(first_metadata.get("candidate_name", "")),
        source_filename=str(first_metadata.get("source_filename", "")),
        source_path=str(first_metadata.get("source_path", "")),
        stored_chunk_count=stored_chunk_count,
        expected_chunk_count=expected_chunk_count,
        complete=(
            expected_chunk_count is not None
            and expected_chunk_count > 0
            and stored_chunk_count == expected_chunk_count
        ),
    )


def _serialize_chunk_metadata(
    item: EmbeddedCvChunk,
    *,
    document_chunk_count: int,
) -> dict[str, Any]:
    """Convert source and chunk identity into Chroma-compatible scalar values."""

    chunk = item.chunk
    source = chunk.source
    return {
        "document_id": source.document_id,
        "document_hash": source.document_hash,
        "document_chunk_count": document_chunk_count,
        "candidate_id": source.candidate_id,
        "candidate_name": source.candidate_name or "",
        "professional_title": source.professional_title or "",
        "source_filename": source.source_filename,
        "source_path": source.source_path.as_posix(),
        "section_name": chunk.section_name,
        "page_number_start": chunk.page_number_start,
        "page_number_end": chunk.page_number_end,
        "page_numbers": ",".join(str(page) for page in chunk.page_numbers),
        "chunk_index": chunk.chunk_index,
        "chunking_version": chunk.chunking_version,
        "embedding_model": item.embedding_model,
        "embedding_dimension": item.embedding_dimension,
        "embedding_normalized": item.normalized,
    }


def _create_persistent_client(path: Path) -> ChromaClient:
    """Import Chroma lazily and create one disk-backed local client."""

    try:
        import chromadb
    except ImportError as error:  # pragma: no cover - dependency boundary
        raise CvVectorStoreError(
            "chromadb is not installed. Rebuild the backend image."
        ) from error

    return chromadb.PersistentClient(path=str(path))
