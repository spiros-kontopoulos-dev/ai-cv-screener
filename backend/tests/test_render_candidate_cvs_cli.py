"""Tests for the WP4 CV rendering dry-run command."""

from pathlib import Path

from app.candidate_generation.persistence import save_candidate_profiles
from app.core.config import Settings
from app.schemas import CandidateProfile
from app.scripts.render_candidate_cvs import run_cli


def _test_settings(
    tmp_path: Path,
    profiles_path: Path,
) -> Settings:
    """Return isolated filesystem paths for one CLI test."""

    return Settings(
        candidate_profiles_output_path=profiles_path,
        candidate_images_directory=tmp_path / "images",
        cv_pdfs_output_directory=tmp_path / "pdfs",
        cv_html_preview_directory=tmp_path / "html",
    )


def test_dry_run_prints_boundary_and_artifact_information(
    capsys,
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """Patch 1 inspects the collection without creating render outputs."""

    profile = CandidateProfile.model_validate(valid_candidate_payload)
    profiles_path = tmp_path / "candidate_profiles.json"
    save_candidate_profiles(profiles_path, [profile])

    status = run_cli(
        ["--all", "--dry-run"],
        settings=_test_settings(tmp_path, profiles_path),
    )

    captured = capsys.readouterr()

    assert status == 0
    assert "CV RENDERING DRY RUN" in captured.out
    assert "Profiles available: 1" in captured.out
    assert "Portraits available: 0/1" in captured.out
    assert "candidate_001.pdf" in captured.out
    assert not (tmp_path / "pdfs").exists()


def test_patch_one_requires_explicit_dry_run(
    capsys,
    tmp_path: Path,
) -> None:
    """The skeleton must not pretend that PDF output already exists."""

    status = run_cli(
        ["--all"],
        settings=_test_settings(
            tmp_path,
            tmp_path / "candidate_profiles.json",
        ),
    )

    captured = capsys.readouterr()

    assert status == 2
    assert "PDF rendering is introduced in WP4 Patch 2" in captured.err


def test_dry_run_reports_missing_profile_file_as_empty_collection(
    capsys,
    tmp_path: Path,
) -> None:
    """An empty source collection produces a clear planning error."""

    status = run_cli(
        ["--all", "--dry-run"],
        settings=_test_settings(
            tmp_path,
            tmp_path / "missing_profiles.json",
        ),
    )

    captured = capsys.readouterr()

    assert status == 2
    assert "At least one candidate profile is required" in captured.err
