"""FastAPI application entry point for the local AI CV Screener product."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import install_exception_handlers
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging


logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Configure process logging and record clean startup/shutdown boundaries."""

    configure_logging(settings.log_level)
    logger.info("Starting %s in %s environment", settings.app_name, settings.app_env)
    yield
    logger.info("Stopping %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version="0.8.0",
    description=(
        "Thin HTTP API over the validated candidate-aware retrieval and "
        "grounded answer pipeline."
    ),
    lifespan=lifespan,
)

# The frontend runs on a separate Vite origin during local development. Keep
# this browser permission narrow: no credentials, no arbitrary origins, and
# only the methods/headers used by the product UI.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)

install_exception_handlers(app)
app.include_router(api_router)
