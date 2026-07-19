"""Run the complete idempotent PDF-to-Chroma CV ingestion workflow.

Examples:

    python -m app.scripts.ingest_cv_documents --all
    python -m app.scripts.ingest_cv_documents --file data/uploads/example.pdf
    python -m app.scripts.ingest_cv_documents --directory data/cv_pdfs
"""

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from app.core.config import Settings, get_settings
from app.cv_ingestion import (
    CvChromaRepository,
    CvChunkingConfig,
    CvDocumentSelectionError,
    CvIngestionError,
    CvIngestionService,
    CvMetadataOverrides,
    CvVectorStoreConfig,
    get_embedding_provider,
    select_cv_pdf_paths,
)


def build_parser() -> argparse.ArgumentParser:
    """Create the administrator ingestion command."""

    parser = argparse.ArgumentParser(
        description=(
            "Extract, chunk, embed, and persist selected CV PDFs in the "
            "configured ChromaDB collection."
        )
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--file",
        action="append",
        type=Path,
        dest="files",
        help="Select one PDF. Repeat --file to ingest several PDFs.",
    )
    input_group.add_argument(
        "--directory",
        type=Path,
        help="Ingest every PDF directly inside this directory.",
    )
    input_group.add_argument(
        "--all",
        action="store_true",
        dest="select_all",
        help="Ingest every PDF in the configured default CV directory.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Include nested PDFs for --directory or --all.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete the complete configured collection before ingestion.",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help=(
            "Remove older indexed revisions sharing the source path or "
            "candidate ID before storing the selected document."
        ),
    )
    parser.add_argument(
        "--candidate-id",
        help="Override candidate identity for one selected PDF.",
    )
    parser.add_argument(
        "--candidate-name",
        help="Override candidate display name for one selected PDF.",
    )
    parser.add_argument(
        "--professional-title",
        help="Override professional title for one selected PDF.",
    )
    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    service: CvIngestionService | None = None,
) -> int:
    """Run one complete ingestion request and print a reviewable summary."""

    parser = build_parser()
    arguments = parser.parse_args(argv)
    active_settings = settings or get_settings()

    overrides_requested = any(
        (
            arguments.candidate_id,
            arguments.candidate_name,
            arguments.professional_title,
        )
    )

    try:
        paths = select_cv_pdf_paths(
            files=tuple(arguments.files or ()),
            directory=arguments.directory,
            default_directory=active_settings.cv_ingestion_default_directory,
            select_all=arguments.select_all,
            recursive=arguments.recursive,
        )
        if overrides_requested and len(paths) != 1:
            raise CvIngestionError(
                "Candidate metadata overrides require exactly one PDF."
            )

        active_service = service or _build_service(active_settings)
        summary = active_service.ingest(
            paths,
            rebuild=arguments.rebuild,
            replace_existing=arguments.replace_existing,
            metadata_overrides=(
                CvMetadataOverrides(
                    candidate_id=arguments.candidate_id,
                    candidate_name=arguments.candidate_name,
                    professional_title=arguments.professional_title,
                )
                if overrides_requested
                else None
            ),
        )
    except (CvDocumentSelectionError, CvIngestionError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    print("CV INGESTION COMPLETE")
    print(f"  Selected PDFs: {summary.selected_pdf_count}")
    print(f"  Unique PDF contents: {summary.unique_pdf_count}")
    print(f"  Indexed documents: {summary.indexed_document_count}")
    print(f"  Already indexed: {summary.skipped_document_count}")
    print(f"  Metadata refreshed: {summary.metadata_refreshed_count}")
    print(f"  Duplicate selected contents: {summary.duplicate_input_count}")
    print(f"  Failed documents: {summary.failed_document_count}")
    print(f"  Pages extracted: {summary.pages_extracted}")
    print(f"  Chunks generated: {summary.chunks_generated}")
    print(f"  Chunks embedded: {summary.chunks_embedded}")
    print(f"  Records upserted: {summary.records_upserted}")
    print(f"  Records deleted: {summary.records_deleted}")
    print(f"  Collection records: {summary.collection_count}")
    print(f"  Rebuilt collection: {summary.rebuilt}")

    print("\nINDEX COVERAGE")
    print(f"  Documents: {summary.coverage.document_count}")
    print(f"  Complete documents: {summary.coverage.complete_document_count}")
    print(f"  Incomplete documents: {summary.coverage.incomplete_document_count}")
    print(f"  Candidates: {summary.coverage.candidate_count}")
    print(f"  Source files: {summary.coverage.source_count}")

    print("\nDOCUMENT RESULTS")
    for result in summary.results:
        candidate = result.candidate_id or "unknown"
        print(
            f"  {result.source_path.name} | status={result.status} | "
            f"candidate={candidate} | pages={result.page_count} | "
            f"chunks={result.chunk_count} | hash={result.document_hash[:12]}"
        )

    if summary.failures:
        print("\nFAILURES", file=sys.stderr)
        for failure in summary.failures:
            print(
                f"  {failure.source_path} | stage={failure.stage} | "
                f"{failure.message}",
                file=sys.stderr,
            )
        return 1
    if summary.coverage.incomplete_document_count:
        print(
            "ERROR: The vector index contains incomplete documents.",
            file=sys.stderr,
        )
        return 1
    return 0


def _build_service(settings: Settings) -> CvIngestionService:
    """Build the production service from central immutable settings."""

    provider = get_embedding_provider(
        settings.cv_embedding_model_name,
        settings.cv_embedding_expected_dimension,
        settings.cv_embedding_batch_size,
        settings.cv_embedding_normalize,
        settings.cv_embedding_device,
        settings.cv_embedding_cache_directory,
    )
    repository = CvChromaRepository(
        CvVectorStoreConfig(
            persist_directory=settings.cv_vector_store_directory,
            collection_name=settings.cv_vector_collection_name,
            index_version=settings.cv_vector_index_version,
            embedding_model=settings.cv_embedding_model_name,
            embedding_dimension=settings.cv_embedding_expected_dimension,
            chunking_version=settings.cv_chunking_version,
            distance_metric=settings.cv_vector_distance_metric,
            upsert_batch_size=settings.cv_vector_upsert_batch_size,
        )
    )
    return CvIngestionService(
        chunking_config=CvChunkingConfig(
            version=settings.cv_chunking_version,
            max_characters=settings.cv_chunk_max_characters,
            min_characters=settings.cv_chunk_min_characters,
            overlap_characters=settings.cv_chunk_overlap_characters,
        ),
        embedding_provider=provider,
        repository=repository,
    )


def main() -> None:
    """Run the CLI and expose shell-friendly exit status."""

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
