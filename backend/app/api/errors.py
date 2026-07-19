"""Safe, consistent HTTP error mapping for the public API."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


class PublicApiError(RuntimeError):
    """An expected failure with a safe client-facing status and message."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.public_message = message
        super().__init__(message)


class ApiNotFoundError(PublicApiError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(404, code, message)


class ApiServiceUnavailableError(PublicApiError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(503, code, message)


class ApiUpstreamError(PublicApiError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(502, code, message)


def install_exception_handlers(app: FastAPI) -> None:
    """Install handlers that never expose provider secrets or tracebacks."""

    @app.exception_handler(PublicApiError)
    async def handle_public_error(
        _: Request,
        error: PublicApiError,
    ) -> JSONResponse:
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
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details:
        payload["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=payload, headers=headers)
