from __future__ import annotations

import json
import sys
from typing import Any

from proxy.core.config import settings

# Header names that must never be logged in clear.
_SENSITIVE_HEADERS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
    "x-auth-token",
}
_REDACTED = "***REDACTED***"


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return a copy of headers with sensitive values masked."""
    out: dict[str, str] = {}
    for key, value in headers.items():
        out[key] = _REDACTED if key.lower() in _SENSITIVE_HEADERS else value
    return out


def truncate(text: str, limit: int | None = None) -> str:
    """Truncate a string to the first N chars, marking that it was cut."""
    limit = settings.log_body_max_chars if limit is None else limit
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...<truncated {len(text) - limit} chars>"


def _scalar(value: Any) -> str:
    """Render a value for key=value output, quoting when needed."""
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    s = str(value)
    if any(c in s for c in (" ", "=", '"', "\n")):
        return json.dumps(s, ensure_ascii=False)
    return s


def log_event(event: str, **fields: Any) -> None:
    """Emit a single structured log line to stdout as key=value pairs.

    Example:
        event=upstream_call requestId=ab12 operationType=GetMatch status=200 latency_ms=42.1
    """
    parts = [f"event={event}"]
    parts.extend(f"{key}={_scalar(val)}" for key, val in fields.items())
    sys.stdout.write(" ".join(parts) + "\n")
    sys.stdout.flush()
