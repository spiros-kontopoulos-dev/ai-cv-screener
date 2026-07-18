"""Tests for the WP4 CV planning and rendering command."""

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
    """Dry-run mode inspects the collection without creating outputs."""

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


def test_render_command_writes_verified_pdf_and_html_preview(
    capsys,
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """Non-dry-run mode now executes the real HTML-to-PDF workflow."""

    profile = CandidateProfile.model_validate(valid_candidate_payload)
    profiles_path = tmp_path / "candidate_profiles.json"
    save_candidate_profiles(profiles_path, [profile])

    status = run_cli(
        ["--candidate-id", "candidate_001", "--keep-html"],
        settings=_test_settings(tmp_path, profiles_path),
    )

    captured = capsys.readouterr()

    assert status == 0
    assert "CV RENDERING COMPLETE" in captured.out
    assert "Rendered CVs: 1" in captured.out
    assert "Placeholder portraits: 1/1" in captured.out
    assert "Result: PASS" in captured.out
    assert (tmp_path / "pdfs" / "candidate_001.pdf").is_file()
    assert (tmp_path / "html" / "candidate_001.html").is_file()


def test_dry_run_rejects_keep_html(
    capsys,
    tmp_path: Path,
) -> None:
    """A command that promises no writes cannot request an HTML artifact."""

    status = run_cli(
        ["--all", "--dry-run", "--keep-html"],
        settings=_test_settings(
            tmp_path,
            tmp_path / "candidate_profiles.json",
        ),
    )

    captured = capsys.readouterr()

    assert status == 2
    assert "cannot be combined with --dry-run" in captured.err


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
