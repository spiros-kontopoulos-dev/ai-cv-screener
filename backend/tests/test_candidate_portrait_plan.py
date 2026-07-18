"""Tests for the committed 15-photo / 15-photo-free coverage plan."""

from collections import Counter
from pathlib import Path

from app.candidate_generation.persistence import load_candidate_profiles
from app.portrait_generation import (
    load_portrait_coverage_plan,
    validate_portrait_coverage_against_profiles,
)


_BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
_PLAN_PATH = (
    _BACKEND_DIRECTORY / "app" / "dataset" / "candidate_portrait_plan.json"
)


def _resolve_committed_profiles_path() -> Path:
    """Locate shared profile data in Docker and direct host test layouts.

    Docker runs tests from ``/app`` and mounts shared data at ``/app/data``.
    A direct host-side Pytest run keeps tests under ``<repo>/backend/tests``
    while shared data remains at ``<repo>/data``.  Checking both explicit
    layouts keeps this integration test portable without silently accepting a
    missing dataset as an empty profile collection.
    """

    candidate_paths = (
        _BACKEND_DIRECTORY
        / "data"
        / "candidate_profiles"
        / "candidate_profiles.json",
        _BACKEND_DIRECTORY.parent
        / "data"
        / "candidate_profiles"
        / "candidate_profiles.json",
    )

    for candidate_path in candidate_paths:
        if candidate_path.is_file():
            return candidate_path

    searched_paths = ", ".join(str(path) for path in candidate_paths)
    raise AssertionError(
        "Committed candidate profiles were not found. "
        f"Checked: {searched_paths}."
    )


def test_committed_portrait_plan_is_balanced_and_complete() -> None:
    """The selected subset covers all professions and expected seniority."""

    plan = load_portrait_coverage_plan(_PLAN_PATH)
    profiles = load_candidate_profiles(_resolve_committed_profiles_path())
    validate_portrait_coverage_against_profiles(plan, profiles)

    profiles_by_id = {
        profile.candidate_id: profile
        for profile in profiles
    }
    portrait_profiles = [
        profiles_by_id[candidate_id]
        for candidate_id in plan.portrait_candidate_ids
    ]

    assert len(profiles) == 30
    assert plan.portrait_count == 15
    assert len(profiles) - plan.portrait_count == 15
    assert {
        "candidate_003",
        "candidate_015",
        "candidate_029",
    }.issubset(plan.portrait_candidate_id_set)

    profession_counts = Counter(
        profile.profession.value
        for profile in portrait_profiles
    )
    assert len(profession_counts) == 10

    seniority_counts = Counter(
        profile.seniority.value
        for profile in portrait_profiles
    )
    assert seniority_counts == {
        "junior": 4,
        "mid": 6,
        "senior": 5,
    }
