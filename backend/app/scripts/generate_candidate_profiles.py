"""Preview controlled candidate slots before connecting OpenAI generation.

Example:

    python -m app.scripts.generate_candidate_profiles --count 3 --dry-run

WP3 Patch 01 deliberately performs no network requests. The same CLI will be
extended in the next patch so removing ``--dry-run`` starts real generation.
"""

import argparse
import sys
from collections.abc import Sequence

from app.candidate_generation import (
    CandidatePlanError,
    CandidateSelectionError,
    load_candidate_dataset_plan,
    select_candidate_slots,
)
from app.core.config import Settings, get_settings


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
        help="Preview one exact slot, for example candidate_001.",
    )
    selection.add_argument(
        "--count",
        type=_positive_integer,
        help="Preview the first N slots from the selected starting point.",
    )
    selection.add_argument(
        "--all",
        action="store_true",
        dest="select_all",
        help="Preview every remaining slot in the controlled plan.",
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

    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
) -> int:
    """Run the preview command and return a process-style status code.

    Accepting ``argv`` and ``settings`` makes deterministic CLI tests possible
    without patching global process state or reading a developer's real .env.
    """

    parser = build_parser()
    arguments = parser.parse_args(argv)

    if not arguments.dry_run:
        print(
            "Candidate generation is not connected in WP3 Patch 01. "
            "Run the command with --dry-run.",
            file=sys.stderr,
        )
        return 2

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

    print("CANDIDATE GENERATION DRY RUN")
    print(f"  Plan version: {plan.dataset_version}")
    print(f"  Plan path: {active_settings.candidate_dataset_plan_path}")
    print(f"  Available slots: {plan.candidate_count}")
    print(f"  Selected slots: {len(selected_slots)}")
    print(
        "  Retry limit for future generation: "
        f"{active_settings.candidate_generation_max_retries}"
    )

    for position, slot in enumerate(selected_slots, start=1):
        print(
            f"  {position}. {slot.candidate_id} | {slot.full_name} | "
            f"{slot.seniority.value} {slot.profession.value} | "
            f"{slot.city}, {slot.country}"
        )

    print("  OpenAI requests made: 0")
    return 0


def main() -> None:
    """Execute the CLI and expose its status code to the shell."""

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
