"""CLI tests for the complete administrator ingestion workflow."""

from dataclasses import replace

from pathlib import Path

import pymupdf

from app.core.config import Settings
from app.cv_ingestion import (
    CvIngestionDocumentResult,
    CvIngestionFailure,
    CvIngestionSummary,
    VectorIndexCoverage,
)
from app.scripts.ingest_cv_documents import run_cli


class FakeService:
    """Return one deterministic completed ingestion summary."""

    def ingest(self, paths, **kwargs):
        path = paths[0]
        return CvIngestionSummary(
            selected_pdf_count=1,
            unique_pdf_count=1,
            indexed_document_count=1,
            skipped_document_count=0,
            metadata_refreshed_count=0,
            duplicate_input_count=0,
            failed_document_count=0,
            pages_extracted=2,
            chunks_generated=6,
            chunks_embedded=6,
            records_upserted=6,
            records_deleted=0,
            collection_count=6,
            rebuilt=kwargs.get("rebuild", False),
            results=(
                CvIngestionDocumentResult(
                    path,
                    "a" * 64,
                    "candidate_001",
                    "indexed",
                    page_count=2,
                    chunk_count=6,
                ),
            ),
            failures=(),
            coverage=VectorIndexCoverage(
                record_count=6,
                document_count=1,
                candidate_count=1,
                source_count=1,
                complete_document_count=1,
                incomplete_document_count=0,
                documents=(),
            ),
        )


class FailingService(FakeService):
    """Return a partial document failure for shell exit-code validation."""

    def ingest(self, paths, **kwargs):
        summary = super().ingest(paths, **kwargs)
        return replace(
            summary,
            indexed_document_count=0,
            failed_document_count=1,
            failures=(
                CvIngestionFailure(paths[0], "processing", "bad pdf"),
            ),
        )


def test_cli_prints_complete_ingestion_and_coverage_summary(
    tmp_path: Path,
    capsys,
) -> None:
    """One command reports every stage and final index coverage."""

    pdf_path = tmp_path / "candidate_001.pdf"
    _write_pdf(pdf_path)

    exit_code = run_cli(
        ["--file", str(pdf_path), "--rebuild"],
        settings=Settings(cv_ingestion_default_directory=tmp_path),
        service=FakeService(),
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "CV INGESTION COMPLETE" in output
    assert "Indexed documents: 1" in output
    assert "Chunks embedded: 6" in output
    assert "Collection records: 6" in output
    assert "Complete documents: 1" in output
    assert "status=indexed" in output


def test_cli_rejects_batch_metadata_overrides(tmp_path: Path, capsys) -> None:
    """One candidate identity cannot accidentally be assigned to several PDFs."""

    first = tmp_path / "one.pdf"
    second = tmp_path / "two.pdf"
    _write_pdf(first)
    _write_pdf(second)

    exit_code = run_cli(
        [
            "--file",
            str(first),
            "--file",
            str(second),
            "--candidate-name",
            "Jane Example",
        ],
        service=FakeService(),
    )

    assert exit_code == 2
    assert "exactly one PDF" in capsys.readouterr().err


def test_cli_returns_partial_failure_exit_code(tmp_path: Path, capsys) -> None:
    """Document failures are visible and produce a non-zero shell status."""

    pdf_path = tmp_path / "candidate_001.pdf"
    _write_pdf(pdf_path)

    exit_code = run_cli(
        ["--file", str(pdf_path)],
        service=FailingService(),
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Failed documents: 1" in captured.out
    assert "stage=processing" in captured.err


def _write_pdf(path: Path) -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Jane Example\nBackend Engineer\nPython")
    document.save(path)
    document.close()
