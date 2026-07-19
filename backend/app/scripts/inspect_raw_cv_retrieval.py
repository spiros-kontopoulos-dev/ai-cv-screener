"""Inspect broad, typed, source-traceable retrieval before candidate ranking."""

import argparse
from collections.abc import Sequence
import sys

from app.core.config import Settings, get_settings
from app.cv_retrieval import (
    CvRawRetrievalContractError,
    CvRawRetrievalError,
    RawCvRetrievalQuery,
    RawCvRetriever,
    build_raw_cv_retriever,
)


def build_parser() -> argparse.ArgumentParser:
    """Create the WP6 raw-retrieval inspection command."""

    parser = argparse.ArgumentParser(
        description=(
            "Inspect broad semantic CV evidence with complete source metadata."
        )
    )
    parser.add_argument(
        "--query",
        action="append",
        required=True,
        help="Recruiter question. Repeat to inspect several questions.",
    )
    parser.add_argument(
        "--result-limit",
        "--top-k",
        dest="result_limit",
        type=int,
        help=(
            "Raw chunks requested per question. Defaults to the configured "
            "broad-retrieval limit."
        ),
    )
    parser.add_argument(
        "--preview-characters",
        type=int,
        default=240,
        help="Maximum normalized evidence preview per hit (default: 240).",
    )
    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    retriever: RawCvRetriever | None = None,
) -> int:
    """Retrieve each question and print inspectable typed evidence records."""

    arguments = build_parser().parse_args(argv)
    if arguments.preview_characters < 0:
        print(
            "ERROR: --preview-characters cannot be negative.",
            file=sys.stderr,
        )
        return 2

    active_retriever = retriever or build_raw_cv_retriever(
        settings or get_settings()
    )
    print("RAW CV RETRIEVAL INSPECTION")

    for question_index, question_text in enumerate(arguments.query, start=1):
        try:
            result = active_retriever.retrieve(
                RawCvRetrievalQuery(
                    text=question_text,
                    result_limit=arguments.result_limit,
                )
            )
        except (CvRawRetrievalContractError, CvRawRetrievalError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2

        if question_index == 1:
            print(f"  Collection: {result.collection_name}")
            print(f"  Collection records: {result.collection_record_count}")
            print(f"  Distance metric: {result.distance_metric}")
            print(f"  Embedding model: {result.embedding_model}")
            print(f"  Embedding dimension: {result.embedding_dimension}")

        print(f"\nQUERY: {result.query.text}")
        print(f"  Requested raw chunks: {result.requested_result_limit}")
        print(f"  Returned raw chunks: {result.returned_result_count}")
        print(f"  Candidates represented: {result.distinct_candidate_count}")

        if not result.hits:
            print("  No raw evidence returned.")
            continue

        for hit in result.hits:
            source = hit.source
            print(
                f"  {hit.rank}. distance={hit.distance:.6f} | "
                f"candidate={source.candidate_id} | "
                f"name={source.candidate_name or ''} | "
                f"title={source.professional_title or ''}"
            )
            print(
                f"     chunk={hit.chunk_id} | section={source.section_name} | "
                f"pages={source.page_label} | file={source.source_filename}"
            )
            print(
                f"     document={source.document_id} | "
                f"hash={source.document_hash[:12]} | "
                f"chunk_index={source.chunk_index} | "
                f"chunking={source.chunking_version}"
            )
            preview = " ".join(hit.text.split())
            if arguments.preview_characters:
                preview = preview[: arguments.preview_characters]
                if preview:
                    print(f"     {preview}")
    return 0


def main() -> None:
    """Run the CLI and expose shell-friendly exit status."""

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
