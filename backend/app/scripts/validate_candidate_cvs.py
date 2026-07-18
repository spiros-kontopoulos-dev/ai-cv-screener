"""Validate the final rendered CV PDF collection.

Example:

    python -m app.scripts.validate_candidate_cvs
"""

import sys

from app.candidate_generation import (
    CandidatePlanError,
    CandidateProfilesFileError,
    load_candidate_dataset_plan,
    load_candidate_profiles,
)
from app.core.config import Settings, get_settings
from app.cv_rendering import validate_cv_pdf_collection


def run_cli(*, settings: Settings | None = None) -> int:
    """Load configured inputs, validate PDFs, print a report, and return status."""

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

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
