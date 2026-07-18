"""Tests for typed loading and selection of candidate-generation slots."""

import json
from pathlib import Path

import pytest

from app.candidate_generation import (
    CandidatePlanError,
    CandidateSelectionError,
    load_candidate_dataset_plan,
    select_candidate_slots,
)
from app.schemas import ProfessionCategory, SeniorityLevel


PLAN_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "dataset"
    / "candidate_dataset_plan.json"
)


def test_plan_loader_returns_typed_candidate_slots() -> None:
    """The committed JSON should become a validated domain model."""

    plan = load_candidate_dataset_plan(PLAN_PATH)
    first_slot = plan.candidates[0]

    assert plan.candidate_count == 30
    assert first_slot.candidate_id == "candidate_001"
    assert first_slot.profession == ProfessionCategory.BACKEND_ENGINEERING
    assert first_slot.seniority == SeniorityLevel.SENIOR
    assert first_slot.required_skills[:3] == [
        "Python",
        "FastAPI",
        "PostgreSQL",
    ]


def test_plan_loader_rejects_invalid_json(tmp_path: Path) -> None:
    """A malformed plan should fail with a focused domain error."""

    invalid_plan_path = tmp_path / "invalid-plan.json"
    invalid_plan_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(
        CandidatePlanError,
        match="contains invalid JSON",
    ):
        load_candidate_dataset_plan(invalid_plan_path)


def test_plan_loader_rejects_inconsistent_candidate_count(
    tmp_path: Path,
) -> None:
    """Top-level counts must agree with the actual candidate slot list."""

    raw_plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    raw_plan["candidate_count"] = 29

    invalid_plan_path = tmp_path / "wrong-count.json"
    invalid_plan_path.write_text(
        json.dumps(raw_plan),
        encoding="utf-8",
    )

    with pytest.raises(
        CandidatePlanError,
        match="candidate_count must match",
    ):
        load_candidate_dataset_plan(invalid_plan_path)


def test_select_one_candidate_by_id() -> None:
    """A precise candidate ID should return exactly its plan slot."""

    plan = load_candidate_dataset_plan(PLAN_PATH)

    selected_slots = select_candidate_slots(
        plan,
        candidate_id="candidate_009",
    )

    assert [slot.candidate_id for slot in selected_slots] == [
        "candidate_009"
    ]


def test_select_count_from_later_starting_point() -> None:
    """Count selection should preserve plan order from start_from."""

    plan = load_candidate_dataset_plan(PLAN_PATH)

    selected_slots = select_candidate_slots(
        plan,
        count=3,
        start_from="candidate_010",
    )

    assert [slot.candidate_id for slot in selected_slots] == [
        "candidate_010",
        "candidate_011",
        "candidate_012",
    ]


def test_selection_rejects_unknown_candidate_id() -> None:
    """Selection mistakes should fail before any future API request."""

    plan = load_candidate_dataset_plan(PLAN_PATH)

    with pytest.raises(
        CandidateSelectionError,
        match="Unknown candidate ID",
    ):
        select_candidate_slots(
            plan,
            candidate_id="candidate_999",
        )
