"""Command-line tool for final CV PDF validation.

It checks that every expected PDF exists, opens correctly, contains all intended
visible facts, stays within the page limit, and supports the planned search
scenarios using PDF-extracted text.
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
)
from app.core.config import Settings, get_settings
from app.cv_rendering import validate_cv_pdf_collection


def build_parser() -> argparse.ArgumentParser:
    """Describe the complete rendered CV validation command."""

    return build_cli_parser(
        description=(
            "Validate every configured candidate PDF for existence, readable "
            "text, expected facts, page limits, and search scenarios."
        ),
        sections=(
            (
                "Valid command combinations",
                (
                    "This command validates the complete configured PDF collection and takes no filters.",
                    "Use --help to display this reference.",
                ),
            ),
            (
                "What the command changes",
                ("It reads the plan, profiles, and PDF files. It writes nothing.",),
            ),
            (
                "Example",
                ("python -m app.scripts.validate_candidate_cvs",),
            ),
        ),
    )


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
) -> int:
    """Load the plan and profiles, validate the PDF collection, and print pass/fail details."""

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

    report = validate_cv_pdf_collection(
        plan,
        profiles,
        pdf_directory=active_settings.cv_pdfs_output_directory,
    )

    print("FINAL CV PDF VALIDATION")
    print(f"  Plan version: {plan.dataset_version}")
    print(f"  Profiles path: {active_settings.candidate_profiles_output_path}")
    print(f"  PDF directory: {active_settings.cv_pdfs_output_directory}")
    print(
        "  PDF files: "
        f"{report.actual_pdf_count}/{report.expected_pdf_count}"
    )
    print(
        "  Fully validated PDFs: "
        f"{report.validated_pdf_count}/{report.expected_pdf_count}"
    )
    print(
        "  Searchable profile facts: "
        f"{report.validated_fact_count}/{report.expected_fact_count}"
    )
    print(
        "  Validated search scenarios: "
        f"{report.validated_scenario_count}/{report.total_scenario_count}"
    )

    if report.candidate_results:
        page_counts = [result.page_count for result in report.candidate_results]
        text_counts = [
            result.extracted_text_characters
            for result in report.candidate_results
        ]
        print(
            "  Page range: "
            f"{min(page_counts)}-{max(page_counts)}"
        )
        print(
            "  Extracted text range: "
            f"{min(text_counts)}-{max(text_counts)} non-whitespace characters"
        )

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
