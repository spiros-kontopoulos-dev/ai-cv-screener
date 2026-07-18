"""Load and select controlled candidate-generation plan entries.

The dataset plan is deterministic input for the probabilistic LLM stage. This
module handles filesystem and selection behaviour, while ``models.py`` owns
the Pydantic contracts for the plan itself.
"""

from json import JSONDecodeError, loads
from pathlib import Path

from pydantic import ValidationError

from .models import CandidateDatasetPlan, CandidateGenerationSlot


class CandidatePlanError(RuntimeError):
    """Raised when the committed dataset plan cannot be loaded or validated."""


class CandidateSelectionError(ValueError):
    """Raised when CLI selection options do not identify valid plan slots."""


def load_candidate_dataset_plan(path: Path) -> CandidateDatasetPlan:
    """Read a JSON plan from disk and return its validated typed model."""

    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise CandidatePlanError(
            f"Candidate dataset plan was not found: {path}"
        ) from error
    except OSError as error:
        raise CandidatePlanError(
            f"Candidate dataset plan could not be read: {path}"
        ) from error

    try:
        raw_plan = loads(raw_text)
    except JSONDecodeError as error:
        raise CandidatePlanError(
            f"Candidate dataset plan contains invalid JSON: {path}"
        ) from error

    try:
        return CandidateDatasetPlan.model_validate(raw_plan)
    except ValidationError as error:
        raise CandidatePlanError(
            f"Candidate dataset plan failed validation: {path}\n{error}"
        ) from error


def select_candidate_slots(
    plan: CandidateDatasetPlan,
    *,
    candidate_id: str | None = None,
    count: int | None = None,
    start_from: str | None = None,
    select_all: bool = False,
) -> list[CandidateGenerationSlot]:
    """Select ordered slots for one future generation command.

    Exactly one selection mode is required. ``start_from`` may be combined
    with ``count`` or ``select_all`` to resume from a later plan position.
    """

    selected_modes = sum(
        value is not None
        for value in (candidate_id, count)
    ) + int(select_all)

    if selected_modes != 1:
        raise CandidateSelectionError(
            "Choose exactly one of candidate_id, count, or select_all."
        )

    if count is not None and count < 1:
        raise CandidateSelectionError("count must be at least 1.")

    slots_by_id = {slot.candidate_id: slot for slot in plan.candidates}

    if candidate_id is not None:
        if start_from is not None:
            raise CandidateSelectionError(
                "start_from cannot be combined with candidate_id."
            )

        try:
            return [slots_by_id[candidate_id]]
        except KeyError as error:
            raise CandidateSelectionError(
                f"Unknown candidate ID: {candidate_id}"
            ) from error

    start_index = 0
    if start_from is not None:
        try:
            start_index = next(
                index
                for index, slot in enumerate(plan.candidates)
                if slot.candidate_id == start_from
            )
        except StopIteration as error:
            raise CandidateSelectionError(
                f"Unknown start candidate ID: {start_from}"
            ) from error

    remaining_slots = plan.candidates[start_index:]

    if select_all:
        return list(remaining_slots)

    assert count is not None
    if count > len(remaining_slots):
        raise CandidateSelectionError(
            f"Requested {count} slots, but only {len(remaining_slots)} "
            "remain from the selected starting point."
        )

    return list(remaining_slots[:count])
