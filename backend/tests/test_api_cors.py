"""Focused browser-origin tests for the local React/FastAPI boundary."""

from fastapi.testclient import TestClient

from app.main import app


def test_configured_frontend_origin_receives_cors_headers() -> None:
    response = TestClient(app).options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:5173"
    )
    assert "POST" in response.headers["access-control-allow-methods"]


def test_unknown_origin_is_not_granted_browser_access() -> None:
    response = TestClient(app).options(
        "/api/chat",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "access-control-allow-origin" not in response.headers
