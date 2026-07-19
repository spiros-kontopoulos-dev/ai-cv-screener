"""OpenAPI contract coverage for the four frozen WP8 endpoints."""

from fastapi.testclient import TestClient

from app.main import app


def test_openapi_exposes_frozen_routes_and_chat_examples() -> None:
    schema = TestClient(app).get("/openapi.json").json()

    assert set(
        path for path in schema["paths"] if path.startswith("/api/")
    ) == {
        "/api/health",
        "/api/candidates",
        "/api/candidates/{candidate_id}/cv",
        "/api/chat",
    }
    chat_schema = schema["components"]["schemas"]["ChatRequest"]
    assert chat_schema["example"]["candidate_limit"] == 5
    assert "Python" in chat_schema["example"]["question"]
