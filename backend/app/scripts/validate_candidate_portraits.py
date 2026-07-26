"""Command-line tool for checking the planned portrait collection.

It validates plan coverage, image structure, missing files, and unexpected
portraits for photo-free candidates, then returns a shell-friendly pass/fail
status.
"""

import sys
import argparse
from collections.abc import Sequence

from app.scripts.cli_help import build_cli_parser

from app.candidate_generation.persistence import (
    CandidateProfilesFileError,
    load_candidate_profiles,
)
from app.core.config import Settings, get_settings
from app.portrait_generation import (
    PortraitCoveragePlanError,
    load_portrait_coverage_plan,
    validate_portrait_collection,
    validate_portrait_coverage_against_profiles,
)


def build_parser() -> argparse.ArgumentParser:
    """Describe the complete portrait collection validation command."""

    return build_cli_parser(
        description=(
            "Validate portrait-plan coverage and every normalized candidate "
            "image in the configured directory."
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
                ("It reads profiles, the portrait plan, and image files. It writes nothing.",),
            ),
            (
                "Example",
                ("python -m app.scripts.validate_candidate_portraits",),
            ),
        ),
    )


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
) -> int:
    """Validate the portrait plan and image directory, then print one summary report."""

    if argv and "--help" not in argv and "-h" not in argv:
        print("ERROR: This command accepts no arguments.", file=sys.stderr)
        return 2
    build_parser().parse_args(tuple(argv or ()))

    active_settings = settings or get_settings()

    try:
        profiles = load_candidate_profiles(
            active_settings.candidate_profiles_output_path
        )
        coverage_plan = load_portrait_coverage_plan(
            active_settings.candidate_portrait_plan_path
        )
        validate_portrait_coverage_against_profiles(
            coverage_plan,
            profiles,
        )
    except (CandidateProfilesFileError, PortraitCoveragePlanError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    result = validate_portrait_collection(
        profiles,
        portrait_candidate_ids=coverage_plan.portrait_candidate_id_set,
        images_directory=active_settings.candidate_images_directory,
        expected_size=active_settings.portrait_normalized_size,
    )

    print("CANDIDATE PORTRAIT VALIDATION")
    print(f"  Profiles path: {active_settings.candidate_profiles_output_path}")
    print(f"  Portrait plan: {active_settings.candidate_portrait_plan_path}")
    print(f"  Images path: {active_settings.candidate_images_directory}")
    print(f"  Total profiles: {len(profiles)}")
    print(f"  Planned portraits: {result.expected_count}")
    print(f"  Planned photo-free CVs: {len(profiles) - result.expected_count}")
    print(f"  Valid portraits: {result.valid_count}")
    print(f"  Missing portraits: {len(result.missing_candidate_ids)}")
    print(f"  Invalid portraits: {len(result.invalid_portraits)}")
    print(f"  Unexpected image files: {len(result.unexpected_files)}")

    if result.missing_candidate_ids:
        print("\nMISSING")
        for candidate_id in result.missing_candidate_ids:
            print(f"  {candidate_id}")

    if result.invalid_portraits:
        print("\nINVALID")
        for problem in result.invalid_portraits:
            print(f"  {problem}")

    if result.unexpected_files:
        print("\nUNEXPECTED")
        for filename in result.unexpected_files:
            print(f"  {filename}")

    print(f"\n  Result: {'PASS' if result.is_valid else 'FAIL'}")
    return 0 if result.is_valid else 1


def main() -> None:
    """Execute the command and expose its return status to the shell."""

    raise SystemExit(run_cli(sys.argv[1:]))


if __name__ == "__main__":
    main()
