"""Inspect grounded recruiter answers, citations, and provider selection."""

import argparse
from collections.abc import Sequence
import sys

from app.core.config import Settings, get_settings
from app.cv_answer_generation import (
    GroundedAnswerConfigurationError,
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
            "recruiter answer, validated citations, and active provider."
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
    try:
        active_generator = generator or build_grounded_cv_answer_generator(
            active_settings
        )
    except GroundedAnswerConfigurationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    print("GROUNDED CV ANSWER INSPECTION")
    print(f"  Configured provider: {active_settings.cv_grounded_answer_provider}")

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
        response = result.response
        print(f"\nQUERY: {retrieval.query.text}")
        print(f"  Retrieval outcome: {retrieval.outcome}")
        print(f"  Answer outcome: {response.outcome}")
        print(f"  Active provider: {response.provider}")
        print(f"  Model: {response.model}")
        print(f"  Provider called: {response.provider_called}")
        print(f"  Provider attempts: {response.provider_attempts}")
        print(
            f"  Candidates: {len(response.candidates)}/"
            f"{retrieval.requested_candidate_limit}"
        )
        print(f"  Validated sources: {len(response.sources)}")
        print("\nANSWER")
        print(response.answer)
        if response.answer_citation_ids:
            print(
                "  citations=" + ", ".join(response.answer_citation_ids)
            )

        if response.candidates:
            print("\nCANDIDATE ASSESSMENTS")
            for index, candidate in enumerate(response.candidates, start=1):
                print(
                    f"  {index}. {candidate.candidate_name} | "
                    f"{candidate.professional_title} | "
                    f"{candidate.candidate_id}"
                )
                print(
                    "     matched_requirements="
                    + ", ".join(candidate.matched_requirements)
                )
                print(
                    "     citations=" + ", ".join(candidate.citation_ids)
                )
                print(f"     {candidate.assessment}")

        if response.sources:
            print("\nSOURCES")
            for source in response.sources:
                supports = ", ".join(source.supports) or "support-only"
                print(
                    f"  [{source.source_id}] {source.source_filename} | "
                    f"page {source.page_label} | {source.section_name} | "
                    f"{source.chunk_id}"
                )
                print(
                    f"     candidate={source.candidate_id} | supports={supports}"
                )

        if response.warnings:
            print("\nWARNINGS")
            for warning in response.warnings:
                print(f"  - {warning}")

        if arguments.show_context:
            print("\n--- RETRIEVAL CONTEXT SUPPLIED TO MODEL ---")
            print(retrieval.context_text)
            print("--- END RETRIEVAL CONTEXT ---")

    return 0


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
