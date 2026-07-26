"""Create and configure the FastAPI application.

This is the backend starting point. Uvicorn imports ``app`` from this file.
The setup happens in this order:

1. Load the shared settings.
2. Configure logging when the server starts.
3. Create the FastAPI application.
4. Allow the local React frontend to call the API.
5. Install the shared error handlers.
6. Attach all routes under the ``/api`` prefix.

This file only connects the main parts of the backend. The real candidate
search and answer logic stays in the service modules.
"""

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
    """Run the small amount of work needed at server start and shutdown.

    FastAPI enters this function before it accepts requests. Logging is set up
    first so every later module uses the same format and log level. Code after
    ``yield`` runs when the server is stopping.
    """

    configure_logging(settings.log_level)
    logger.info("Starting %s in %s environment", settings.app_name, settings.app_env)
    yield
    logger.info("Stopping %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version="0.8.0",
    description=(
        "HTTP API for candidate search, grounded answers, source details, "
        "and CV access."
    ),
    lifespan=lifespan,
)

# React and FastAPI run on different local ports, so the browser needs CORS
# permission. Only the configured frontend origin and the methods used by this
# application are allowed. API keys are never sent to the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)

# Use one error format across every route, then attach the public API routes.
install_exception_handlers(app)
app.include_router(api_router)
