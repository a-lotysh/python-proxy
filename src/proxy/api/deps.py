from __future__ import annotations

from starlette.requests import Request

from proxy.core.config import settings
from proxy.providers.base import SportsProvider
from proxy.providers.registry import build_provider


def get_provider(request: Request) -> SportsProvider:
    client = request.app.state.upstream_client
    return build_provider(settings.provider_name, client)
