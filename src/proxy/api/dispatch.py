from __future__ import annotations

import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from starlette.requests import Request

from proxy.api.deps import get_provider
from proxy.core.config import settings
from proxy.core.exceptions import PayloadValidationError, ProxyError
from proxy.core.logging import log_event
from proxy.mapper import resolve, validate_payload
from proxy.providers.base import SportsProvider
from proxy.schemas.dispatch import DispatchRequest

router = APIRouter()


@router.post("/proxy/execute")
async def execute(
    body: DispatchRequest,
    request: Request,
    provider: Annotated[SportsProvider, Depends(get_provider)],
) -> dict[str, Any]:
    # requestId: prefer body, then middleware-assigned, then '-'.
    request_id: str = body.request_id or str(getattr(request.state, "request_id", "-"))
    request.state.request_id = request_id
    op_type = body.operation_type

    log_event("audit_start", requestId=request_id, operationType=op_type, timestamp=time.time())

    # 1. Route by operationType (raises UnknownOperationError -> 400).
    operation = resolve(op_type)

    # 2. Validate payload (raises PayloadValidationError -> 400).
    try:
        payload = validate_payload(operation, body.payload)
    except PayloadValidationError as exc:
        log_event(
            "audit_validation",
            requestId=request_id,
            operationType=op_type,
            outcome="fail",
            reasons=_reasons(exc.details),
        )
        raise

    log_event("audit_validation", requestId=request_id, operationType=op_type, outcome="pass")

    # 3. Invoke the provider adapter; it returns the normalised response.
    try:
        data = await operation.call(provider, payload, request_id)
    except ProxyError as exc:
        log_event(
            "audit_end",
            requestId=request_id,
            operationType=op_type,
            provider=settings.provider_name,
            outcome="error",
            errorCode=exc.error_code,
            status=exc.status_code,
        )
        raise

    log_event(
        "audit_end",
        requestId=request_id,
        operationType=op_type,
        provider=settings.provider_name,
        outcome="success",
    )
    return {"requestId": request_id, "operationType": op_type, "data": data}


def _reasons(details: Any) -> str:
    if isinstance(details, list):
        return ";".join(
            f"{'.'.join(str(p) for p in d.get('loc', []))}:{d.get('msg', '')}" for d in details
        )
    return str(details)
