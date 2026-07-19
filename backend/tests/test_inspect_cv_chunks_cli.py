"""Tests for the developer CV chunk inspection command."""

from pathlib import Path

import pymupdf

from app.core.config import Settings
from app.scripts.inspect_cv_chunks import run_cli


def test_cli_chunks_configured_collection_and_prints_sections(
    tmp_path: Path,
    capsys,
) -> None:
    """--all applies extraction and chunking to the configured directory."""

    _write_pdf(tmp_path / "candidate_002.pdf", "Bob Example", "Data Engineer")
    _write_pdf(tmp_path / "candidate_001.pdf", "Alice Example", "API Engineer")
    settings = Settings(cv_ingestion_default_directory=tmp_path)

    status = run_cli(
        ["--all", "--preview-characters", "0"],
        settings=settings,
    )

    output = capsys.readouterr().out
    assert status == 0
    assert "CV CHUNKING COMPLETE" in output
    assert "Documents: 2" in output
    assert "SECTION COUNTS" in output
    assert "professional_summary" in output
    assert output.index("candidate_001") < output.index("candidate_002")


def test_cli_supports_future_upload_metadata_overrides(
    tmp_path: Path,
    capsys,
) -> None:
    """One arbitrary PDF can use explicit identity before a future upload API."""

    pdf_path = _write_pdf(
        tmp_path / "uploaded.pdf",
        "Unknown Person",
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


def test_cli_rejects_incompatible_chunk_limits(tmp_path: Path, capsys) -> None:
    """CLI overrides use the same deterministic configuration validation."""

    pdf_path = _write_pdf(
        tmp_path / "candidate_001.pdf",
        "Alice Example",
        "API Engineer",
    )

    status = run_cli(
        [
            "--file",
            str(pdf_path),
            "--max-characters",
            "300",
            "--overlap-characters",
            "300",
        ]
    )

    error_output = capsys.readouterr().err
    assert status == 2
    assert "smaller than maximum" in error_output


def _write_pdf(
    path: Path,
    name: str,
    title: str,
    candidate_id: str | None = "candidate_001",
) -> Path:
    """Create a selectable one-page CV with common section headings."""

    lines = [
        "CURRICULUM VITAE",
        name,
        title,
    ]
    if candidate_id:
        lines.append(candidate_id)
    lines.extend(
        (
            "PROFESSIONAL PROFILE",
            "Builds reliable applications.",
            "SKILLS",
            "Python FastAPI PostgreSQL",
        )
    )

    with pymupdf.open() as document:
        page = document.new_page()
        for index, line in enumerate(lines):
            page.insert_text((72, 72 + index * 18), line)
        document.save(path)

    return path
