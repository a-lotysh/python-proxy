from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from proxy.core.logging import log_event, redact_headers

REQUEST_ID_HEADER = "x-request-id"

_Next = Callable[[Request], Awaitable[Response]]


class RecordingMiddleware(BaseHTTPMiddleware):
    """Logs inbound request and outbound response metadata, correlated by requestId.

    The requestId is taken from the X-Request-Id header if present, otherwise
    generated, and stored on request.state so handlers and error handlers reuse it.
    """

    async def dispatch(self, request: Request, call_next: _Next) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:16]
        request.state.request_id = request_id

        body = await request.body()  # cached by Starlette for downstream handlers
        log_event(
            "request_in",
            requestId=request_id,
            method=request.method,
            path=request.url.path,
            headers=_headers_str(dict(request.headers)),
            bodySize=len(body),
        )

        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = (time.perf_counter() - start) * 1000

        response.headers[REQUEST_ID_HEADER] = request_id
        log_event(
            "request_out",
            requestId=request_id,
            status=response.status_code,
            bodySize=int(response.headers.get("content-length", 0) or 0),
            latency_ms=round(latency_ms, 1),
        )
        return response


def _headers_str(headers: dict[str, str]) -> str:
    redacted = redact_headers(headers)
    return ",".join(f"{k}:{v}" for k, v in redacted.items())
