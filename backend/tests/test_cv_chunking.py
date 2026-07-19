"""Tests for adaptive, candidate-safe CV chunking."""

from hashlib import sha256
from pathlib import Path

import pytest

from app.cv_ingestion import (
    SECTION_DOCUMENT,
    SECTION_EDUCATION,
    SECTION_EXPERIENCE,
    SECTION_IDENTITY,
    SECTION_PROFESSIONAL_SUMMARY,
    SECTION_PROJECTS,
    SECTION_SKILLS_AND_LANGUAGES,
    CvChunkingConfig,
    CvChunkingError,
    CvSourceMetadata,
    ExtractedCvDocument,
    ExtractedCvPage,
    chunk_cv_document,
    chunk_cv_documents,
    load_cv_documents,
    select_cv_pdf_paths,
)


def test_chunker_detects_known_sections_and_combined_columns() -> None:
    """Rendered headings become stable section metadata without template JSON."""

    document = _make_document(
        [
            "\n".join(
                (
                    "C U R R I C U L U M V I T A E",
                    "Jane Example",
                    "Backend Engineer",
                    "candidate_001",
                    "PROFESSIONAL PROFILE",
                    "Builds reliable APIs and data services.",
                    "PROFESSIONAL EXPERIENCE",
                    "Backend Engineer Jan 2022 - Present",
                    "Example Labs · Athens, Greece",
                    "• Built Python APIs.",
                    "Technologies: Python, FastAPI, PostgreSQL",
                    "SKILLS LANGUAGES",
                    "PROGRAMMING LANGUAGES English Native",
                    "Python 6y German Professional",
                    "FastAPI 4y SELECTED PROJECTS",
                    "Search API 2025",
                    "Built a semantic search API.",
                )
            )
        ]
    )

    chunks = chunk_cv_document(document)
    sections = [chunk.section_name for chunk in chunks]

    assert sections == [
        SECTION_IDENTITY,
        SECTION_PROFESSIONAL_SUMMARY,
        SECTION_EXPERIENCE,
        SECTION_SKILLS_AND_LANGUAGES,
        SECTION_PROJECTS,
    ]
    assert "C U R R I C U L U M" not in chunks[0].text
    assert "Jane Example" in chunks[0].text
    assert "FastAPI 4y" in chunks[3].text
    assert "Search API 2025" in chunks[4].text


def test_experience_continues_across_pdf_pages_until_new_heading() -> None:
    """Page breaks do not terminate a section that visibly continues."""

    document = _make_document(
        [
            "Jane Example\nBackend Engineer\nPROFESSIONAL EXPERIENCE\n"
            "Role One\n• Built APIs.",
            "Role Two\n• Built data pipelines.\nSKILLS\nPython\nPostgreSQL",
        ]
    )

    chunks = chunk_cv_document(
        document,
        config=CvChunkingConfig(max_characters=1000, overlap_characters=50),
    )
    experience_chunk = next(
        chunk for chunk in chunks if chunk.section_name == SECTION_EXPERIENCE
    )

    assert experience_chunk.page_numbers == (1, 2)
    assert "Role One" in experience_chunk.text
    assert "Role Two" in experience_chunk.text


def test_unknown_layout_uses_generic_page_aware_fallback() -> None:
    """An arbitrary CV without recognized headings remains ingestible."""

    document = _make_document(
        [
            "Jane Example\nBackend Engineer\nBuilds APIs and services.",
            "Python FastAPI PostgreSQL Docker AWS",
        ],
        filename="uploaded-resume.pdf",
    )

    chunks = chunk_cv_document(document)

    assert {chunk.section_name for chunk in chunks} == {SECTION_DOCUMENT}
    assert chunks[0].source.candidate_id == "candidate_001"
    assert set(page for chunk in chunks for page in chunk.page_numbers) == {1, 2}


def test_long_content_respects_hard_maximum_and_uses_overlap() -> None:
    """Dense sections split into bounded windows with controlled context."""

    long_text = " ".join(f"skill{index}" for index in range(180))
    document = _make_document(
        [f"Jane Example\nEngineer\nSKILLS\n{long_text}"]
    )
    config = CvChunkingConfig(
        max_characters=240,
        min_characters=40,
        overlap_characters=40,
    )

    chunks = chunk_cv_document(document, config=config)
    skill_chunks = [
        chunk for chunk in chunks if chunk.section_name != SECTION_IDENTITY
    ]

    assert len(skill_chunks) > 2
    assert all(len(chunk.text) <= 240 for chunk in skill_chunks)
    first_tail_words = set(skill_chunks[0].text.split()[-3:])
    second_start_words = set(skill_chunks[1].text.split()[:8])
    assert first_tail_words & second_start_words


def test_chunk_ids_ignore_filename_and_path_but_include_version() -> None:
    """Renaming a PDF does not duplicate vectors, while strategy changes do."""

    first_document = _make_document(
        ["Jane Example\nEngineer\nSKILLS\nPython FastAPI"],
        filename="candidate_001.pdf",
        source_path=Path("/tmp/candidate_001.pdf"),
        document_hash="a" * 64,
    )
    renamed_document = _make_document(
        ["Jane Example\nEngineer\nSKILLS\nPython FastAPI"],
        filename="jane-example-engineer-cv.pdf",
        source_path=Path("/different/jane-example-engineer-cv.pdf"),
        document_hash="a" * 64,
    )

    original_chunks = chunk_cv_document(first_document)
    renamed_chunks = chunk_cv_document(renamed_document)
    revised_chunks = chunk_cv_document(
        first_document,
        config=CvChunkingConfig(version="cv-sections-v2"),
    )

    assert [chunk.chunk_id for chunk in original_chunks] == [
        chunk.chunk_id for chunk in renamed_chunks
    ]
    assert [chunk.chunk_id for chunk in original_chunks] != [
        chunk.chunk_id for chunk in revised_chunks
    ]


def test_batch_chunking_is_deterministic_and_candidate_safe() -> None:
    """Caller order does not change output and no chunk crosses documents."""

    second = _make_document(
        ["Second Person\nData Engineer\nSKILLS\nPython"],
        candidate_id="candidate_002",
        filename="zeta.pdf",
        document_hash="b" * 64,
    )
    first = _make_document(
        ["First Person\nBackend Engineer\nSKILLS\nFastAPI"],
        candidate_id="candidate_001",
        filename="alpha.pdf",
        document_hash="a" * 64,
    )

    chunks = chunk_cv_documents([second, first])

    assert chunks[0].source.candidate_id == "candidate_001"
    assert {chunk.source.candidate_id for chunk in chunks} == {
        "candidate_001",
        "candidate_002",
    }
    first_candidate_chunks = [
        chunk for chunk in chunks
        if chunk.source.candidate_id == "candidate_001"
    ]
    second_candidate_chunks = [
        chunk for chunk in chunks
        if chunk.source.candidate_id == "candidate_002"
    ]
    assert all("Second Person" not in chunk.text for chunk in first_candidate_chunks)
    assert all("First Person" not in chunk.text for chunk in second_candidate_chunks)


def test_config_rejects_incompatible_size_controls() -> None:
    """Invalid chunk limits fail before text is processed."""

    with pytest.raises(CvChunkingError, match="at least 200"):
        CvChunkingConfig(max_characters=199)

    with pytest.raises(CvChunkingError, match="cannot exceed"):
        CvChunkingConfig(max_characters=300, min_characters=301)

    with pytest.raises(CvChunkingError, match="smaller than maximum"):
        CvChunkingConfig(max_characters=300, overlap_characters=300)


def test_committed_collection_chunks_all_candidates_without_mixing() -> None:
    """The 30 committed PDFs produce bounded, unique candidate-safe chunks."""

    pdf_directory = _resolve_committed_pdf_directory()
    paths = select_cv_pdf_paths(directory=pdf_directory)
    documents = load_cv_documents(paths)

    chunks = chunk_cv_documents(documents)

    assert len(documents) == 30
    assert len(chunks) == 184
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)
    assert all(len(chunk.text) <= 1200 for chunk in chunks)
    assert {chunk.source.candidate_id for chunk in chunks} == {
        f"candidate_{index:03d}" for index in range(1, 31)
    }
    assert all(
        chunk.source.document_id.startswith("document_")
        for chunk in chunks
    )


def _make_document(
    page_texts: list[str],
    *,
    candidate_id: str = "candidate_001",
    filename: str = "candidate_001.pdf",
    source_path: Path | None = None,
    document_hash: str | None = None,
) -> ExtractedCvDocument:
    """Build an extracted document directly for focused chunking tests."""

    combined_text = "\n\n".join(page_texts)
    resolved_hash = document_hash or sha256(combined_text.encode()).hexdigest()
    source = CvSourceMetadata(
        document_id=f"document_{resolved_hash[:16]}",
        document_hash=resolved_hash,
        candidate_id=candidate_id,
        candidate_name="Jane Example",
        professional_title="Backend Engineer",
        source_filename=filename,
        source_path=source_path or Path(filename),
    )
    pages = tuple(
        ExtractedCvPage(
            source=source,
            page_number=page_number,
            total_pages=len(page_texts),
            text=page_text,
        )
        for page_number, page_text in enumerate(page_texts, start=1)
    )
    return ExtractedCvDocument(source=source, pages=pages)


def _resolve_committed_pdf_directory() -> Path:
    """Resolve shared test data in Docker and direct host execution."""

    candidates = (
        Path("/app/data/cv_pdfs"),
        Path(__file__).resolve().parents[2] / "data" / "cv_pdfs",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise AssertionError("Committed CV PDF directory could not be resolved.")
