"""Tests for trusted candidate metadata and PDF resolution."""

from pathlib import Path

import pytest

from app.core.config import Settings
from app.cv_ingestion import RawStoredChunk, VectorIndexCoverage
from app.services import (
    CandidateCatalogError,
    CandidateCatalogService,
    CandidateNotFoundError,
)


class FakeRepository:
    def __init__(self, chunks, coverage=None):
        self._chunks = tuple(chunks)
        self._coverage = coverage

    def get_all_chunks(self):
        return self._chunks

    def get_index_coverage(self):
        return self._coverage


def _metadata(**overrides):
    values = {
        "candidate_id": "candidate_001",
        "candidate_name": "Eleni Markou",
        "professional_title": "Senior Python Backend Engineer",
        "document_id": "document_001",
        "document_hash": "a" * 64,
        "source_filename": "eleni-markou-cv.pdf",
        "source_path": "/app/data/cv_pdfs/eleni-markou-cv.pdf",
    }
    values.update(overrides)
    return values


def _service(tmp_path: Path, chunks) -> CandidateCatalogService:
    pdf_directory = tmp_path / "pdfs"
    image_directory = tmp_path / "images"
    pdf_directory.mkdir()
    image_directory.mkdir()
    settings = Settings(
        cv_ingestion_default_directory=pdf_directory,
        cv_pdfs_output_directory=pdf_directory,
        candidate_images_directory=image_directory,
        cv_vector_store_directory=tmp_path / "chroma",
    )
    return CandidateCatalogService(
        settings,
        repository=FakeRepository(chunks),
    )


def test_catalogue_uses_index_metadata_and_safe_filename_fallback(tmp_path) -> None:
    pdf_path = tmp_path / "pdfs" / "eleni-markou-cv.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF-1.4\n% test\n")
    image_path = tmp_path / "images" / "candidate_001.webp"
    image_path.parent.mkdir()
    image_path.write_bytes(b"RIFFtestWEBP")

    service = CandidateCatalogService(
        Settings(
            cv_ingestion_default_directory=pdf_path.parent,
            cv_pdfs_output_directory=pdf_path.parent,
            candidate_images_directory=image_path.parent,
            cv_vector_store_directory=tmp_path / "chroma",
        ),
        repository=FakeRepository(
            [RawStoredChunk("chunk_1", "Evidence", _metadata())]
        ),
    )

    candidates = service.list_candidates()

    assert len(candidates) == 1
    assert candidates[0].candidate_id == "candidate_001"
    assert candidates[0].name == "Eleni Markou"
    assert candidates[0].cv_available is True
    assert candidates[0].photo_available is True
    assert service.resolve_candidate_pdf("candidate_001") == pdf_path.resolve()


def test_catalogue_rejects_inconsistent_candidate_metadata(tmp_path) -> None:
    service = _service(
        tmp_path,
        [
            RawStoredChunk("chunk_1", "One", _metadata()),
            RawStoredChunk(
                "chunk_2",
                "Two",
                _metadata(candidate_name="Invented Name"),
            ),
        ],
    )

    with pytest.raises(CandidateCatalogError, match="inconsistent"):
        service.list_candidates()


def test_catalogue_rejects_non_basename_pdf_metadata(tmp_path) -> None:
    service = _service(
        tmp_path,
        [
            RawStoredChunk(
                "chunk_1",
                "Evidence",
                _metadata(source_filename="../secret.pdf"),
            )
        ],
    )

    with pytest.raises(CandidateCatalogError, match="safe basename"):
        service.list_candidates()


def test_unknown_candidate_id_is_not_resolved(tmp_path) -> None:
    service = _service(
        tmp_path,
        [RawStoredChunk("chunk_1", "Evidence", _metadata())],
    )

    with pytest.raises(CandidateNotFoundError, match="Unknown candidate"):
        service.resolve_candidate_pdf("candidate_999")
