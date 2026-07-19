"""Central versioned application router for all public WP8 endpoints."""

from fastapi import APIRouter

from app.api.routes.candidates import router as candidates_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router


api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(candidates_router)
api_router.include_router(chat_router)
