"""
FastAPI application entry point.

Uvicorn imports the `app` object from this module when the backend container
starts with:

    uvicorn app.main:app
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging



# Create a logger named after this module: "app.main".
logger = logging.getLogger(__name__)


# Load the validated and cached application settings.
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """
    Run application startup and shutdown logic.

    Code before `yield` runs during startup.
    Code after `yield` runs during shutdown.
    """

    configure_logging(settings.log_level)

    logger.info(
        "Starting %s in %s environment",
        settings.app_name,
        settings.app_env,
    )

    # FastAPI serves requests while execution is paused here.
    yield

    logger.info("Stopping %s", settings.app_name)


# Create the main FastAPI application.
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# Configure Cross-Origin Resource Sharing.
#
# During local development, the React frontend and FastAPI backend run on
# different ports. Browsers treat them as different origins, so FastAPI must
# explicitly allow the configured frontend origin to make API requests.
app.add_middleware(
    CORSMiddleware,

    # Only the configured frontend address may call the backend from a browser.
    allow_origins=[settings.frontend_origin],

    # The current application does not use browser cookies or authentication.
    allow_credentials=False,

    # Allow standard HTTP methods such as GET, POST, and OPTIONS.
    allow_methods=["*"],

    # Allow the frontend to send headers such as Content-Type.
    allow_headers=["*"],
)


# Attach all routes collected by the central API router.
app.include_router(api_router)