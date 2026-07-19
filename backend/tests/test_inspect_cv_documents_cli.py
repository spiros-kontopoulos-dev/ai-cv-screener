"""Tests for the developer PDF extraction inspection command."""

from pathlib import Path

import pymupdf

from app.core.config import Settings
from app.scripts.inspect_cv_documents import run_cli


def test_cli_inspects_configured_default_directory(
    tmp_path: Path,
    capsys,
) -> None:
    """--all scans the configured directory and prints page summaries."""

    _write_pdf(tmp_path / "candidate_002.pdf", "Bob Example", "Data Engineer")
    _write_pdf(tmp_path / "candidate_001.pdf", "Alice Example", "API Engineer")
    settings = Settings(cv_ingestion_default_directory=tmp_path)

    status = run_cli(
        ["--all", "--preview-characters", "0"],
        settings=settings,
    )

    output = capsys.readouterr().out
    assert status == 0
    assert "CV PDF EXTRACTION COMPLETE" in output
    assert "Documents: 2" in output
    assert output.index("candidate_001") < output.index("candidate_002")
    assert "page=1/1" in output


def test_cli_allows_metadata_overrides_for_one_arbitrary_pdf(
    tmp_path: Path,
    capsys,
) -> None:
    """A future-upload-like file can receive explicit candidate metadata."""

    pdf_path = _write_pdf(
        tmp_path / "uploaded-resume.pdf",
        "Header Placeholder",
        "Unknown Role",
        candidate_id=None,
    )

    status = run_cli(
        [
            "--file",
            str(pdf_path),
            "--candidate-id",
            "candidate_external_001",
            "--candidate-name",
            "Spiros Kontopoulos",
            "--professional-title",
            "Senior Python Engineer",
            "--preview-characters",
            "0",
        ]
    )

    output = capsys.readouterr().out
    assert status == 0
    assert "candidate_external_001" in output
    assert "name=Spiros Kontopoulos" in output
    assert "title=Senior Python Engineer" in output


def test_cli_rejects_batch_metadata_overrides(tmp_path: Path, capsys) -> None:
    """One override cannot silently assign identity to several PDFs."""

    _write_pdf(tmp_path / "one.pdf", "One Person", "Engineer")
    _write_pdf(tmp_path / "two.pdf", "Two Person", "Engineer")

    status = run_cli(
        [
            "--directory",
            str(tmp_path),
            "--candidate-name",
            "Wrong Shared Name",
        ]
    )

    error_output = capsys.readouterr().err
    assert status == 2
    assert "exactly one selected PDF" in error_output


def _write_pdf(
    path: Path,
    name: str,
    title: str,
    candidate_id: str | None = "candidate_001",
) -> Path:
    """Create a small CV PDF for CLI tests."""

    lines = ["CURRICULUM VITAE", name, title]
    if candidate_id:
        lines.append(candidate_id)

    with pymupdf.open() as document:
        page = document.new_page()
        for index, line in enumerate(lines):
            page.insert_text((72, 72 + index * 18), line)
        document.save(path)

    return path
