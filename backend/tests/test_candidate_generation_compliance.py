"""Tests for deterministic generated-profile versus slot validation."""

from pathlib import Path

from app.candidate_generation import (
    load_candidate_dataset_plan,
    validate_profile_against_slot,
)
from app.schemas import CandidateProfile


PLAN_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "dataset"
    / "candidate_dataset_plan.json"
)


def _candidate_001_slot():
    """Load the first controlled slot used by the focused tests."""

    return load_candidate_dataset_plan(PLAN_PATH).candidates[0]


def test_matching_profile_satisfies_its_controlled_slot(
    valid_candidate_001_payload: dict,
) -> None:
    """A profile containing every locked value should be accepted."""

    profile = CandidateProfile.model_validate(valid_candidate_001_payload)

    problems = validate_profile_against_slot(
        profile,
        _candidate_001_slot(),
    )

    assert problems == []


def test_compliance_reports_multiple_problems_in_one_pass(
    valid_candidate_001_payload: dict,
) -> None:
    """Complete retry feedback should reduce unnecessary API attempts."""

    valid_candidate_001_payload["contact"]["city"] = "Patras"
    valid_candidate_001_payload["skills"] = [
        skill
        for skill in valid_candidate_001_payload["skills"]
        if skill["name"] != "FastAPI"
    ]
    valid_candidate_001_payload["work_experience"][0][
        "managed_team_size"
    ] = 4

    profile = CandidateProfile.model_validate(valid_candidate_001_payload)

    problems = validate_profile_against_slot(
        profile,
        _candidate_001_slot(),
    )

    assert any("city must be 'Athens'" in problem for problem in problems)
    assert any("Required skill 'FastAPI'" in problem for problem in problems)
    assert any("managed_team_size=5" in problem for problem in problems)


def test_compliance_rejects_unplanned_certifications_and_projects(
    valid_candidate_001_payload: dict,
) -> None:
    """Optional sections must not silently change controlled distributions."""

    valid_candidate_001_payload["certifications"] = [
        {
            "name": "Extra Certificate",
            "issuer": "Example Institute",
            "year": 2024,
        }
    ]
    valid_candidate_001_payload["projects"] = [
        {
            "name": "Extra Project",
            "description": (
                "A substantial additional project that was not required by "
                "the controlled candidate slot."
            ),
            "technologies": ["Python"],
            "year": 2025,
        }
    ]

    profile = CandidateProfile.model_validate(valid_candidate_001_payload)

    problems = validate_profile_against_slot(
        profile,
        _candidate_001_slot(),
    )

    assert any("certifications must be empty" in item for item in problems)
    assert any("projects must be empty" in item for item in problems)


def test_compliance_rejects_future_and_unsorted_work_history(
    valid_candidate_001_payload: dict,
) -> None:
    """Generated timelines should be newest-first and never enter the future."""

    valid_candidate_001_payload["work_experience"] = [
        {
            "job_title": "Backend Engineer",
            "company": "Earlier Systems",
            "location": "Athens, Greece",
            "start_date": "2020-01",
            "end_date": "2022-12",
            "highlights": [
                "Built Python and PostgreSQL services for internal teams."
            ],
            "technologies": ["Python", "PostgreSQL"],
            "managed_team_size": None,
        },
        {
            "job_title": "Senior Backend Engineer",
            "company": "Future Systems",
            "location": "Athens, Greece",
            "start_date": "2027-01",
            "end_date": None,
            "highlights": [
                "Built FastAPI services with Docker and AWS deployment."
            ],
            "technologies": ["FastAPI", "Docker", "AWS"],
            "managed_team_size": 5,
        },
    ]

    profile = CandidateProfile.model_validate(valid_candidate_001_payload)

    problems = validate_profile_against_slot(
        profile,
        _candidate_001_slot(),
    )

    assert "work_experience must be ordered newest first." in problems
    assert any("later than 2026-07" in item for item in problems)


def test_compliance_rejects_declared_experience_that_conflicts_with_history(
    valid_candidate_001_payload: dict,
) -> None:
    """A visible ten-year career must not be accepted as eight years."""

    valid_candidate_001_payload["work_experience"][-1][
        "start_date"
    ] = "2016-07"

    profile = CandidateProfile.model_validate(valid_candidate_001_payload)

    problems = validate_profile_against_slot(
        profile,
        _candidate_001_slot(),
    )

    assert any(
        "inconsistent with the visible work history" in problem
        for problem in problems
    )


def test_compliance_does_not_double_count_overlapping_roles(
    valid_candidate_001_payload: dict,
) -> None:
    """Parallel roles should be merged when calculating career duration."""

    valid_candidate_001_payload["work_experience"].append(
        {
            "job_title": "Part-time Technical Advisor",
            "company": "Harborline Software",
            "location": "Remote",
            "start_date": "2020-01",
            "end_date": "2022-12",
            "highlights": [
                "Advised a small team on Python service architecture."
            ],
            "technologies": ["Python"],
            "managed_team_size": None,
        }
    )

    # Keep the work entries newest-first after adding the overlapping role.
    valid_candidate_001_payload["work_experience"].sort(
        key=lambda role: role["start_date"],
        reverse=True,
    )
    profile = CandidateProfile.model_validate(valid_candidate_001_payload)

    problems = validate_profile_against_slot(
        profile,
        _candidate_001_slot(),
    )

    assert not any(
        "inconsistent with the visible work history" in problem
        for problem in problems
    )
