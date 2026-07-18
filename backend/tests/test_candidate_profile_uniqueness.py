"""Tests for lightweight cross-candidate duplicate detection."""

from copy import deepcopy

import pytest

from app.candidate_generation import (
    CandidateUniquenessError,
    find_profile_uniqueness_problems,
    validate_profile_uniqueness,
)
from app.schemas import CandidateProfile


def _distinct_profile_payload(valid_candidate_payload: dict) -> dict:
    """Return a second structurally valid but clearly different profile."""

    payload = deepcopy(valid_candidate_payload)
    payload.update(
        {
            "candidate_id": "candidate_002",
            "full_name": "Jamie Rivera",
            "summary": (
                "Experienced platform engineer delivering dependable cloud "
                "services, infrastructure automation, observability, and "
                "secure release workflows for distributed product teams."
            ),
        }
    )
    payload["contact"]["email"] = "jamie.rivera@example.com"
    payload["work_experience"][0].update(
        {
            "job_title": "Platform Engineer",
            "company": "Silverline Cloud Works",
        }
    )
    return payload


def test_uniqueness_accepts_a_distinct_candidate(
    valid_candidate_payload: dict,
) -> None:
    """Different identity, summary, and history should pass."""

    existing = CandidateProfile.model_validate(valid_candidate_payload)
    candidate = CandidateProfile.model_validate(
        _distinct_profile_payload(valid_candidate_payload)
    )

    validate_profile_uniqueness(candidate, [existing])


def test_uniqueness_collects_identity_and_content_duplicates(
    valid_candidate_payload: dict,
) -> None:
    """One retry should receive every exact duplication problem together."""

    existing = CandidateProfile.model_validate(valid_candidate_payload)
    duplicate_payload = _distinct_profile_payload(valid_candidate_payload)
    duplicate_payload["full_name"] = existing.full_name.upper()
    duplicate_payload["contact"]["email"] = existing.contact.email
    duplicate_payload["summary"] = existing.summary
    duplicate_payload["work_experience"] = [
        role.model_dump(mode="json")
        for role in existing.work_experience
    ]
    duplicate = CandidateProfile.model_validate(duplicate_payload)

    problems = find_profile_uniqueness_problems(duplicate, [existing])

    assert any("full_name duplicates" in problem for problem in problems)
    assert any("email duplicates" in problem for problem in problems)
    assert any("summary duplicates" in problem for problem in problems)
    assert any("history duplicates" in problem for problem in problems)

    with pytest.raises(CandidateUniquenessError):
        validate_profile_uniqueness(duplicate, [existing])
