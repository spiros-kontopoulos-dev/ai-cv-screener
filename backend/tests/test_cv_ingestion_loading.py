"""Tests for generic, deterministic CV PDF selection and extraction."""

from hashlib import sha256
from pathlib import Path
import shutil

import pymupdf
import pytest

from app.cv_ingestion import (
    CvDocumentExtractionError,
    CvDocumentSelectionError,
    calculate_pdf_sha256,
    load_cv_document,
    load_cv_documents,
    normalize_extracted_page_text,
    select_cv_pdf_paths,
)


def test_select_explicit_pdf_paths_in_deterministic_order(tmp_path: Path) -> None:
    """Repeatable --file input is sorted and does not depend on caller order."""

    second_path = _write_text_pdf(tmp_path / "zeta.pdf", ["Zeta Candidate"])
    first_path = _write_text_pdf(tmp_path / "Alpha.PDF", ["Alpha Candidate"])

    selected = select_cv_pdf_paths(files=[second_path, first_path])

    assert selected == (first_path, second_path)


def test_directory_selection_supports_optional_recursive_scanning(
    tmp_path: Path,
) -> None:
    """Directory mode ignores other files and only descends when requested."""

    root_pdf = _write_text_pdf(tmp_path / "root.pdf", ["Root Candidate"])
    nested_directory = tmp_path / "nested"
    nested_directory.mkdir()
    nested_pdf = _write_text_pdf(
        nested_directory / "nested.pdf",
        ["Nested Candidate"],
    )
    (tmp_path / "notes.txt").write_text("not a pdf", encoding="utf-8")

    direct = select_cv_pdf_paths(directory=tmp_path)
    recursive = select_cv_pdf_paths(directory=tmp_path, recursive=True)

    assert direct == (root_pdf,)
    assert recursive == (nested_pdf, root_pdf)


def test_selection_rejects_missing_or_ambiguous_inputs(tmp_path: Path) -> None:
    """The selector fails clearly instead of silently processing nothing."""

    with pytest.raises(CvDocumentSelectionError, match="exactly one"):
        select_cv_pdf_paths()

    with pytest.raises(CvDocumentSelectionError, match="does not exist"):
        select_cv_pdf_paths(files=[tmp_path / "missing.pdf"])

    empty_directory = tmp_path / "empty"
    empty_directory.mkdir()
    with pytest.raises(CvDocumentSelectionError, match="No PDF files"):
        select_cv_pdf_paths(directory=empty_directory)


def test_loader_extracts_pages_hash_and_candidate_metadata(tmp_path: Path) -> None:
    """One PDF becomes an immutable document with stable page metadata."""

    pdf_path = _write_text_pdf(
        tmp_path / "candidate_123.pdf",
        [
            "CURRICULUM VITAE\nJane Example\nSenior Backend Engineer\n"
            "Senior · Backend Engineering · candidate_123\n"
            "PROFESSIONAL PROFILE\nBuilds reliable APIs.\nPage 1 of 2",
            "SKILLS\nPython\n•\nPostgreSQL\nPage 2 of 2",
        ],
    )

    document = load_cv_document(pdf_path)

    expected_hash = sha256(pdf_path.read_bytes()).hexdigest()
    assert calculate_pdf_sha256(pdf_path) == expected_hash
    assert document.source.document_hash == expected_hash
    assert document.source.document_id == f"document_{expected_hash[:16]}"
    assert document.source.candidate_id == "candidate_123"
    assert document.source.candidate_name == "Jane Example"
    assert document.source.professional_title == "Senior Backend Engineer"
    assert document.source.source_filename == "candidate_123.pdf"
    assert document.page_count == 2
    assert [page.page_number for page in document.pages] == [1, 2]
    assert all(page.source is document.source for page in document.pages)
    assert "Page 1 of 2" not in document.pages[0].text
    assert "\n•\n" not in f"\n{document.pages[1].text}\n"
    assert "PROFESSIONAL PROFILE" in document.pages[0].text
    assert "SKILLS" in document.pages[1].text


def test_arbitrary_filename_uses_hash_identity_and_allows_metadata_overrides(
    tmp_path: Path,
) -> None:
    """Real uploads do not need candidate_XXX filenames or generator data."""

    pdf_path = _write_text_pdf(
        tmp_path / "resume-final-v4.pdf",
        ["A logo line\nContact details only"],
    )

    document = load_cv_document(
        pdf_path,
        candidate_name="Spiros Kontopoulos",
        professional_title="Senior Python Engineer",
    )

    assert document.source.candidate_id == (
        f"candidate_{document.source.document_hash[:16]}"
    )
    assert document.source.candidate_name == "Spiros Kontopoulos"
    assert document.source.professional_title == "Senior Python Engineer"


def test_loader_rejects_empty_and_corrupt_pdfs(tmp_path: Path) -> None:
    """Unreadable files and image-only or blank PDFs fail before chunking."""

    empty_pdf = tmp_path / "empty.pdf"
    with pymupdf.open() as document:
        document.new_page()
        document.save(empty_pdf)

    corrupt_pdf = tmp_path / "corrupt.pdf"
    corrupt_pdf.write_bytes(b"this is not a pdf")

    with pytest.raises(CvDocumentExtractionError, match="no extractable text"):
        load_cv_document(empty_pdf)

    with pytest.raises(CvDocumentExtractionError, match="could not be opened"):
        load_cv_document(corrupt_pdf)


def test_batch_rejects_duplicate_content_and_candidate_ids(tmp_path: Path) -> None:
    """One batch cannot ambiguously represent the same file or candidate twice."""

    first_path = _write_text_pdf(
        tmp_path / "first.pdf",
        ["Jane Example\nBackend Engineer\ncandidate_001"],
    )
    copied_path = tmp_path / "copy.pdf"
    shutil.copyfile(first_path, copied_path)

    with pytest.raises(CvDocumentExtractionError, match="content hash"):
        load_cv_documents([first_path, copied_path])

    second_path = _write_text_pdf(
        tmp_path / "second.pdf",
        ["Jane Example\nBackend Engineer\ncandidate_001\nDifferent revision"],
    )
    with pytest.raises(CvDocumentExtractionError, match="candidate ID"):
        load_cv_documents([first_path, second_path])


def test_normalization_preserves_lines_and_removes_known_layout_noise() -> None:
    """Whitespace cleanup keeps headings while removing footers and bullets."""

    normalized = normalize_extracted_page_text(
        "  SKILLS  \r\nPython   8y\r\n•\r\n\r\nPage 1 of 2\r\n"
    )

    assert normalized == "SKILLS\nPython 8y"


def _write_text_pdf(path: Path, page_texts: list[str]) -> Path:
    """Create a small selectable-text PDF for extraction tests."""

    with pymupdf.open() as document:
        for page_text in page_texts:
            page = document.new_page()
            y_position = 72
            for line in page_text.splitlines():
                page.insert_text((72, y_position), line)
                y_position += 16
        document.save(path)

    return path
