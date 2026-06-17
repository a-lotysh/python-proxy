from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from proxy.core.logging import log_event


class ProxyError(Exception):
    """Base class for domain errors that map to a structured HTTP response."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class UnknownOperationError(ProxyError):
    status_code = 400
    error_code = "unknown_operation"

    def __init__(self, operation_type: str, allowed: list[str]) -> None:
        super().__init__(
            f"Unknown operationType: {operation_type!r}",
            details={"allowed": allowed},
        )
        self.operation_type = operation_type


class PayloadValidationError(ProxyError):
    status_code = 400
    error_code = "validation_error"

    def __init__(self, errors: Any) -> None:
        super().__init__("Payload validation failed", details=errors)


class UpstreamError(ProxyError):
    status_code = 502
    error_code = "upstream_failed"

    def __init__(self, message: str = "Upstream API failed", details: Any | None = None) -> None:
        super().__init__(message, details=details)


def _error_body(
    error_code: str, message: str, request_id: str, details: Any | None
) -> dict[str, Any]:
    body: dict[str, Any] = {"error": error_code, "message": message, "requestId": request_id}
    if details is not None:
        body["details"] = details
    return body


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProxyError)
    async def _proxy_error(request: Request, exc: ProxyError) -> JSONResponse:
        rid = _request_id(request)
        log_event(
            "request_error",
            requestId=rid,
            error=exc.error_code,
            status=exc.status_code,
            message=exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.error_code, exc.message, rid, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _body_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Top-level request body (e.g. missing operationType) failed to parse.
        rid = _request_id(request)
        log_event("request_error", requestId=rid, error="validation_error", status=400)
        return JSONResponse(
            status_code=400,
            content=_error_body(
                "validation_error",
                "Request body validation failed",
                rid,
                jsonable_errors(exc.errors()),
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        rid = _request_id(request)
        log_event(
            "request_error",
            requestId=rid,
            error="internal_error",
            status=500,
            message=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content=_error_body("internal_error", "Internal server error", rid, None),
        )


def jsonable_errors(errors: Any) -> Any:
    """Pydantic/Starlette validation errors may contain non-serialisable ctx values."""
    safe: list[dict[str, Any]] = []
    for err in errors:
        safe.append(
            {
                "loc": list(err.get("loc", [])),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
        )
    return safe
