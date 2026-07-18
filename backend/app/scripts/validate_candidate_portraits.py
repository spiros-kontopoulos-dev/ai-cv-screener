"""Validate profile-to-portrait mapping and normalized image integrity."""

import sys
from collections.abc import Sequence

from app.candidate_generation.persistence import (
    CandidateProfilesFileError,
    load_candidate_profiles,
)
from app.core.config import Settings, get_settings
from app.portrait_generation import validate_portrait_collection


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
) -> int:
    """Validate the complete portrait collection and print a concise report."""

    # Keep an argv parameter for symmetry and straightforward test injection.
    if argv:
        print("ERROR: This command accepts no arguments.", file=sys.stderr)
        return 2

    active_settings = settings or get_settings()

    try:
        profiles = load_candidate_profiles(
            active_settings.candidate_profiles_output_path
        )
    except CandidateProfilesFileError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    result = validate_portrait_collection(
        profiles,
        images_directory=active_settings.candidate_images_directory,
        expected_size=active_settings.portrait_normalized_size,
    )

    print("CANDIDATE PORTRAIT VALIDATION")
    print(f"  Profiles path: {active_settings.candidate_profiles_output_path}")
    print(f"  Images path: {active_settings.candidate_images_directory}")
    print(f"  Expected portraits: {result.expected_count}")
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

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
