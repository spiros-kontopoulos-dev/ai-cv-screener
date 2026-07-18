"""Tests for final collection-wide candidate dataset validation."""

from pathlib import Path

from app.candidate_generation import (
    load_candidate_dataset_plan,
    load_candidate_profiles,
    validate_candidate_dataset,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = BACKEND_ROOT / "app" / "dataset" / "candidate_dataset_plan.json"

# Docker runs tests from /app, where Compose mounts the repository data folder
# as /app/data. The fallback also supports running Pytest directly from the
# local backend directory, where data is a sibling of backend.
CONFIGURED_PROFILES_PATH = Path(
    "data/candidate_profiles/candidate_profiles.json"
)
PROFILES_PATH = (
    CONFIGURED_PROFILES_PATH
    if CONFIGURED_PROFILES_PATH.exists()
    else BACKEND_ROOT.parent
    / "data"
    / "candidate_profiles"
    / "candidate_profiles.json"
)


def _load_dataset():
    return (
        load_candidate_dataset_plan(PLAN_PATH),
        load_candidate_profiles(PROFILES_PATH),
    )


def test_committed_candidate_collection_passes_every_final_check() -> None:
    """The complete 30-profile dataset should be ready for PDF rendering."""

    plan, profiles = _load_dataset()

    report = validate_candidate_dataset(plan, profiles)

    assert report.is_valid
    assert report.actual_profile_count == 30
    assert report.compliant_profile_count == 30
    assert report.validated_scenario_count == 11
    assert report.uniqueness_problem_count == 0
    assert report.distribution_problem_count == 0
    assert report.issues == ()


def test_validation_reports_missing_candidate_and_count_problem() -> None:
    """A partial generation file must never be accepted as complete."""

    plan, profiles = _load_dataset()

    report = validate_candidate_dataset(plan, profiles[:-1])

    assert not report.is_valid
    assert any("Profile count mismatch" in issue for issue in report.issues)
    assert any("candidate_030" in issue for issue in report.issues)


def test_validation_reports_cross_candidate_duplicate_name() -> None:
    """Collection validation reruns the same uniqueness checks as generation."""

    plan, profiles = _load_dataset()
    duplicate_profile = profiles[1].model_copy(
        update={"full_name": profiles[0].full_name}
    )
    changed_profiles = [profiles[0], duplicate_profile, *profiles[2:]]

    report = validate_candidate_dataset(plan, changed_profiles)

    assert not report.is_valid
    assert report.uniqueness_problem_count >= 1
    assert any("full_name duplicates" in issue for issue in report.issues)


def test_validation_detects_unsupported_security_clearance_evidence() -> None:
    """The planned no-evidence question must remain genuinely unsupported."""

    plan, profiles = _load_dataset()
    changed_summary = (
        profiles[0].summary
        + " Holds active government security clearance."
    )
    changed_profile = profiles[0].model_copy(
        update={"summary": changed_summary}
    )
    changed_profiles = [changed_profile, *profiles[1:]]

    report = validate_candidate_dataset(plan, changed_profiles)

    assert not report.is_valid
    assert any(
        "unsupported evidence 'security clearance'" in issue
        for issue in report.issues
    )
