from __future__ import annotations

from collections.abc import Callable

from proxy.core.http_client import UpstreamClient
from proxy.providers.base import SportsProvider
from proxy.providers.openligadb import OpenLigaDBProvider

# Provider selection is configurable: add an adapter factory here and point
# settings.provider_name at it to swap the upstream without other changes.
_PROVIDERS: dict[str, Callable[[UpstreamClient], SportsProvider]] = {
    "openligadb": OpenLigaDBProvider,
}


def build_provider(name: str, client: UpstreamClient) -> SportsProvider:
    factory = _PROVIDERS.get(name)
    if factory is None:
        raise ValueError(f"Unknown provider: {name!r}. Available: {sorted(_PROVIDERS)}")
    return factory(client)
