"""
Application logging configuration.

This module keeps the logging setup in one place so every backend module
uses the same log level and message format.
"""

import logging


# Define one consistent format for all backend log messages.
#
# Example output:
# 2026-07-17 14:30:00 | INFO | app.main | Starting AI CV Screener API
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging(log_level: str) -> None:
    """
    Configure Python's root logger for the application.

    Args:
        log_level:
            A text value such as "DEBUG", "INFO", "WARNING", or "ERROR".
            The value comes from the LOG_LEVEL environment variable.
    """

    # Convert the text value, such as "INFO", into Python's numeric logging
    # constant, such as logging.INFO.
    #
    # If an invalid value is supplied, the application safely falls back
    # to INFO instead of failing during startup.
    resolved_level = getattr(
        logging,
        log_level.upper(),
        logging.INFO,
    )

    # basicConfig configures the root logger used by the whole application.
    #
    # force=True replaces any earlier logging configuration. This is useful
    # because Uvicorn may configure logging before importing our application.
    logging.basicConfig(
        level=resolved_level,
        format=LOG_FORMAT,
        force=True,
    )