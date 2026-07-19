"""Validate final CV retrieval against all committed recruiter scenarios."""

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from app.core.config import Settings, get_settings
from app.cv_retrieval import (
    CvRetrievalEvaluationReport,
    FinalCvRetriever,
    build_final_cv_retriever,
    evaluate_retrieval_scenarios,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the final source-traceable retrieval pipeline against the "
            "committed search scenarios."
        )
    )
    parser.add_argument(
        "--plan",
        type=Path,
        help="Candidate dataset plan path. Defaults to application settings.",
    )
    parser.add_argument(
        "--scenario-id",
        action="append",
        default=[],
        help="Validate one scenario ID. Repeat to select several.",
    )
    parser.add_argument(
        "--semantic-result-limit",
        type=int,
        help="Override broad semantic chunk recall for validation.",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        help="Override final candidate output limit.",
    )
    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    retriever: FinalCvRetriever | None = None,
) -> int:
    arguments = build_parser().parse_args(argv)
    active_settings = settings or get_settings()
    plan_path = arguments.plan or active_settings.candidate_dataset_plan_path
    active_retriever = retriever or build_final_cv_retriever(active_settings)

    try:
        report = evaluate_retrieval_scenarios(
            active_retriever,
            plan_path=plan_path,
            scenario_ids=tuple(arguments.scenario_id),
            semantic_result_limit=arguments.semantic_result_limit,
            candidate_limit=arguments.candidate_limit,
        )
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    _print_report(report)
    return 0 if report.passed else 1


def _print_report(report: CvRetrievalEvaluationReport) -> None:
    print("FINAL CV RETRIEVAL VALIDATION")
    print(f"  Plan path: {report.plan_path}")
    print(f"  Scenarios: {report.scenario_count}")
    print(f"  Passed: {report.passed_count}")
    print(f"  Failed: {report.failed_count}")
    print(f"  Result: {'PASS' if report.passed else 'FAIL'}")
    print("\nSCENARIOS")

    for evaluation in report.evaluations:
        status = "PASS" if evaluation.passed else "FAIL"
        expected = ", ".join(
            evaluation.scenario.expected_candidate_ids
        ) or "none"
        returned = ", ".join(evaluation.returned_candidate_ids) or "none"
        print(
            f"  [{status}] {evaluation.scenario.scenario_id} | "
            f"outcome={evaluation.outcome}"
        )
        print(f"     expected={expected}")
        print(f"     returned={returned}")
        print(
            f"     sources={evaluation.source_traceable} | "
            f"budget={evaluation.budget_compliant} | "
            f"context_chars={evaluation.context_character_count} | "
            f"evidence_chunks={evaluation.evidence_chunk_count}"
        )
        if evaluation.missing_expected_candidate_ids:
            print(
                "     missing="
                + ", ".join(evaluation.missing_expected_candidate_ids)
            )
        if evaluation.unexpected_candidate_ids:
            print(
                "     additional="
                + ", ".join(evaluation.unexpected_candidate_ids)
            )
        if evaluation.error:
            print(f"     error={evaluation.error}")


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
