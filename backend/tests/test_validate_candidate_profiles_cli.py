"""Tests for the final candidate dataset validation command."""

from pathlib import Path

from app.candidate_generation import save_candidate_profiles
from app.core.config import Settings
from app.scripts.validate_candidate_profiles import run_cli


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


def _settings(profiles_path: Path = PROFILES_PATH) -> Settings:
    return Settings(
        candidate_dataset_plan_path=PLAN_PATH,
        candidate_profiles_output_path=profiles_path,
    )


def test_cli_prints_passing_collection_summary(capsys) -> None:
    """A valid collection should return zero with a concise report."""

    status = run_cli(settings=_settings())

    captured = capsys.readouterr()
    assert status == 0
    assert "Profiles: 30/30" in captured.out
    assert "Slot-compliant profiles: 30/30" in captured.out
    assert "Validated search scenarios: 11/11" in captured.out
    assert "Result: PASS" in captured.out
    assert captured.err == ""


def test_cli_returns_failure_for_partial_collection(
    tmp_path: Path,
    capsys,
) -> None:
    """A partial persisted file should return a non-zero validation status."""

    from app.candidate_generation import load_candidate_profiles

    profiles = load_candidate_profiles(PROFILES_PATH)
    partial_path = tmp_path / "candidate_profiles.json"
    save_candidate_profiles(partial_path, profiles[:-1])

    status = run_cli(settings=_settings(partial_path))

    captured = capsys.readouterr()
    assert status == 1
    assert "Profiles: 29/30" in captured.out
    assert "Result: FAIL" in captured.out
