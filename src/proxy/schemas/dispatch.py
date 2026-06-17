from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DispatchRequest(BaseModel):
    operation_type: str = Field(alias="operationType", min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = Field(default=None, alias="requestId")

    model_config = {"populate_by_name": True}
