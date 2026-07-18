"""Tests for the WP3 candidate-generation command-line skeleton."""

from pathlib import Path

from app.core.config import Settings
from app.scripts.generate_candidate_profiles import run_cli


PLAN_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "dataset"
    / "candidate_dataset_plan.json"
)


def _test_settings() -> Settings:
    """Return isolated settings without reading a developer's real paths."""

    return Settings(
        candidate_dataset_plan_path=PLAN_PATH,
        candidate_generation_max_retries=2,
    )


def test_dry_run_previews_selected_candidates(capsys) -> None:
    """The first patch should inspect slots without network activity."""

    status = run_cli(
        ["--count", "2", "--dry-run"],
        settings=_test_settings(),
    )

    captured = capsys.readouterr()

    assert status == 0
    assert "CANDIDATE GENERATION DRY RUN" in captured.out
    assert "candidate_001 | Eleni Markou" in captured.out
    assert "candidate_002 | Jonas Keller" in captured.out
    assert "Selected slots: 2" in captured.out
    assert "OpenAI requests made: 0" in captured.out
    assert captured.err == ""


def test_cli_can_preview_one_exact_candidate(capsys) -> None:
    """A developer can target one slot while tuning the future prompt."""

    status = run_cli(
        ["--candidate-id", "candidate_024", "--dry-run"],
        settings=_test_settings(),
    )

    captured = capsys.readouterr()

    assert status == 0
    assert "candidate_024" in captured.out
    assert "Selected slots: 1" in captured.out


def test_cli_requires_dry_run_until_openai_is_connected(capsys) -> None:
    """Patch 01 must never imply that real generation already occurred."""

    status = run_cli(
        ["--count", "1"],
        settings=_test_settings(),
    )

    captured = capsys.readouterr()

    assert status == 2
    assert "not connected in WP3 Patch 01" in captured.err
    assert captured.out == ""


def test_cli_reports_invalid_selection_without_traceback(capsys) -> None:
    """Developer input errors should produce concise actionable output."""

    status = run_cli(
        ["--candidate-id", "candidate_999", "--dry-run"],
        settings=_test_settings(),
    )

    captured = capsys.readouterr()

    assert status == 2
    assert "ERROR: Unknown candidate ID" in captured.err
