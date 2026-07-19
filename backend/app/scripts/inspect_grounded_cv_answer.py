"""Inspect grounded recruiter answers generated from final WP6 evidence."""

import argparse
from collections.abc import Sequence
import sys

from app.core.config import Settings, get_settings
from app.cv_answer_generation import (
    GroundedAnswerGenerationFailed,
    GroundedCvAnswerGenerator,
    build_grounded_cv_answer_generator,
)
from app.cv_retrieval import CvRawRetrievalContractError, FinalCvRetrievalQuery


def build_parser() -> argparse.ArgumentParser:
    """Create the reusable grounded-answer inspection parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Retrieve source-grounded CV evidence and inspect the structured "
            "recruiter answer generated from that evidence."
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
        help="Maximum final candidates made available to generation.",
    )
    parser.add_argument(
        "--show-context",
        action="store_true",
        help="Print the exact bounded WP6 context supplied to the model.",
    )
    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    generator: GroundedCvAnswerGenerator | None = None,
) -> int:
    """Run grounded answer inspection for one or more recruiter questions."""

    arguments = build_parser().parse_args(argv)
    active_settings = settings or get_settings()
    active_generator = generator or build_grounded_cv_answer_generator(
        active_settings
    )

    print("GROUNDED CV ANSWER INSPECTION")
    print(f"  Model: {active_settings.cv_grounded_answer_model}")

    for question_text in arguments.query:
        try:
            result = active_generator.generate(
                FinalCvRetrievalQuery(
                    question_text,
                    candidate_limit=arguments.candidate_limit,
                    semantic_result_limit=arguments.semantic_result_limit,
                )
            )
        except (
            GroundedAnswerGenerationFailed,
            CvRawRetrievalContractError,
        ) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2

        retrieval = result.retrieval_result
        draft = result.draft
        print(f"\nQUERY: {retrieval.query.text}")
        print(f"  Retrieval outcome: {retrieval.outcome}")
        print(f"  Answer outcome: {draft.outcome}")
        print(f"  Provider called: {result.provider_called}")
        print(f"  Provider attempts: {result.attempts}")
        print(
            f"  Candidates: {len(draft.candidates)}/"
            f"{retrieval.requested_candidate_limit}"
        )
        print("\nANSWER")
        print(draft.answer)

        if draft.candidates:
            print("\nCANDIDATE ASSESSMENTS")
            for index, candidate in enumerate(draft.candidates, start=1):
                print(
                    f"  {index}. {candidate.candidate_name} | "
                    f"{candidate.professional_title} | "
                    f"{candidate.candidate_id}"
                )
                print(
                    "     matched_requirements="
                    + ", ".join(candidate.matched_requirements)
                )
                print(f"     {candidate.assessment}")

        if draft.limitations:
            print("\nLIMITATIONS")
            for limitation in draft.limitations:
                print(f"  - {limitation}")

        if arguments.show_context:
            print("\n--- RETRIEVAL CONTEXT SUPPLIED TO MODEL ---")
            print(retrieval.context_text)
            print("--- END RETRIEVAL CONTEXT ---")

    return 0


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
