"""Tests for optional human-readable PDF filename planning."""

from pathlib import Path

import pymupdf

from app.cv_ingestion import (
    apply_cv_document_renames,
    build_readable_cv_filename,
    build_readable_cv_filename_from_metadata,
    load_cv_document,
    plan_cv_document_renames,
)


def test_readable_filename_uses_detected_name_and_role(tmp_path: Path) -> None:
    """Display metadata becomes a portable name-role-cv.pdf slug."""

    document = load_cv_document(
        _write_cv_pdf(
            tmp_path / "candidate_001.pdf",
            name="Lucía Navarro",
            title="Junior Python API Engineer",
            candidate_id="candidate_001",
        )
    )

    assert build_readable_cv_filename(document) == (
        "lucia-navarro-junior-python-api-engineer-cv.pdf"
    )


def test_readable_filename_can_be_built_before_pdf_rendering() -> None:
    """Validated profile metadata uses the same canonical naming rule."""

    assert build_readable_cv_filename_from_metadata(
        candidate_name="Lucía Navarro",
        professional_title="Junior Python API Engineer",
        source_label="candidate_003",
    ) == "lucia-navarro-junior-python-api-engineer-cv.pdf"


def test_rename_plan_adds_hash_suffix_for_colliding_names(tmp_path: Path) -> None:
    """Two matching display names receive deterministic unique targets."""

    first_document = load_cv_document(
        _write_cv_pdf(
            tmp_path / "candidate_001.pdf",
            name="Alex Morgan",
            title="Backend Engineer",
            candidate_id="candidate_001",
        )
    )
    second_document = load_cv_document(
        _write_cv_pdf(
            tmp_path / "candidate_002.pdf",
            name="Alex Morgan",
            title="Backend Engineer",
            candidate_id="candidate_002",
        )
    )

    plans = plan_cv_document_renames([first_document, second_document])

    assert plans[0].target_path.name == "alex-morgan-backend-engineer-cv.pdf"
    assert plans[1].target_path.name == (
        "alex-morgan-backend-engineer-cv-"
        f"{second_document.source.document_hash[:8]}.pdf"
    )


def test_apply_rename_changes_only_the_filename(tmp_path: Path) -> None:
    """Applying a reviewed plan preserves bytes while changing the path."""

    source_path = _write_cv_pdf(
        tmp_path / "candidate_003.pdf",
        name="Jane Example",
        title="Data Engineer",
        candidate_id="candidate_003",
    )
    original_bytes = source_path.read_bytes()
    document = load_cv_document(source_path)
    plans = plan_cv_document_renames([document])

    applied = apply_cv_document_renames(plans)

    assert applied == plans
    assert not source_path.exists()
    assert plans[0].target_path.read_bytes() == original_bytes


def _write_cv_pdf(
    path: Path,
    *,
    name: str,
    title: str,
    candidate_id: str,
) -> Path:
    """Create a one-page PDF with the header shape used by the demo CVs."""

    with pymupdf.open() as document:
        page = document.new_page()
        for index, line in enumerate(
            ["CURRICULUM VITAE", name, title, candidate_id],
            start=0,
        ):
            page.insert_text((72, 72 + index * 18), line)
        document.save(path)

    return path
