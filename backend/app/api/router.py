"""
Central API router.

Every endpoint module is registered here before the combined router is
attached to the FastAPI application.
"""

from fastapi import APIRouter

from app.api.routes.health import router as health_router


# This router will eventually combine the health, chat, and any other
# approved API routes.
api_router = APIRouter()


# Register the routes defined in health.py.
api_router.include_router(health_router)