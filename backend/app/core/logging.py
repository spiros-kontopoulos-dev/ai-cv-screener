"""Set one logging format and log level for the whole backend.

Every module creates its own logger with ``logging.getLogger(__name__)``. This
file configures the shared root logger once when FastAPI starts.
"""

import logging


# Example:
# 2026-07-17 14:30:00 | INFO | app.main | Starting AI CV Screener API
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging(log_level: str) -> None:
    """Apply the requested log level to all backend loggers.

    ``log_level`` normally comes from the ``LOG_LEVEL`` environment variable.
    Unknown values fall back to ``INFO`` so a spelling mistake does not stop
    the application from starting.

    ``force=True`` replaces logging that Uvicorn may have configured before it
    imported the application.
    """

    resolved_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=resolved_level,
        format=LOG_FORMAT,
        force=True,
    )
