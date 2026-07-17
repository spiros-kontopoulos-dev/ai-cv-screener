"""
Health-check API endpoint.

This module contains only the HTTP route responsible for confirming that
the backend process is running and its configuration loaded successfully.
"""

from fastapi import APIRouter

from app.core.config import get_settings


# APIRouter lets us define endpoints outside main.py.
# These routes will later be attached to the main FastAPI application.
router = APIRouter(
    tags=["health"],
)


# Load the shared, cached application settings.
settings = get_settings()


@router.get("/health")
def health_check() -> dict[str, str]:
    """
    Return the basic status of the backend application.

    This endpoint deliberately avoids OpenAI, ChromaDB, and the CV dataset.
    It remains available even when those later dependencies are unavailable.
    """

    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }