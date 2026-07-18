"""Generate controlled fictional candidate profiles from the dataset plan.

Examples:

    # Inspect three slots without making network requests.
    python -m app.scripts.generate_candidate_profiles --count 3 --dry-run

    # Generate one validated candidate and print its full JSON.
    python -m app.scripts.generate_candidate_profiles \
        --candidate-id candidate_001 --print-json

WP3 Patch 02 validates and displays generated profiles but deliberately does
not persist them yet. Safe JSON persistence and resume behavior belong to the
next cohesive patch.
"""

import argparse
import sys
from collections.abc import Callable, Sequence

from app.candidate_generation import (
    CandidateGenerationFailed,
    CandidateGenerationSlot,
    CandidatePlanError,
    CandidateProfileProvider,
    CandidateSelectionError,
    OpenAICandidateGenerator,
    generate_candidate_with_retries,
    load_candidate_dataset_plan,
    select_candidate_slots,
)
from app.core.config import Settings, get_settings


ProviderFactory = Callable[[Settings], CandidateProfileProvider]


def _positive_integer(value: str) -> int:
    """Convert one CLI value to an integer greater than zero."""

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
    """Create the reusable argument parser for candidate generation."""

    parser = argparse.ArgumentParser(
        description=(
            "Select controlled candidate slots and generate fictional "
            "profiles from the committed dataset plan."
        )
    )

    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--candidate-id",
        help="Select one exact slot, for example candidate_001.",
    )
    selection.add_argument(
        "--count",
        type=_positive_integer,
        help="Select the first N slots from the chosen starting point.",
    )
    selection.add_argument(
        "--all",
        action="store_true",
        dest="select_all",
        help="Select every remaining slot in the controlled plan.",
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
        help="Load, validate, and display slots without calling OpenAI.",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Print each accepted CandidateProfile as formatted JSON.",
    )

    return parser


def create_openai_provider(settings: Settings) -> OpenAICandidateGenerator:
    """Create the direct OpenAI provider from validated application settings."""

    api_key = _read_openai_api_key(settings)

    return OpenAICandidateGenerator(
        api_key=api_key,
        model=settings.candidate_generation_model,
        timeout_seconds=settings.candidate_generation_timeout_seconds,
        max_completion_tokens=(
            settings.candidate_generation_max_completion_tokens
        ),
    )


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    provider_factory: ProviderFactory = create_openai_provider,
) -> int:
    """Run dry-run inspection or real bounded candidate generation."""

    parser = build_parser()
    arguments = parser.parse_args(argv)
    active_settings = settings or get_settings()

    try:
        plan = load_candidate_dataset_plan(
            active_settings.candidate_dataset_plan_path
        )
        selected_slots = select_candidate_slots(
            plan,
            candidate_id=arguments.candidate_id,
            count=arguments.count,
            start_from=arguments.start_from,
            select_all=arguments.select_all,
        )
    except (CandidatePlanError, CandidateSelectionError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    if arguments.dry_run:
        _print_dry_run(
            active_settings,
            plan.dataset_version,
            plan.candidate_count,
            selected_slots,
        )
        return 0

    try:
        provider = provider_factory(active_settings)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    print("CANDIDATE GENERATION")
    print(f"  Model: {active_settings.candidate_generation_model}")
    print(f"  Selected slots: {len(selected_slots)}")
    print(
        "  Maximum attempts per candidate: "
        f"{active_settings.candidate_generation_max_retries + 1}"
    )

    successful = 0
    failed = 0
    total_attempts = 0

    for slot in selected_slots:
        print(f"\nGenerating {slot.candidate_id} | {slot.full_name} ...")

        try:
            result = generate_candidate_with_retries(
                slot,
                provider=provider,
                max_retries=(
                    active_settings.candidate_generation_max_retries
                ),
            )
        except CandidateGenerationFailed as error:
            failed += 1
            total_attempts += error.attempts
            print(f"  FAILED: {error}", file=sys.stderr)
            continue

        successful += 1
        total_attempts += result.attempts
        print(
            f"  ACCEPTED after {result.attempts} attempt(s): "
            f"{result.profile.professional_title}"
        )

        if arguments.print_json:
            print(result.profile.model_dump_json(indent=2))

    print("\nGENERATION SUMMARY")
    print(f"  Requested: {len(selected_slots)}")
    print(f"  Accepted: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Provider attempts: {total_attempts}")
    print("  Profiles persisted: 0 (added in WP3 Patch 03)")

    return 0 if failed == 0 else 1


def _read_openai_api_key(settings: Settings) -> str:
    """Return the configured API key or raise an actionable CLI error."""

    if settings.openai_api_key is None:
        raise ValueError(
            "OPENAI_API_KEY is required for real candidate generation."
        )

    api_key = settings.openai_api_key.get_secret_value().strip()
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is required for real candidate generation."
        )

    return api_key


def _print_dry_run(
    settings: Settings,
    plan_version: int,
    available_slot_count: int,
    selected_slots: Sequence[CandidateGenerationSlot],
) -> None:
    """Display deterministic selection details without provider activity."""

    print("CANDIDATE GENERATION DRY RUN")
    print(f"  Plan version: {plan_version}")
    print(f"  Plan path: {settings.candidate_dataset_plan_path}")
    print(f"  Available slots: {available_slot_count}")
    print(f"  Selected slots: {len(selected_slots)}")
    print(f"  Future model: {settings.candidate_generation_model}")
    print(
        "  Maximum attempts per candidate: "
        f"{settings.candidate_generation_max_retries + 1}"
    )

    for position, slot in enumerate(selected_slots, start=1):
        print(
            f"  {position}. {slot.candidate_id} | {slot.full_name} | "
            f"{slot.seniority.value} {slot.profession.value} | "
            f"{slot.city}, {slot.country}"
        )

    print("  OpenAI requests made: 0")


def main() -> None:
    """Execute the CLI and expose its status code to the shell."""

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
