"""Tests for the preview-first readable filename migration command."""

from pathlib import Path

import pymupdf

from app.scripts.rename_cv_documents import run_cli


def test_rename_cli_is_dry_run_by_default(tmp_path: Path, capsys) -> None:
    """The command displays changes without mutating files unless approved."""

    source_path = _write_pdf(tmp_path / "candidate_001.pdf")

    status = run_cli(["--file", str(source_path)])

    output = capsys.readouterr().out
    assert status == 0
    assert "Mode: DRY RUN" in output
    assert "candidate_001.pdf -> jane-example-backend-engineer-cv.pdf" in output
    assert source_path.exists()


def test_rename_cli_applies_reviewed_filename(tmp_path: Path, capsys) -> None:
    """--apply performs the exact displayed rename."""

    source_path = _write_pdf(tmp_path / "candidate_001.pdf")

    status = run_cli(["--file", str(source_path), "--apply"])

    output = capsys.readouterr().out
    assert status == 0
    assert "Mode: APPLY" in output
    assert "Applied renames: 1" in output
    assert not source_path.exists()
    assert (tmp_path / "jane-example-backend-engineer-cv.pdf").is_file()


def _write_pdf(path: Path) -> Path:
    """Create a PDF whose visible header supports readable naming."""

    with pymupdf.open() as document:
        page = document.new_page()
        for index, line in enumerate(
            [
                "CURRICULUM VITAE",
                "Jane Example",
                "Backend Engineer",
                "candidate_001",
            ]
        ):
            page.insert_text((72, 72 + index * 18), line)
        document.save(path)

    return path
