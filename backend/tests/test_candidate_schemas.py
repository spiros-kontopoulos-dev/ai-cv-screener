"""Automated tests for candidate-profile Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.schemas import (
    CandidateProfile,
    ContactDetails,
    Education,
    Project,
    WorkExperience,
)


def test_valid_candidate_profile_is_created(
    valid_candidate_payload: dict,
) -> None:
    """A complete valid payload should become a nested candidate model."""

    candidate = CandidateProfile(**valid_candidate_payload)

    assert candidate.candidate_id == "candidate_001"
    assert candidate.contact.city == "Athens"

    # The input contained dictionaries, but Pydantic converted them into
    # typed nested models that support attribute access.
    assert isinstance(candidate.contact, ContactDetails)
    assert isinstance(candidate.work_experience[0], WorkExperience)
    assert isinstance(candidate.education[0], Education)


def test_candidate_strings_are_stripped(
    valid_candidate_payload: dict,
) -> None:
    """Shared schema configuration should remove surrounding whitespace."""

    valid_candidate_payload["full_name"] = "  Alex Morgan  "
    valid_candidate_payload["contact"]["city"] = "  Athens  "

    candidate = CandidateProfile(**valid_candidate_payload)

    assert candidate.full_name == "Alex Morgan"
    assert candidate.contact.city == "Athens"


def test_unknown_contact_field_is_rejected() -> None:
    """Unexpected data should not silently enter the candidate contract."""

    with pytest.raises(ValidationError) as error:
        ContactDetails(
            email="alex@example.com",
            phone="+30 690 000 0000",
            city="Athens",
            country="Greece",
            linkedin_url="https://example.com/alex",
        )

    # Checking the structured error type is more robust than matching the
    # entire human-readable error message.
    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_invalid_email_is_rejected() -> None:
    """ContactDetails should reject values without a valid email structure."""

    with pytest.raises(ValidationError) as error:
        ContactDetails(
            email="not-an-email",
            phone="+30 690 000 0000",
            city="Athens",
            country="Greece",
        )

    assert error.value.errors()[0]["loc"] == ("email",)


def test_invalid_candidate_id_is_rejected(
    valid_candidate_payload: dict,
) -> None:
    """Candidate identifiers must follow the candidate_001 format."""

    valid_candidate_payload["candidate_id"] = "alex-1"

    with pytest.raises(ValidationError) as error:
        CandidateProfile(**valid_candidate_payload)

    assert error.value.errors()[0]["loc"] == ("candidate_id",)


def test_work_experience_cannot_end_before_it_starts() -> None:
    """Employment date ranges must follow chronological order."""

    with pytest.raises(
        ValidationError,
        match="Work experience end_date must be",
    ):
        WorkExperience(
            job_title="Backend Engineer",
            company="Northstar Systems",
            start_date="2025-06",
            end_date="2022-03",
            highlights=["Built reliable Python APIs."],
        )


def test_education_cannot_end_before_it_starts() -> None:
    """Education date ranges must follow chronological order."""

    with pytest.raises(
        ValidationError,
        match="Education end_year must be",
    ):
        Education(
            degree="BSc",
            field_of_study="Computer Science",
            institution="Westbridge University",
            start_year=2020,
            end_year=2018,
        )


def test_candidate_requires_at_least_three_skills(
    valid_candidate_payload: dict,
) -> None:
    """A candidate with too few skills would be weak for retrieval."""

    valid_candidate_payload["skills"] = [
        {
            "name": "Python",
            "category": "programming_language",
        },
        {
            "name": "FastAPI",
            "category": "framework",
        },
    ]

    with pytest.raises(ValidationError) as error:
        CandidateProfile(**valid_candidate_payload)

    assert error.value.errors()[0]["loc"] == ("skills",)


def test_duplicate_candidate_skills_are_rejected(
    valid_candidate_payload: dict,
) -> None:
    """Skill names should be unique regardless of capitalization."""

    valid_candidate_payload["skills"][1]["name"] = "python"

    with pytest.raises(
        ValidationError,
        match="Candidate skills must not contain duplicate names",
    ):
        CandidateProfile(**valid_candidate_payload)


def test_duplicate_candidate_languages_are_rejected(
    valid_candidate_payload: dict,
) -> None:
    """Language names should be unique regardless of capitalization."""

    valid_candidate_payload["languages"].append(
        {
            "name": "english",
            "proficiency": "professional",
        }
    )

    with pytest.raises(
        ValidationError,
        match="Candidate languages must not contain duplicate names",
    ):
        CandidateProfile(**valid_candidate_payload)


def test_duplicate_work_technologies_are_rejected() -> None:
    """One employment entry should not repeat the same technology."""

    with pytest.raises(
        ValidationError,
        match="Work experience technologies must not contain duplicate",
    ):
        WorkExperience(
            job_title="Backend Engineer",
            company="Northstar Systems",
            start_date="2022-01",
            end_date="2025-01",
            highlights=["Built reliable Python APIs."],
            technologies=[
                "Python",
                "FastAPI",
                "python",
            ],
        )


def test_duplicate_project_technologies_are_rejected() -> None:
    """One project should not repeat the same technology."""

    with pytest.raises(
        ValidationError,
        match="Project technologies must not contain duplicate",
    ):
        Project(
            name="Candidate Matching API",
            description=(
                "Built a candidate-ranking API using structured fictional "
                "profiles and deterministic matching rules."
            ),
            technologies=[
                "Python",
                "FastAPI",
                "PYTHON",
            ],
            year=2025,
        )