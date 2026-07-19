"""Inspect candidate-level coverage, rank components, and selected CV evidence."""

import argparse
from collections.abc import Sequence
import sys

from app.core.config import Settings, get_settings
from app.cv_retrieval import (
    CandidateAwareCvRetriever,
    CandidateCvRetrievalQuery,
    CvCandidateRetrievalError,
    CvRawRetrievalContractError,
    build_candidate_aware_cv_retriever,
)


def build_parser() -> argparse.ArgumentParser:
    """Create the WP6 candidate-aware inspection command."""

    parser = argparse.ArgumentParser(
        description=(
            "Inspect candidate grouping, compound condition coverage, and "
            "bounded source evidence."
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
        "--raw-limit",
        dest="semantic_result_limit",
        type=int,
        help="Broad semantic chunks requested before exact assistance.",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        help="Maximum candidate results returned per question.",
    )
    parser.add_argument(
        "--evidence-limit",
        type=int,
        help="Maximum evidence chunks retained per candidate.",
    )
    parser.add_argument(
        "--display-limit",
        type=int,
        default=10,
        help="Candidate results printed per question (default: 10).",
    )
    parser.add_argument(
        "--preview-characters",
        type=int,
        default=200,
        help="Maximum normalized evidence preview per source (default: 200).",
    )
    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    retriever: CandidateAwareCvRetriever | None = None,
) -> int:
    """Print interpretable candidate ranks and the evidence covering conditions."""

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

    active_retriever = retriever or build_candidate_aware_cv_retriever(
        settings or get_settings()
    )
    print("CANDIDATE-AWARE CV RETRIEVAL INSPECTION")

    for question_text in arguments.query:
        try:
            result = active_retriever.retrieve(
                CandidateCvRetrievalQuery(
                    text=question_text,
                    candidate_limit=arguments.candidate_limit,
                    semantic_result_limit=arguments.semantic_result_limit,
                    evidence_limit=arguments.evidence_limit,
                )
            )
        except (CvRawRetrievalContractError, CvCandidateRetrievalError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2

        assisted = result.assisted_result
        print(f"\nQUERY: {assisted.raw_result.query.text}")
        print(f"  Scored chunks: {assisted.returned_result_count}")
        print(f"  Grouped candidates: {result.grouped_candidate_count}")
        print(f"  Returned candidates: {result.returned_candidate_count}")
        print(f"  Evidence limit per candidate: {result.evidence_per_candidate_limit}")
        print(
            "  Conditions: "
            + (
                ", ".join(
                    f"{condition.label} [{condition.kind}]"
                    for condition in result.conditions
                )
                or "none (semantic ranking fallback)"
            )
        )

        for candidate in result.candidates[: arguments.display_limit]:
            print(
                f"  {candidate.rank}. candidate={candidate.candidate_id} | "
                f"name={candidate.candidate_name or ''} | "
                f"title={candidate.professional_title or ''}"
            )
            print(
                f"     score={candidate.candidate_score:.4f} | "
                f"coverage={candidate.coverage_score:.4f} | "
                f"condition_quality={candidate.condition_quality_score:.4f} | "
                f"semantic_support={candidate.semantic_support_score:.4f}"
            )
            print(
                f"     matched_conditions={candidate.matched_condition_count}/"
                f"{candidate.total_condition_count} | "
                f"complete={candidate.complete_condition_coverage} | "
                f"candidate_hits={candidate.total_candidate_hit_count} | "
                f"selected_evidence={len(candidate.evidence)}"
            )
            print(
                "     condition_evidence="
                + (
                    ", ".join(
                        f"{match.condition.label}->{match.chunk_id}"
                        for match in candidate.matched_conditions
                    )
                    or "none"
                )
            )
            for evidence in candidate.evidence:
                hit = evidence.hit
                source = hit.source
                print(
                    f"     evidence {evidence.order}: chunk={hit.chunk_id} | "
                    f"assisted_rank={hit.rank} | section={source.section_name} | "
                    f"pages={source.page_label} | file={source.source_filename}"
                )
                print(
                    "       covers="
                    + (", ".join(evidence.condition_keys) or "support only")
                )
                if arguments.preview_characters:
                    preview = " ".join(hit.text.split())[
                        : arguments.preview_characters
                    ]
                    if preview:
                        print(f"       {preview}")
    return 0


def main() -> None:
    """Run the CLI and expose shell-friendly exit status."""

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
