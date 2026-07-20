"""Run the diagnostic recruiter-query paraphrase matrix.

The command never calls OpenAI or Gemini. It exercises the existing retrieval
pipeline, records whether a hosted provider *would* be called, and can write a
full JSON report for before/after comparison during the query-understanding
refactor.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
import sys

from app.core.config import Settings, get_settings
from app.cv_retrieval import (
    CvQueryRobustnessReport,
    FinalCvRetriever,
    build_final_cv_retriever,
    evaluate_query_robustness,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate recruiter-query paraphrases through the unchanged final "
            "retrieval pipeline without calling a hosted answer provider."
        )
    )
    parser.add_argument(
        "--matrix",
        type=Path,
        help="Robustness matrix path. Defaults to application settings.",
    )
    parser.add_argument(
        "--family-id",
        action="append",
        default=[],
        help="Evaluate one family ID. Repeat to select several families.",
    )
    parser.add_argument(
        "--scenario-id",
        action="append",
        default=[],
        help="Evaluate one scenario ID. Repeat to select several scenarios.",
    )
    parser.add_argument(
        "--semantic-result-limit",
        type=int,
        help="Override the matrix semantic recall limit.",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        help="Override the matrix final candidate limit.",
    )
    parser.add_argument(
        "--diagnostic-candidate-limit",
        type=int,
        default=5,
        help="Maximum pre-threshold candidate rows printed and stored per query.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Write the complete machine-readable diagnostic report.",
    )
    parser.add_argument(
        "--failed-only",
        action="store_true",
        help="Print only failed scenarios while retaining the full JSON report.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print parser features and candidate-coverage diagnostics.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with status 1 when any scenario fails its expectation.",
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
    matrix_path = (
        arguments.matrix or active_settings.cv_query_robustness_matrix_path
    )
    active_retriever = retriever or build_final_cv_retriever(active_settings)

    try:
        report = evaluate_query_robustness(
            active_retriever,
            matrix_path=matrix_path,
            family_ids=tuple(arguments.family_id),
            scenario_ids=tuple(arguments.scenario_id),
            semantic_result_limit=arguments.semantic_result_limit,
            candidate_limit=arguments.candidate_limit,
            diagnostic_candidate_limit=(
                arguments.diagnostic_candidate_limit
            ),
        )
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    _print_report(
        report,
        failed_only=arguments.failed_only,
        verbose=arguments.verbose,
    )
    if arguments.json_output is not None:
        try:
            _write_json_report(arguments.json_output, report)
        except ValueError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2
    if arguments.strict and not report.passed:
        return 1
    return 0


def _print_report(
    report: CvQueryRobustnessReport,
    *,
    failed_only: bool,
    verbose: bool,
) -> None:
    print("CV QUERY ROBUSTNESS DIAGNOSTIC")
    print(f"  Matrix path: {report.matrix_path}")
    print(f"  Matrix version: {report.matrix_version}")
    print(f"  Families: {report.family_count}")
    print(f"  Scenarios: {report.scenario_count}")
    print(f"  Passed: {report.passed_count}")
    print(f"  Failed: {report.failed_count}")
    print(
        "  Inconsistent outcomes: "
        f"{report.inconsistent_outcome_family_count} families"
    )
    print(
        "  Inconsistent candidate sets: "
        f"{report.inconsistent_candidate_family_count} families"
    )
    print(f"  Hosted provider calls made: {report.hosted_provider_calls_made}")
    print(
        "  Result: "
        + ("PASS" if report.passed else "BASELINE MISMATCHES FOUND")
    )
    print("\nFAMILIES")

    for family_evaluation in report.family_evaluations:
        family = family_evaluation.family
        status = "PASS" if family_evaluation.passed else "FAIL"
        print(
            f"  [{status}] {family.family_id} | "
            f"{family_evaluation.passed_count}/"
            f"{family_evaluation.scenario_count} passed | "
            f"outcome_consistent={family_evaluation.outcome_consistent} | "
            "candidate_set_consistent="
            f"{family_evaluation.candidate_set_consistent}"
        )
        print(f"     {family.description}")
        for evaluation in family_evaluation.evaluations:
            if failed_only and evaluation.passed:
                continue
            _print_scenario(evaluation, verbose=verbose)


def _print_scenario(evaluation, *, verbose: bool) -> None:
    status = "PASS" if evaluation.passed else "FAIL"
    expected = ", ".join(evaluation.expected_candidate_ids) or "none"
    returned = ", ".join(evaluation.returned_candidate_ids) or "none"
    print(
        f"     [{status}] {evaluation.scenario_id} | "
        f"outcome={evaluation.outcome} | "
        "provider_would_call="
        f"{evaluation.hosted_provider_would_be_called}"
    )
    print(f"        question={evaluation.question}")
    print(
        f"        expectation={evaluation.expected_outcome}/"
        f"{evaluation.candidate_policy} | expected={expected} | "
        f"minimum={evaluation.minimum_returned_candidates}"
    )
    print(f"        returned={returned}")
    if evaluation.failure_reasons:
        print("        failures=" + " | ".join(evaluation.failure_reasons))
    if evaluation.error:
        print(f"        error={evaluation.error}")
    if not verbose or evaluation.parser is None:
        return

    parser = evaluation.parser
    conditions = ", ".join(
        f"{condition.kind}:{condition.label}"
        for condition in parser.hard_conditions
    ) or "none"
    print(
        "        parser.lexical_terms="
        + (", ".join(parser.lexical_terms) or "none")
    )
    print(
        "        parser.text_relations="
        + (", ".join(parser.text_relations) or "none")
    )
    print(
        "        parser.numeric_constraints="
        + (", ".join(parser.numeric_constraints) or "none")
    )
    print(f"        parser.hard_conditions={conditions}")
    print(
        "        parser.unconditioned_terms="
        + (", ".join(parser.unconditioned_lexical_terms) or "none")
    )
    print(
        "        parser.discarded_tokens="
        + (", ".join(parser.discarded_tokens) or "none")
    )
    for candidate in evaluation.candidate_diagnostics:
        matched = ", ".join(candidate.matched_condition_labels) or "none"
        missing = ", ".join(candidate.missing_condition_labels) or "none"
        print(
            f"        candidate[{candidate.rank}] "
            f"{candidate.candidate_id} | score={candidate.candidate_score:.3f} "
            f"coverage={candidate.coverage_score:.3f} | "
            f"selected={candidate.selected_for_final_context}"
        )
        print(f"           matched={matched}")
        print(f"           missing={missing}")


def _write_json_report(
    path: Path,
    report: CvQueryRobustnessReport,
) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report.to_json_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        raise ValueError(
            f"Could not write robustness report {path}: {error}"
        ) from error
    print(f"\nJSON report: {path}")


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
