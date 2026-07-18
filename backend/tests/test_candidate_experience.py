"""Tests for deterministic experience calculation and normalization."""

from pathlib import Path

import pytest

from app.candidate_generation import (
    CandidateExperienceNormalizationError,
    calculate_employment_years,
    load_candidate_dataset_plan,
    normalize_profile_experience,
)
from app.schemas import CandidateProfile


PLAN_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "dataset"
    / "candidate_dataset_plan.json"
)


def test_unlocked_experience_is_derived_from_work_dates(
    valid_candidate_002_payload: dict,
) -> None:
    """The LLM's provisional total must not override deterministic arithmetic."""

    plan = load_candidate_dataset_plan(PLAN_PATH)
    slot = plan.candidates[1]
    profile = CandidateProfile.model_validate(valid_candidate_002_payload)

    normalized = normalize_profile_experience(profile, slot)

    assert calculate_employment_years(profile) == 7.7
    assert normalized.years_of_experience == 7.7


def test_normalization_caps_skill_years_at_derived_total(
    valid_candidate_002_payload: dict,
) -> None:
    """A skill duration cannot remain longer than the normalized career."""

    valid_candidate_002_payload["years_of_experience"] = 9
    valid_candidate_002_payload["skills"][0]["years_of_experience"] = 9
    valid_candidate_002_payload["work_experience"][0][
        "start_date"
    ] = "2020-07"

    plan = load_candidate_dataset_plan(PLAN_PATH)
    profile = CandidateProfile.model_validate(valid_candidate_002_payload)
    normalized = normalize_profile_experience(profile, plan.candidates[1])

    assert normalized.years_of_experience == 6.1
    assert normalized.skills[0].years_of_experience == 6.1


def test_locked_experience_is_not_overwritten(
    valid_candidate_001_payload: dict,
) -> None:
    """A controlled known fact remains authoritative over derived arithmetic."""

    valid_candidate_001_payload["work_experience"][-1][
        "start_date"
    ] = "2016-07"
    profile = CandidateProfile.model_validate(valid_candidate_001_payload)
    slot = load_candidate_dataset_plan(PLAN_PATH).candidates[0]

    normalized = normalize_profile_experience(profile, slot)

    assert normalized.years_of_experience == 8


def test_normalization_rejects_timeline_outside_locked_seniority(
    valid_candidate_002_payload: dict,
) -> None:
    """Python should ask for new dates when a timeline contradicts seniority."""

    valid_candidate_002_payload["years_of_experience"] = 9
    valid_candidate_002_payload["work_experience"][0][
        "start_date"
    ] = "2014-01"
    profile = CandidateProfile.model_validate(valid_candidate_002_payload)
    slot = load_candidate_dataset_plan(PLAN_PATH).candidates[1]

    with pytest.raises(
        CandidateExperienceNormalizationError,
        match="locked mid seniority requires between 2 and 10 years",
    ):
        normalize_profile_experience(profile, slot)
