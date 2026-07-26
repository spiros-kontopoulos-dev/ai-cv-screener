"""Collect the public API routes under one ``/api`` prefix.

Each route file owns one small area of the HTTP API:

- ``health`` reports whether the provider and vector index are ready;
- ``candidates`` lists candidates and serves their PDF CVs;
- ``chat`` runs the grounded candidate-question flow.

``app.main`` includes only this router, so new public route groups can be added
here without making the application entry point larger.
"""

from fastapi import APIRouter

from app.api.routes.candidates import router as candidates_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router


api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(candidates_router)
api_router.include_router(chat_router)
