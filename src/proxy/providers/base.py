from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SportsProvider(ABC):
    """Provider-agnostic interface for a sports-data source.

    The decision mapper and proxy depend only on this interface. To support a
    different upstream, implement these four methods in a new adapter and
    register it in ``providers/registry.py`` — no proxy/mapper changes needed.

    Every method returns data already normalised to this service's stable
    output schema; provider-specific URLs, params and field names stay inside
    the adapter.
    """

    @abstractmethod
    async def list_leagues(self, *, request_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_league_matches(
        self, *, league_shortcut: str, season: str, request_id: str
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_team(
        self, *, team_id: int, league_shortcut: str, season: str, request_id: str
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def get_match(self, *, match_id: int, request_id: str) -> dict[str, Any]: ...
