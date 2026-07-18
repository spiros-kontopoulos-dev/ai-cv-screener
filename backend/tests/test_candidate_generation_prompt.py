"""Tests for focused candidate-specific prompt construction."""

from pathlib import Path

from app.candidate_generation import (
    build_candidate_prompt,
    load_candidate_dataset_plan,
)


PLAN_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "dataset"
    / "candidate_dataset_plan.json"
)


def test_prompt_contains_only_the_selected_slot_requirements() -> None:
    """The prompt should focus on one candidate rather than all 30 slots."""

    plan = load_candidate_dataset_plan(PLAN_PATH)

    prompt = build_candidate_prompt(plan.candidates[0])

    assert '"candidate_id": "candidate_001"' in prompt
    assert '"full_name": "Eleni Markou"' in prompt
    assert '"leadership_team_size": 5' in prompt
    assert "candidate_002" not in prompt
    assert "Jonas Keller" not in prompt


def test_retry_prompt_includes_actionable_compliance_feedback() -> None:
    """A retry should receive every deterministic problem from the validator."""

    plan = load_candidate_dataset_plan(PLAN_PATH)

    prompt = build_candidate_prompt(
        plan.candidates[0],
        correction_feedback=[
            "city must be 'Athens'; received 'Patras'.",
            "Required skill 'FastAPI' is missing from skills.",
        ],
    )

    assert "A previous attempt failed" in prompt
    assert "city must be 'Athens'" in prompt
    assert "Required skill 'FastAPI'" in prompt
    assert "Return a complete corrected CandidateProfile" in prompt
