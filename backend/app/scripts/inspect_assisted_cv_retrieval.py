"""Inspect semantic, lexical, and numeric evidence before candidate grouping."""

import argparse
from collections.abc import Sequence
import sys

from app.core.config import Settings, get_settings
from app.cv_retrieval import (
    AssistedCvRetriever,
    CvAssistedRetrievalError,
    CvRawRetrievalContractError,
    RawCvRetrievalQuery,
    build_assisted_cv_retriever,
)


def build_parser() -> argparse.ArgumentParser:
    """Create the WP6 exact-condition inspection command."""

    parser = argparse.ArgumentParser(
        description=(
            "Inspect semantic CV retrieval assisted by exact lexical and "
            "numeric evidence."
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
        help="Broad semantic chunks requested before exact assistance.",
    )
    parser.add_argument(
        "--display-limit",
        type=int,
        default=20,
        help="Scored chunks printed per question (default: 20).",
    )
    parser.add_argument(
        "--preview-characters",
        type=int,
        default=220,
        help="Maximum normalized evidence preview per hit (default: 220).",
    )
    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    retriever: AssistedCvRetriever | None = None,
) -> int:
    """Print interpretable score components and exact-condition matches."""

    arguments = build_parser().parse_args(argv)
    if arguments.display_limit < 1:
        print("ERROR: --display-limit must be positive.", file=sys.stderr)
        return 2
    if arguments.preview_characters < 0:
        print(
            "ERROR: --preview-characters cannot be negative.",
            file=sys.stderr,
        )
        return 2

    active_retriever = retriever or build_assisted_cv_retriever(
        settings or get_settings()
    )
    print("ASSISTED CV RETRIEVAL INSPECTION")

    for question_text in arguments.query:
        try:
            result = active_retriever.retrieve(
                RawCvRetrievalQuery(
                    text=question_text,
                    result_limit=arguments.result_limit,
                )
            )
        except (CvRawRetrievalContractError, CvAssistedRetrievalError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2

        features = result.query_features
        raw = result.raw_result
        print(f"\nQUERY: {raw.query.text}")
        print(f"  Semantic chunks requested: {raw.requested_result_limit}")
        print(f"  Collection records scanned: {result.scanned_record_count}")
        print(f"  Supplemental exact hits: {result.supplemental_hit_count}")
        print(f"  Duplicate chunks removed: {result.duplicates_removed}")
        print(f"  Unique scored chunks: {result.returned_result_count}")
        print(f"  Candidates represented: {result.distinct_candidate_count}")
        print(
            "  Lexical terms: "
            + (", ".join(features.lexical_terms) or "none")
        )
        print(
            "  Numeric constraints: "
            + (
                ", ".join(
                    constraint.display_value
                    for constraint in features.numeric_constraints
                )
                or "none"
            )
        )

        for hit in result.hits[: arguments.display_limit]:
            source = hit.source
            score = hit.score
            origin = "exact-scan" if hit.supplemental_exact_hit else "semantic"
            raw_rank = str(hit.raw_rank) if hit.raw_rank is not None else "-"
            distance = f"{hit.distance:.6f}" if hit.distance is not None else "-"
            print(
                f"  {hit.rank}. score={score.combined_score:.4f} | "
                f"semantic={score.semantic_score:.4f} | "
                f"lexical={score.lexical_score:.4f} | "
                f"numeric={score.numeric_score:.4f} | origin={origin}"
            )
            print(
                f"     raw_rank={raw_rank} | distance={distance} | "
                f"candidate={source.candidate_id} | "
                f"name={source.candidate_name or ''} | "
                f"title={source.professional_title or ''}"
            )
            print(
                f"     chunk={hit.chunk_id} | section={source.section_name} | "
                f"pages={source.page_label} | file={source.source_filename}"
            )
            print(
                "     matched_terms="
                + (", ".join(score.matched_terms) or "none")
                + " | matched_text="
                + (", ".join(score.matched_term_evidence) or "none")
            )
            print(
                "     matched_numbers="
                + (", ".join(score.matched_numeric_values) or "none")
                + " | numeric_context="
                + (", ".join(score.matched_numeric_contexts) or "none")
                + f" | contextual_numeric={score.contextual_numeric_match}"
            )
            if arguments.preview_characters:
                preview = " ".join(hit.text.split())[
                    : arguments.preview_characters
                ]
                if preview:
                    print(f"     {preview}")
    return 0


def main() -> None:
    """Run the CLI and expose shell-friendly exit status."""

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
