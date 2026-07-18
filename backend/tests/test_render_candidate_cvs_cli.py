"""Tests for the WP4 CV planning and rendering command."""

from pathlib import Path

from app.candidate_generation.persistence import save_candidate_profiles
from app.core.config import Settings
from app.schemas import CandidateProfile
from app.scripts.render_candidate_cvs import run_cli


def _test_settings(
    tmp_path: Path,
    profiles_path: Path,
    portrait_plan_path: Path,
) -> Settings:
    """Return isolated filesystem paths for one CLI test."""

    return Settings(
        candidate_profiles_output_path=profiles_path,
        candidate_portrait_plan_path=portrait_plan_path,
        candidate_images_directory=tmp_path / "images",
        cv_pdfs_output_directory=tmp_path / "pdfs",
        cv_html_preview_directory=tmp_path / "html",
    )


def test_dry_run_prints_boundary_and_artifact_information(
    capsys,
    tmp_path: Path,
    valid_candidate_payload: dict,
    portrait_plan_factory,
) -> None:
    """Dry-run mode shows portrait-plan status without creating outputs."""

    profile = CandidateProfile.model_validate(valid_candidate_payload)
    profiles_path = tmp_path / "candidate_profiles.json"
    save_candidate_profiles(profiles_path, [profile])

    status = run_cli(
        ["--all", "--dry-run"],
        settings=_test_settings(
            tmp_path,
            profiles_path,
            portrait_plan_factory(["candidate_001"]),
        ),
    )

    captured = capsys.readouterr()

    assert status == 0
    assert "CV RENDERING DRY RUN" in captured.out
    assert "Profiles available: 1" in captured.out
    assert "Planned portraits: 1" in captured.out
    assert "Portraits available: 0/1" in captured.out
    assert "portrait=planned-missing" in captured.out
    assert "candidate_001.pdf" in captured.out
    assert not (tmp_path / "pdfs").exists()


def test_render_command_writes_photo_free_pdf_and_html_preview(
    capsys,
    tmp_path: Path,
    valid_candidate_payload: dict,
    portrait_plan_factory,
) -> None:
    """A candidate outside the plan renders without a fake initials photo."""

    profile = CandidateProfile.model_validate(valid_candidate_payload)
    profiles_path = tmp_path / "candidate_profiles.json"
    save_candidate_profiles(profiles_path, [profile])

    # A second profile is not required for the renderer; an empty plan is not
    # valid by contract, so point the plan at an unused but valid candidate ID
    # would fail coverage validation. Instead render a two-profile collection
    # with candidate_002 planned and candidate_001 intentionally photo-free.
    second_payload = {
        **valid_candidate_payload,
        "candidate_id": "candidate_002",
        "full_name": "Jordan Lee",
        "contact": {
            **valid_candidate_payload["contact"],
            "email": "jordan.lee@example.com",
        },
    }
    second_profile = CandidateProfile.model_validate(second_payload)
    save_candidate_profiles(profiles_path, [profile, second_profile])

    status = run_cli(
        ["--candidate-id", "candidate_001", "--keep-html"],
        settings=_test_settings(
            tmp_path,
            profiles_path,
            portrait_plan_factory(["candidate_002"]),
        ),
    )

    captured = capsys.readouterr()

    assert status == 0
    assert "CV RENDERING COMPLETE" in captured.out
    assert "Rendered CVs: 1" in captured.out
    assert "Photo-free CVs: 1" in captured.out
    assert "Placeholder portraits: 0" in captured.out
    assert "portrait=photo-free" in captured.out
    assert "Result: PASS" in captured.out
    assert (tmp_path / "pdfs" / "candidate_001.pdf").is_file()
    html_path = tmp_path / "html" / "candidate_001.html"
    assert html_path.is_file()
    assert '<div class="portrait-frame"' not in html_path.read_text(encoding="utf-8")


def test_dry_run_rejects_keep_html(
    capsys,
    tmp_path: Path,
    portrait_plan_factory,
) -> None:
    """A command that promises no writes cannot request an HTML artifact."""

    status = run_cli(
        ["--all", "--dry-run", "--keep-html"],
        settings=_test_settings(
            tmp_path,
            tmp_path / "candidate_profiles.json",
            portrait_plan_factory(["candidate_001"]),
        ),
    )

    captured = capsys.readouterr()

    assert status == 2
    assert "cannot be combined with --dry-run" in captured.err


def test_dry_run_reports_missing_profile_file_as_empty_collection(
    capsys,
    tmp_path: Path,
    portrait_plan_factory,
) -> None:
    """An empty source collection produces a clear planning error."""

    status = run_cli(
        ["--all", "--dry-run"],
        settings=_test_settings(
            tmp_path,
            tmp_path / "missing_profiles.json",
            portrait_plan_factory(["candidate_001"]),
        ),
    )

    captured = capsys.readouterr()

    assert status == 2
    assert "At least one candidate profile is required" in captured.err


def test_render_command_enforces_planned_portraits(
    capsys,
    tmp_path: Path,
    valid_candidate_payload: dict,
    portrait_plan_factory,
) -> None:
    """The final dataset flag rejects missing planned portrait assets."""

    profile = CandidateProfile.model_validate(valid_candidate_payload)
    profiles_path = tmp_path / "candidate_profiles.json"
    save_candidate_profiles(profiles_path, [profile])

    status = run_cli(
        [
            "--candidate-id",
            "candidate_001",
            "--enforce-portrait-plan",
        ],
        settings=_test_settings(
            tmp_path,
            profiles_path,
            portrait_plan_factory(["candidate_001"]),
        ),
    )

    captured = capsys.readouterr()
    assert status == 2
    assert "Planned portraits are missing" in captured.err
    assert not (tmp_path / "pdfs").exists()
