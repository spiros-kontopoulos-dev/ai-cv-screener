"""Plan or render validated candidate profiles as HTML and PDF CVs.

Examples:

    python -m app.scripts.render_candidate_cvs \\
        --candidate-id candidate_003 --dry-run

    python -m app.scripts.render_candidate_cvs \\
        --candidate-id candidate_003 --keep-html

    python -m app.scripts.render_candidate_cvs --all
"""

import argparse
import sys
from collections.abc import Sequence

from app.candidate_generation.persistence import (
    CandidateProfilesFileError,
    load_candidate_profiles,
)
from app.core.config import Settings, get_settings
from app.cv_rendering import (
    CvRenderJob,
    CvRenderResult,
    CvRenderingError,
    CvRenderingPlanError,
    build_cv_render_jobs,
    find_profile_boundaries,
    render_cv_jobs,
    select_cv_render_jobs,
)


def _positive_integer(value: str) -> int:
    """Convert one command-line value to an integer greater than zero."""

    try:
        parsed_value = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"Expected an integer, received {value!r}."
        ) from error

    if parsed_value < 1:
        raise argparse.ArgumentTypeError("Value must be at least 1.")

    return parsed_value


def build_parser() -> argparse.ArgumentParser:
    """Create the reusable argument parser for the CV rendering command."""

    parser = argparse.ArgumentParser(
        description=(
            "Plan or render deterministic HTML and PDF CV artifacts from "
            "the validated candidate profile collection."
        )
    )

    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--candidate-id",
        help="Select one exact candidate, for example candidate_003.",
    )
    selection.add_argument(
        "--count",
        type=_positive_integer,
        help="Select the first N profiles from the chosen starting point.",
    )
    selection.add_argument(
        "--all",
        action="store_true",
        dest="select_all",
        help="Select every validated candidate profile.",
    )

    parser.add_argument(
        "--start-from",
        help=(
            "Start --count or --all selection from this candidate ID. "
            "It cannot be combined with --candidate-id."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Inspect source profiles and planned paths without writing "
            "HTML or PDF files."
        ),
    )
    parser.add_argument(
        "--keep-html",
        action="store_true",
        help=(
            "Save the standalone HTML preview beside the generated PDF. "
            "Use this while tuning the template in a browser."
        ),
    )
    parser.add_argument(
        "--require-portraits",
        action="store_true",
        help=(
            "Fail before rendering when any selected candidate lacks a real "
            "normalized portrait. Use this for the final PDF dataset."
        ),
    )

    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
) -> int:
    """Load profiles, select jobs, then plan or render their CV artifacts."""

    parser = build_parser()
    arguments = parser.parse_args(argv)
    active_settings = settings or get_settings()

    if arguments.dry_run and arguments.keep_html:
        print(
            "ERROR: --keep-html writes an artifact and cannot be combined "
            "with --dry-run.",
            file=sys.stderr,
        )
        return 2

    try:
        profiles = load_candidate_profiles(
            active_settings.candidate_profiles_output_path
        )
        all_jobs = build_cv_render_jobs(
            profiles,
            images_directory=(
                active_settings.candidate_images_directory
            ),
            pdf_directory=active_settings.cv_pdfs_output_directory,
            html_preview_directory=(
                active_settings.cv_html_preview_directory
            ),
        )
        selected_jobs = select_cv_render_jobs(
            all_jobs,
            candidate_id=arguments.candidate_id,
            count=arguments.count,
            start_from=arguments.start_from,
            select_all=arguments.select_all,
        )
        shortest_job, densest_job = find_profile_boundaries(all_jobs)

        if arguments.dry_run:
            _print_rendering_plan(
                settings=active_settings,
                all_jobs=all_jobs,
                selected_jobs=selected_jobs,
                shortest_job=shortest_job,
                densest_job=densest_job,
            )
            return 0

        results = render_cv_jobs(
            selected_jobs,
            keep_html=arguments.keep_html,
            require_portraits=arguments.require_portraits,
        )
    except (
        CandidateProfilesFileError,
        CvRenderingError,
        CvRenderingPlanError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    _print_rendering_summary(
        settings=active_settings,
        results=results,
    )
    return 0


def _print_rendering_plan(
    *,
    settings: Settings,
    all_jobs: Sequence[CvRenderJob],
    selected_jobs: Sequence[CvRenderJob],
    shortest_job: CvRenderJob,
    densest_job: CvRenderJob,
) -> None:
    """Print concise paths, boundary cases, and portrait readiness."""

    portrait_count = sum(job.portrait_exists for job in all_jobs)

    print("CV RENDERING DRY RUN")
    print(f"  Profiles path: {settings.candidate_profiles_output_path}")
    print(f"  Profiles available: {len(all_jobs)}")
    print(f"  Candidate images: {settings.candidate_images_directory}")
    print(f"  PDF output: {settings.cv_pdfs_output_directory}")
    print(f"  HTML previews: {settings.cv_html_preview_directory}")
    print(f"  Portraits available: {portrait_count}/{len(all_jobs)}")
    print(f"  Selected jobs: {len(selected_jobs)}")
    print(
        "  Shortest profile: "
        f"{shortest_job.candidate_id} | "
        f"{shortest_job.profile.full_name} | "
        f"{shortest_job.metrics.total_text_characters} text characters"
    )
    print(
        "  Densest profile: "
        f"{densest_job.candidate_id} | "
        f"{densest_job.profile.full_name} | "
        f"{densest_job.metrics.total_text_characters} text characters"
    )

    print("\nPLANNED ARTIFACTS")
    for job in selected_jobs:
        portrait_status = "ready" if job.portrait_exists else "placeholder"
        print(
            f"  {job.candidate_id} | {job.profile.full_name} | "
            f"portrait={portrait_status} | pdf={job.pdf_path.name}"
        )

    print("\n  Result: READY TO RENDER")


def _print_rendering_summary(
    *,
    settings: Settings,
    results: Sequence[CvRenderResult],
) -> None:
    """Print the verified output details from one rendering operation."""

    placeholder_count = sum(
        result.used_placeholder_portrait
        for result in results
    )

    print("CV RENDERING COMPLETE")
    print(f"  PDF output: {settings.cv_pdfs_output_directory}")
    print(f"  Rendered CVs: {len(results)}")
    print(f"  Placeholder portraits: {placeholder_count}/{len(results)}")

    print("\nRENDERED ARTIFACTS")
    for result in results:
        html_status = (
            result.html_preview_path.name
            if result.html_preview_path is not None
            else "not saved"
        )
        portrait_status = (
            "placeholder"
            if result.used_placeholder_portrait
            else "portrait"
        )
        print(
            f"  {result.candidate_id} | pages={result.page_count} | "
            f"text={result.extracted_text_characters} chars | "
            f"portrait={portrait_status} | "
            f"pdf={result.pdf_path.name} | html={html_status}"
        )

    print("\n  Result: PASS")


def main() -> None:
    """Execute the command and expose its return status to the shell."""

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
