"""Endpoint tests for indexed candidate listing and trusted PDF delivery."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.dependencies import get_candidate_catalog_service
from app.main import app
from app.services import IndexedCandidate, CandidateNotFoundError


class FakeCatalog:
    def __init__(self, candidate: IndexedCandidate, pdf_path: Path):
        self.candidate = candidate
        self.pdf_path = pdf_path

    def list_candidates(self):
        return (self.candidate,)

    def get_candidate(self, candidate_id):
        if candidate_id != self.candidate.candidate_id:
            raise CandidateNotFoundError("Unknown candidate ID.")
        return self.candidate

    def resolve_candidate_pdf(self, candidate_id):
        self.get_candidate(candidate_id)
        return self.pdf_path


def _catalog(tmp_path: Path) -> FakeCatalog:
    pdf_path = tmp_path / "eleni-markou-cv.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% candidate test\n")
    candidate = IndexedCandidate(
        candidate_id="candidate_001",
        name="Eleni Markou",
        professional_title="Senior Python Backend Engineer",
        document_id="document_001",
        document_hash="a" * 64,
        source_filename=pdf_path.name,
        source_path=pdf_path,
        cv_available=True,
        photo_available=False,
    )
    return FakeCatalog(candidate, pdf_path)


def test_candidate_list_returns_stable_real_index_shape(tmp_path) -> None:
    app.dependency_overrides[get_candidate_catalog_service] = lambda: _catalog(
        tmp_path
    )
    try:
        response = TestClient(app).get("/api/candidates")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "count": 1,
        "candidates": [
            {
                "candidate_id": "candidate_001",
                "name": "Eleni Markou",
                "professional_title": "Senior Python Backend Engineer",
                "source_filename": "eleni-markou-cv.pdf",
                "cv_available": True,
                "photo_available": False,
            }
        ],
    }


def test_candidate_pdf_is_served_inline_with_pdf_content_type(tmp_path) -> None:
    app.dependency_overrides[get_candidate_catalog_service] = lambda: _catalog(
        tmp_path
    )
    try:
        response = TestClient(app).get("/api/candidates/candidate_001/cv")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert "inline" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-1.4")


def test_unknown_candidate_pdf_returns_safe_404(tmp_path) -> None:
    app.dependency_overrides[get_candidate_catalog_service] = lambda: _catalog(
        tmp_path
    )
    try:
        response = TestClient(app).get("/api/candidates/candidate_999/cv")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "candidate_not_found"
