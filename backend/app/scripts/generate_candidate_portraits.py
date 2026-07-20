"""Generate and normalize fictional AI portraits for validated candidates.

Examples:

    python -m app.scripts.generate_candidate_portraits \
        --candidate-id candidate_003 --dry-run --show-prompts

    python -m app.scripts.generate_candidate_portraits \
        --candidate-id candidate_003

    python -m app.scripts.generate_candidate_portraits --all

Existing valid portraits are skipped by default so interrupted batches can be
resumed safely. Use ``--overwrite`` only when a selected portrait should be
replaced after visual review.
"""

import argparse
import sys
from collections.abc import Callable, Sequence

from app.candidate_generation.persistence import (
    CandidateProfilesFileError,
    load_candidate_profiles,
)
from app.core.config import Settings, get_settings
from app.portrait_generation import (
    OpenAIPortraitGenerator,
    PortraitCoveragePlanError,
    PortraitGenerationFailed,
    PortraitGenerationJob,
    PortraitGenerationPlanError,
    PortraitImageError,
    PortraitImageProvider,
    build_portrait_generation_jobs,
    load_portrait_coverage_plan,
    generate_portrait_with_retries,
    inspect_portrait_image,
    select_portrait_generation_jobs,
    validate_portrait_coverage_against_profiles,
)


ProviderFactory = Callable[[Settings], PortraitImageProvider]


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
    """Create the reusable parser for portrait generation."""

    parser = argparse.ArgumentParser(
        description=(
            "Generate fictional professional portraits and normalize them "
            "to deterministic WebP assets for CV rendering."
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
        help="Select every candidate in the committed portrait plan.",
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
        help="Inspect prompts and output paths without calling OpenAI.",
    )
    parser.add_argument(
        "--show-prompts",
        action="store_true",
        help="Print the complete deterministic prompt for each selection.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Regenerate selected portraits even when a valid WebP file "
            "already exists."
        ),
    )

    return parser


def create_openai_provider(settings: Settings) -> OpenAIPortraitGenerator:
    """Create the direct OpenAI image provider from application settings."""

    return OpenAIPortraitGenerator(
        api_key=_read_openai_api_key(settings),
        model=settings.portrait_generation_model,
        size=settings.portrait_generation_size,
        quality=settings.portrait_generation_quality,
        output_compression=(
            settings.portrait_generation_output_compression
        ),
        timeout_seconds=settings.portrait_generation_timeout_seconds,
    )


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    provider_factory: ProviderFactory = create_openai_provider,
) -> int:
    """Run prompt inspection or persisted portrait generation."""

    parser = build_parser()
    arguments = parser.parse_args(argv)
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
        all_jobs = build_portrait_generation_jobs(
            profiles,
            images_directory=active_settings.candidate_images_directory,
            portrait_candidate_ids=(
                coverage_plan.portrait_candidate_id_set
            ),
            appearance_by_candidate_id=(
                coverage_plan.appearance_by_candidate_id
            ),
        )
        selected_jobs = select_portrait_generation_jobs(
            all_jobs,
            candidate_id=arguments.candidate_id,
            count=arguments.count,
            start_from=arguments.start_from,
            select_all=arguments.select_all,
        )
    except (
        CandidateProfilesFileError,
        PortraitCoveragePlanError,
        PortraitGenerationPlanError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    if arguments.dry_run:
        _print_dry_run(
            settings=active_settings,
            profile_count=len(profiles),
            all_jobs=all_jobs,
            selected_jobs=selected_jobs,
            show_prompts=arguments.show_prompts,
        )
        return 0

    try:
        jobs_to_generate, skipped_existing = _partition_existing_jobs(
            selected_jobs,
            settings=active_settings,
            overwrite=arguments.overwrite,
        )
    except PortraitImageError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    if jobs_to_generate:
        try:
            provider = provider_factory(active_settings)
        except ValueError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2
    else:
        provider = None

    print("CANDIDATE PORTRAIT GENERATION")
    print(f"  Model: {active_settings.portrait_generation_model}")
    print(f"  Provider size: {active_settings.portrait_generation_size}")
    print(f"  Provider quality: {active_settings.portrait_generation_quality}")
    print(
        "  Normalized output: "
        f"{active_settings.portrait_normalized_size}x"
        f"{active_settings.portrait_normalized_size} WebP"
    )
    print(f"  Output directory: {active_settings.candidate_images_directory}")
    print(f"  Selected portraits: {len(selected_jobs)}")
    print(f"  Skipped existing: {skipped_existing}")
    print(
        "  Maximum attempts per portrait: "
        f"{active_settings.portrait_generation_max_retries + 1}"
    )

    successful = 0
    failed = 0
    total_attempts = 0

    for job in jobs_to_generate:
        print(f"\nGenerating {job.candidate_id} | {job.profile.full_name} ...")
        if arguments.show_prompts:
            print(f"  Prompt: {job.prompt}")

        try:
            assert provider is not None
            result = generate_portrait_with_retries(
                job,
                provider=provider,
                max_retries=active_settings.portrait_generation_max_retries,
                normalized_size=active_settings.portrait_normalized_size,
                webp_quality=active_settings.portrait_webp_quality,
            )
        except PortraitGenerationFailed as error:
            failed += 1
            total_attempts += error.attempts
            print(f"  FAILED: {error}", file=sys.stderr)
            continue

        successful += 1
        total_attempts += result.attempts
        print(
            f"  SAVED after {result.attempts} attempt(s): "
            f"{result.output_path.name} | "
            f"{result.metadata.width}x{result.metadata.height} | "
            f"{result.metadata.size_bytes} bytes"
        )

    print("\nPORTRAIT GENERATION SUMMARY")
    print(f"  Requested: {len(selected_jobs)}")
    print(f"  Skipped existing: {skipped_existing}")
    print(f"  Generated and saved: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Provider attempts: {total_attempts}")
    print(f"  Output directory: {active_settings.candidate_images_directory}")

    return 0 if failed == 0 else 1


def _partition_existing_jobs(
    jobs: Sequence[PortraitGenerationJob],
    *,
    settings: Settings,
    overwrite: bool,
) -> tuple[list[PortraitGenerationJob], int]:
    """Skip valid existing files or require overwrite for invalid files."""

    jobs_to_generate: list[PortraitGenerationJob] = []
    skipped_existing = 0

    for job in jobs:
        if not job.portrait_exists or overwrite:
            jobs_to_generate.append(job)
            continue

        try:
            inspect_portrait_image(
                job.output_path,
                expected_size=settings.portrait_normalized_size,
            )
        except PortraitImageError as error:
            raise PortraitImageError(
                f"Existing portrait is invalid; use --overwrite to replace "
                f"it: {job.output_path}. {error}"
            ) from error

        skipped_existing += 1

    return jobs_to_generate, skipped_existing


def _read_openai_api_key(settings: Settings) -> str:
    """Return the configured API key or raise an actionable CLI error."""

    if settings.openai_api_key is None:
        raise ValueError(
            "OPENAI_API_KEY is required for real portrait generation."
        )

    api_key = settings.openai_api_key.get_secret_value().strip()
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is required for real portrait generation."
        )

    return api_key


def _print_dry_run(
    *,
    settings: Settings,
    profile_count: int,
    all_jobs: Sequence[PortraitGenerationJob],
    selected_jobs: Sequence[PortraitGenerationJob],
    show_prompts: bool,
) -> None:
    """Display deterministic portrait requests without provider activity."""

    existing_count = sum(job.portrait_exists for job in all_jobs)

    print("CANDIDATE PORTRAIT GENERATION DRY RUN")
    print(f"  Profiles path: {settings.candidate_profiles_output_path}")
    print(f"  Profiles available: {profile_count}")
    print(f"  Planned portraits: {len(all_jobs)}")
    print(f"  Portraits available: {existing_count}/{len(all_jobs)}")
    print(f"  Selected portraits: {len(selected_jobs)}")
    print(f"  Future model: {settings.portrait_generation_model}")
    print(f"  Future provider size: {settings.portrait_generation_size}")
    print(f"  Future quality: {settings.portrait_generation_quality}")
    print(f"  Portrait plan: {settings.candidate_portrait_plan_path}")
    print(f"  Output directory: {settings.candidate_images_directory}")

    for position, job in enumerate(selected_jobs, start=1):
        status = "exists" if job.portrait_exists else "missing"
        print(
            f"  {position}. {job.candidate_id} | "
            f"{job.profile.full_name} | {status} | "
            f"{job.output_path.name}"
        )
        if show_prompts:
            print(f"     Prompt: {job.prompt}")

    print("  OpenAI requests made: 0")


def main() -> None:
    """Execute the CLI and expose its return status to the shell."""

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
