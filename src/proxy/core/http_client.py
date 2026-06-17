from __future__ import annotations

import asyncio
import random
import time
from typing import Any

import httpx

from proxy.core.config import settings
from proxy.core.exceptions import UpstreamError
from proxy.core.logging import log_event
from proxy.core.ratelimit import RateLimiter

# Status codes worth retrying (transient upstream conditions).
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class UpstreamClient:
    """httpx.AsyncClient wrapper adding rate limiting, retries with jittered
    exponential backoff, and audit logging. Provider-agnostic: it knows nothing
    about OpenLigaDB endpoints — adapters pass fully-formed paths."""

    def __init__(self, client: httpx.AsyncClient, limiter: RateLimiter | None = None) -> None:
        self._client = client
        self._limiter = limiter or RateLimiter(settings.upstream_rate_per_sec)

    async def get_json(self, path: str, *, request_id: str, operation_type: str) -> Any:
        url = f"{settings.provider_base_url}{path}"
        attempts = settings.upstream_max_retries
        last_status: int | None = None
        last_error: str | None = None

        for attempt in range(1, attempts + 1):
            await self._limiter.acquire()
            start = time.perf_counter()
            try:
                resp = await self._client.get(url)
            except httpx.RequestError as exc:
                latency_ms = (time.perf_counter() - start) * 1000
                last_error = type(exc).__name__
                log_event(
                    "upstream_call",
                    requestId=request_id,
                    operationType=operation_type,
                    provider=settings.provider_name,
                    targetUrl=url,
                    attempt=attempt,
                    status="-",
                    latency_ms=round(latency_ms, 1),
                    outcome="transport_error",
                    error=last_error,
                )
            else:
                latency_ms = (time.perf_counter() - start) * 1000
                last_status = resp.status_code
                retryable = resp.status_code in _RETRYABLE_STATUS
                log_event(
                    "upstream_call",
                    requestId=request_id,
                    operationType=operation_type,
                    provider=settings.provider_name,
                    targetUrl=url,
                    attempt=attempt,
                    status=resp.status_code,
                    latency_ms=round(latency_ms, 1),
                    outcome="retryable_status" if retryable else "completed",
                )
                if not retryable:
                    if resp.is_success:
                        return _parse_json(resp)
                    # Non-retryable error status -> fail fast.
                    raise UpstreamError(
                        "Upstream API failed",
                        details={"status": resp.status_code, "url": url},
                    )

            if attempt < attempts:
                await asyncio.sleep(_backoff_delay(attempt))

        # Exhausted retries.
        raise UpstreamError(
            "Upstream API failed",
            details={"status": last_status, "error": last_error, "url": url, "attempts": attempts},
        )


def _backoff_delay(attempt: int) -> float:
    """Exponential backoff (base * 2^(n-1)) with full jitter."""
    ceiling = settings.upstream_backoff_base_s * (2 ** (attempt - 1))
    return random.uniform(0, ceiling)


def _parse_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError as exc:
        raise UpstreamError(
            "Upstream API failed", details={"reason": "invalid_json", "error": str(exc)}
        ) from exc
