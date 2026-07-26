"""Command-line tool for validating the complete saved profile collection.

It loads the dataset plan and generated JSON, runs collection-wide checks, and
prints a pass/fail report before CV rendering begins.
"""

import argparse
from collections.abc import Sequence
import sys

from app.scripts.cli_help import build_cli_parser

from app.candidate_generation import (
    CandidatePlanError,
    CandidateProfilesFileError,
    load_candidate_dataset_plan,
    load_candidate_profiles,
    validate_candidate_dataset,
)
from app.core.config import Settings, get_settings


def build_parser() -> argparse.ArgumentParser:
    """Describe the complete candidate profile validation command."""

    return build_cli_parser(
        description=(
            "Validate the saved candidate profile collection against the "
            "controlled dataset plan."
        ),
        sections=(
            (
                "Valid command combinations",
                (
                    "This command validates the complete configured collection and takes no filters.",
                    "Use --help to display this reference.",
                ),
            ),
            (
                "What the command changes",
                ("It reads the plan and profile JSON. It writes nothing and makes no provider call.",),
            ),
            (
                "Example",
                ("python -m app.scripts.validate_candidate_profiles",),
            ),
        ),
    )


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
) -> int:
    """Load the plan and profiles, print all collection results, and return a shell status."""

    build_parser().parse_args(tuple(argv or ()))
    active_settings = settings or get_settings()

    try:
        plan = load_candidate_dataset_plan(
            active_settings.candidate_dataset_plan_path
        )
        profiles = load_candidate_profiles(
            active_settings.candidate_profiles_output_path
        )
    except (CandidatePlanError, CandidateProfilesFileError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    report = validate_candidate_dataset(plan, profiles)

    print("CANDIDATE DATASET VALIDATION")
    print(f"  Plan version: {plan.dataset_version}")
    print(f"  Plan path: {active_settings.candidate_dataset_plan_path}")
    print(f"  Profiles path: {active_settings.candidate_profiles_output_path}")
    print(
        "  Profiles: "
        f"{report.actual_profile_count}/{report.expected_profile_count}"
    )
    print(
        "  Slot-compliant profiles: "
        f"{report.compliant_profile_count}/{report.expected_profile_count}"
    )
    print(
        "  Validated search scenarios: "
        f"{report.validated_scenario_count}/{report.total_scenario_count}"
    )
    print(f"  Uniqueness problems: {report.uniqueness_problem_count}")
    print(f"  Distribution problems: {report.distribution_problem_count}")

    if report.issues:
        print("  Result: FAIL")
        print("\nVALIDATION PROBLEMS")
        for issue in report.issues:
            print(f"  - {issue}")
        return 1

    print("  Result: PASS")
    return 0


def main() -> None:
    """Execute the validation command and expose its status to the shell."""

    raise SystemExit(run_cli(sys.argv[1:]))


if __name__ == "__main__":
    main()
