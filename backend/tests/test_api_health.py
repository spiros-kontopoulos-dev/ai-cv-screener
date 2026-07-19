"""Endpoint tests for non-secret API readiness diagnostics."""

from fastapi.testclient import TestClient

from app.api.dependencies import get_api_settings, get_candidate_catalog_service
from app.core.config import Settings
from app.cv_ingestion import VectorIndexCoverage
from app.main import app


class FakeCatalog:
    def __init__(self, coverage):
        self.coverage = coverage

    def get_index_coverage(self):
        return self.coverage


def _coverage() -> VectorIndexCoverage:
    return VectorIndexCoverage(
        record_count=184,
        document_count=30,
        candidate_count=30,
        source_count=30,
        complete_document_count=30,
        incomplete_document_count=0,
        documents=(),
    )


def test_health_reports_deterministic_provider_and_index_readiness() -> None:
    app.dependency_overrides[get_api_settings] = lambda: Settings(
        cv_grounded_answer_provider="deterministic",
    )
    app.dependency_overrides[get_candidate_catalog_service] = lambda: FakeCatalog(
        _coverage()
    )
    try:
        response = TestClient(app).get("/api/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "AI CV Screener API",
        "environment": "development",
        "provider": {
            "requested_mode": "deterministic",
            "active_provider": "deterministic",
            "model": "deterministic-template-v1",
            "ready": True,
        },
        "index": {
            "available": True,
            "record_count": 184,
            "document_count": 30,
            "candidate_count": 30,
            "complete_document_count": 30,
            "incomplete_document_count": 0,
        },
    }


def test_health_degrades_explicit_hosted_provider_without_key() -> None:
    app.dependency_overrides[get_api_settings] = lambda: Settings(
        cv_grounded_answer_provider="openai",
        openai_api_key=None,
    )
    app.dependency_overrides[get_candidate_catalog_service] = lambda: FakeCatalog(
        _coverage()
    )
    try:
        response = TestClient(app).get("/api/health")
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "degraded"
    assert payload["provider"]["active_provider"] == "openai"
    assert payload["provider"]["ready"] is False
    assert "api_key" not in response.text.casefold()
