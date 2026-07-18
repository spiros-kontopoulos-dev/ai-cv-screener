"""Tests for validated and atomic candidate-profile persistence."""

from json import loads
from pathlib import Path

import pytest

from app.candidate_generation import (
    CandidateProfilesFileError,
    load_candidate_profiles,
    save_candidate_profiles,
)
from app.schemas import CandidateProfile


def test_save_and_load_profiles_in_stable_candidate_order(
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """Persistence should be deterministic regardless of insertion order."""

    first_payload = {
        **valid_candidate_payload,
        "candidate_id": "candidate_001",
    }
    second_payload = {
        **valid_candidate_payload,
        "candidate_id": "candidate_002",
        "full_name": "Jamie Rivera",
        "contact": {
            **valid_candidate_payload["contact"],
            "email": "jamie.rivera@example.com",
        },
    }
    first = CandidateProfile.model_validate(first_payload)
    second = CandidateProfile.model_validate(second_payload)
    output_path = tmp_path / "candidate_profiles.json"

    save_candidate_profiles(output_path, [second, first])
    loaded_profiles = load_candidate_profiles(output_path)
    raw_profiles = loads(output_path.read_text(encoding="utf-8"))

    assert [profile.candidate_id for profile in loaded_profiles] == [
        "candidate_001",
        "candidate_002",
    ]
    assert [profile["candidate_id"] for profile in raw_profiles] == [
        "candidate_001",
        "candidate_002",
    ]
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_load_missing_profile_file_returns_empty_collection(
    tmp_path: Path,
) -> None:
    """A first generation run should not need a pre-created JSON file."""

    assert load_candidate_profiles(tmp_path / "missing.json") == []


def test_load_rejects_invalid_profile_json(tmp_path: Path) -> None:
    """Resume must stop instead of building on corrupted preparation data."""

    output_path = tmp_path / "candidate_profiles.json"
    output_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(
        CandidateProfilesFileError,
        match="contain invalid JSON",
    ):
        load_candidate_profiles(output_path)
