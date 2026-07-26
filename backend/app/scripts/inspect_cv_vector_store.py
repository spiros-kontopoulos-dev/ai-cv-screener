"""Show whether the persistent CV vector index is compatible and complete.

The command prints collection settings, document and candidate counts, and any
partial documents. It reads the index but never changes its records.
"""

import argparse
from collections.abc import Sequence
import sys

from app.scripts.cli_help import build_cli_parser

from app.core.config import Settings, get_settings
from app.cv_ingestion import (
    CvChromaRepository,
    CvVectorStoreConfig,
    CvVectorStoreError,
)


def build_parser() -> argparse.ArgumentParser:
    """Describe the single read-only collection inspection mode."""

    return build_cli_parser(
        description=(
            "Inspect the configured CV vector collection, compatibility "
            "metadata, and document coverage."
        ),
        sections=(
            (
                "Valid command combinations",
                (
                    "This command takes no selection or mutation arguments.",
                    "Use --help to display this reference.",
                ),
            ),
            (
                "What the command changes",
                ("It reads Chroma collection metadata and writes nothing.",),
            ),
            (
                "Example",
                ("python -m app.scripts.inspect_cv_vector_store",),
            ),
        ),
    )


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    repository: CvChromaRepository | None = None,
) -> int:
    """Open the configured collection and print settings and coverage counts."""

    if argv and "--help" not in argv and "-h" not in argv:
        print("ERROR: This command does not accept arguments.", file=sys.stderr)
        return 2
    build_parser().parse_args(tuple(argv or ()))
    active_settings = settings or get_settings()
    active_repository = repository or CvChromaRepository(
        CvVectorStoreConfig(
            persist_directory=active_settings.cv_vector_store_directory,
            collection_name=active_settings.cv_vector_collection_name,
            index_version=active_settings.cv_vector_index_version,
            embedding_model=active_settings.cv_embedding_model_name,
            embedding_dimension=active_settings.cv_embedding_expected_dimension,
            chunking_version=active_settings.cv_chunking_version,
            distance_metric=active_settings.cv_vector_distance_metric,
            upsert_batch_size=active_settings.cv_vector_upsert_batch_size,
        )
    )
    try:
        info = active_repository.get_collection_info()
        coverage = active_repository.get_index_coverage()
    except CvVectorStoreError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    print("CV VECTOR COLLECTION")
    print(f"  Name: {info.collection_name}")
    print(f"  Records: {info.record_count}")
    print(f"  Distance metric: {info.distance_metric}")
    print("  Metadata:")
    for key, value in sorted(info.metadata.items()):
        print(f"    {key}: {value}")
    print("  Coverage:")
    print(f"    documents: {coverage.document_count}")
    print(f"    complete_documents: {coverage.complete_document_count}")
    print(f"    incomplete_documents: {coverage.incomplete_document_count}")
    print(f"    candidates: {coverage.candidate_count}")
    print(f"    source_files: {coverage.source_count}")
    return 0


def main() -> None:
    """Run the CLI and expose shell-friendly exit status."""

    raise SystemExit(run_cli(sys.argv[1:]))


if __name__ == "__main__":
    main()
