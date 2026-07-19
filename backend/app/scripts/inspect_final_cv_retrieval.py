"""Inspect final support thresholds, budgets, and prompt-ready CV context."""

import argparse
from collections.abc import Sequence
import sys

from app.core.config import Settings, get_settings
from app.cv_retrieval import (
    CvFinalRetrievalError,
    CvRawRetrievalContractError,
    FinalCvRetrievalQuery,
    FinalCvRetriever,
    build_final_cv_retriever,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect the final supported-candidate boundary and bounded "
            "prompt-ready CV evidence."
        )
    )
    parser.add_argument(
        "--query",
        action="append",
        required=True,
        help="Recruiter question. Repeat to inspect several questions.",
    )
    parser.add_argument(
        "--semantic-result-limit",
        type=int,
        help="Broad semantic chunks requested before later retrieval stages.",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        help="Maximum final candidates returned per question.",
    )
    parser.add_argument(
        "--preview-characters",
        type=int,
        default=220,
        help="Maximum evidence preview characters (default: 220).",
    )
    parser.add_argument(
        "--show-context",
        action="store_true",
        help="Print the complete bounded prompt-ready context.",
    )
    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    retriever: FinalCvRetriever | None = None,
) -> int:
    arguments = build_parser().parse_args(argv)
    if arguments.preview_characters < 0:
        print(
            "ERROR: --preview-characters cannot be negative.",
            file=sys.stderr,
        )
        return 2

    active_retriever = retriever or build_final_cv_retriever(
        settings or get_settings()
    )
    print("FINAL CV RETRIEVAL INSPECTION")

    for question_text in arguments.query:
        try:
            result = active_retriever.retrieve(
                FinalCvRetrievalQuery(
                    question_text,
                    semantic_result_limit=arguments.semantic_result_limit,
                    candidate_limit=arguments.candidate_limit,
                )
            )
        except (CvFinalRetrievalError, CvRawRetrievalContractError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2

        print(f"\nQUERY: {result.query.text}")
        print(f"  Outcome: {result.outcome}")
        print(f"  Message: {result.support_message}")
        print(
            f"  Candidates: {result.returned_candidate_count}/"
            f"{result.requested_candidate_limit}"
        )
        print(
            f"  Evidence chunks: {result.evidence_chunk_count}/"
            f"{result.max_total_evidence_chunks}"
        )
        print(
            f"  Context characters: {result.context_character_count}/"
            f"{result.max_context_characters}"
        )
        print(f"  Budget exhausted: {result.budget_exhausted}")

        for candidate in result.candidates:
            print(
                f"  {candidate.rank}. candidate={candidate.candidate_id} | "
                f"name={candidate.candidate_name or ''} | "
                f"title={candidate.professional_title or ''}"
            )
            print(
                f"     support={candidate.support_level} | "
                f"candidate_score={candidate.candidate_score:.4f} | "
                f"coverage={candidate.coverage_score:.4f} | "
                f"original_rank={candidate.original_candidate_rank}"
            )
            print(
                "     matched_requirements="
                + (", ".join(candidate.matched_condition_labels) or "none")
            )
            for evidence in candidate.evidence:
                print(
                    f"     source {evidence.order}: {evidence.source_label}"
                )
                print(
                    "       supports="
                    + (", ".join(evidence.condition_keys) or "support-only")
                )
                if arguments.preview_characters:
                    preview = evidence.text[: arguments.preview_characters]
                    print(f"       {preview}")

        if arguments.show_context:
            print("\n--- PROMPT-READY CONTEXT ---")
            print(result.context_text)
            print("--- END CONTEXT ---")
    return 0


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
