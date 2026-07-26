"""Return the same safe JSON error shape from every API route.

Application services may raise detailed exceptions that are useful in logs but
not safe or useful for the browser. The route layer raises ``PublicApiError``
subclasses with a status code, a short machine-readable code, and a simple
message for the user.

``install_exception_handlers`` also handles request-validation errors, normal
FastAPI ``HTTPException`` values, and unexpected failures. Unexpected details
are logged on the server, while the response stays generic and never exposes a
traceback, API key, or provider response.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


class PublicApiError(RuntimeError):
    """An expected API failure whose message is safe to show to the browser."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.public_message = message
        super().__init__(message)


class ApiNotFoundError(PublicApiError):
    """A requested candidate or CV could not be found."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(404, code, message)


class ApiServiceUnavailableError(PublicApiError):
    """A local dependency, such as the vector index, is not ready."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(503, code, message)


class ApiUpstreamError(PublicApiError):
    """A hosted provider was configured but failed to answer the request."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(502, code, message)


def install_exception_handlers(app: FastAPI) -> None:
    """Register all shared error handlers on the FastAPI application.

    The browser always receives this shape::

        {"error": {"code": "...", "message": "...", "details": []}}

    Validation failures may include safe field-level details. Unexpected errors
    are logged with their traceback but return only a generic message.
    """

    @app.exception_handler(PublicApiError)
    async def handle_public_error(
        _: Request,
        error: PublicApiError,
    ) -> JSONResponse:
        """Return an expected application error exactly as the route defined it."""

        return _error_response(
            error.status_code,
            error.code,
            error.public_message,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        """Turn Pydantic/FastAPI validation errors into simple field messages."""

        details = [
            {
                "field": ".".join(str(part) for part in item["loc"] if part != "body"),
                "message": item["msg"],
            }
            for item in error.errors()
        ]
        return _error_response(
            422,
            "validation_error",
            "Request validation failed.",
            details=details,
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(
        _: Request,
        error: HTTPException,
    ) -> JSONResponse:
        """Keep normal FastAPI HTTP errors inside the same response format."""

        message = error.detail if isinstance(error.detail, str) else "Request failed."
        return _error_response(
            error.status_code,
            "http_error",
            message,
            headers=error.headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request,
        error: Exception,
    ) -> JSONResponse:
        """Log unexpected details server-side and return a safe generic message."""

        logger.exception(
            "Unhandled API error for %s %s",
            request.method,
            request.url.path,
            exc_info=error,
        )
        return _error_response(
            500,
            "internal_error",
            "The server could not complete the request.",
        )


def _error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build the standard JSON response used by all error handlers."""

    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details:
        payload["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=payload, headers=headers)
