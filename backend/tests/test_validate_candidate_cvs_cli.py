"""Tests for the final CV PDF validation command."""

from pathlib import Path

from app.core.config import Settings
from app.scripts.validate_candidate_cvs import run_cli


_BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
_PLAN_PATH = _BACKEND_DIRECTORY / "app" / "dataset" / "candidate_dataset_plan.json"


def test_cli_passes_for_committed_final_pdf_collection(capsys) -> None:
    """The developer command reports the committed WP4 collection as valid."""

    data_directory = _resolve_committed_data_directory()

    status = run_cli(
        settings=Settings(
            candidate_dataset_plan_path=_PLAN_PATH,
            candidate_profiles_output_path=(
                data_directory
                / "candidate_profiles"
                / "candidate_profiles.json"
            ),
            cv_pdfs_output_directory=data_directory / "cv_pdfs",
        )
    )

    captured = capsys.readouterr()
    assert status == 0
    assert "PDF files: 30/30" in captured.out
    assert "Fully validated PDFs: 30/30" in captured.out
    assert "Searchable profile facts: 2466/2466" in captured.out
    assert "Validated search scenarios: 11/11" in captured.out
    assert "Result: PASS" in captured.out


def test_cli_fails_when_pdf_directory_is_missing(
    capsys,
    tmp_path: Path,
) -> None:
    """A missing output directory produces a controlled failing report."""

    data_directory = _resolve_committed_data_directory()

    status = run_cli(
        settings=Settings(
            candidate_dataset_plan_path=_PLAN_PATH,
            candidate_profiles_output_path=(
                data_directory
                / "candidate_profiles"
                / "candidate_profiles.json"
            ),
            cv_pdfs_output_directory=tmp_path / "missing-pdfs",
        )
    )

    captured = capsys.readouterr()
    assert status == 1
    assert "PDF files: 0/30" in captured.out
    assert "Missing CV PDFs:" in captured.out
    assert "Result: FAIL" in captured.out


def _resolve_committed_data_directory() -> Path:
    """Resolve shared data in Docker and direct host test layouts."""

    candidates = (
        _BACKEND_DIRECTORY / "data",
        _BACKEND_DIRECTORY.parent / "data",
    )
    for candidate in candidates:
        if (
            candidate
            / "candidate_profiles"
            / "candidate_profiles.json"
        ).is_file():
            return candidate

    checked_paths = ", ".join(str(path) for path in candidates)
    raise AssertionError(
        "Committed candidate data was not found. "
        f"Checked: {checked_paths}."
    )
