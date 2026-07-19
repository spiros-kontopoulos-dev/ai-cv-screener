"""Run raw semantic nearest-neighbour checks against the persisted CV index.

This command deliberately prints ungrouped Chroma chunks. Candidate-aware
ranking, thresholds, and balanced evidence selection belong to Work Package 6.
"""

import argparse
from collections.abc import Sequence
import sys

from app.core.config import Settings, get_settings
from app.cv_ingestion import (
    CvChromaRepository,
    CvEmbeddingError,
    CvVectorStoreConfig,
    CvVectorStoreError,
    SentenceTransformerEmbeddingProvider,
    get_embedding_provider,
)


def build_parser() -> argparse.ArgumentParser:
    """Create the raw semantic smoke-test command."""

    parser = argparse.ArgumentParser(
        description="Query raw nearest CV chunks without final retrieval logic."
    )
    parser.add_argument(
        "--query",
        action="append",
        required=True,
        help="Semantic smoke query. Repeat to test several questions.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Raw Chroma chunks to print for each query (default: 5).",
    )
    parser.add_argument(
        "--preview-characters",
        type=int,
        default=180,
        help="Maximum text preview per match (default: 180).",
    )
    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    provider: SentenceTransformerEmbeddingProvider | None = None,
    repository: CvChromaRepository | None = None,
) -> int:
    """Embed each question and print raw nearest-neighbour evidence."""

    parser = build_parser()
    arguments = parser.parse_args(argv)
    if arguments.top_k < 1:
        print("ERROR: --top-k must be positive.", file=sys.stderr)
        return 2
    if arguments.preview_characters < 0:
        print("ERROR: --preview-characters cannot be negative.", file=sys.stderr)
        return 2

    active_settings = settings or get_settings()
    active_provider = provider or get_embedding_provider(
        active_settings.cv_embedding_model_name,
        active_settings.cv_embedding_expected_dimension,
        active_settings.cv_embedding_batch_size,
        active_settings.cv_embedding_normalize,
        active_settings.cv_embedding_device,
        active_settings.cv_embedding_cache_directory,
    )
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
        vectors = active_provider.embed_texts(tuple(arguments.query))
        info = active_repository.get_collection_info()
        if info.record_count == 0:
            print("ERROR: The CV vector collection is empty.", file=sys.stderr)
            return 2
    except (CvEmbeddingError, CvVectorStoreError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    print("RAW CV INDEX SMOKE TEST")
    print(f"  Collection: {info.collection_name}")
    print(f"  Records: {info.record_count}")
    print(f"  Queries: {len(arguments.query)}")
    print(f"  Top K: {arguments.top_k}")

    for query, vector in zip(arguments.query, vectors, strict=True):
        try:
            matches = active_repository.query_nearest(
                vector,
                n_results=arguments.top_k,
            )
        except CvVectorStoreError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2

        print(f"\nQUERY: {query}")
        for rank, match in enumerate(matches, start=1):
            metadata = match.metadata
            preview = " ".join(match.text.split())
            if arguments.preview_characters:
                preview = preview[: arguments.preview_characters]
            else:
                preview = ""
            print(
                f"  {rank}. distance={match.distance:.6f} | "
                f"candidate={metadata.get('candidate_id', '')} | "
                f"name={metadata.get('candidate_name', '')} | "
                f"section={metadata.get('section_name', '')} | "
                f"pages={metadata.get('page_numbers', '')} | "
                f"file={metadata.get('source_filename', '')}"
            )
            if preview:
                print(f"     {preview}")
    return 0


def main() -> None:
    """Run the CLI and expose shell-friendly exit status."""

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
