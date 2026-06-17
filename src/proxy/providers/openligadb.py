from __future__ import annotations

from typing import Any

from proxy.core.exceptions import UpstreamError
from proxy.core.http_client import UpstreamClient
from proxy.providers.base import SportsProvider

_GET_TEAM = "GetTeam"
_GET_MATCH = "GetMatch"
_LIST_LEAGUES = "ListLeagues"
_GET_LEAGUE_MATCHES = "GetLeagueMatches"


class OpenLigaDBProvider(SportsProvider):
    """OpenLigaDB adapter. All OpenLigaDB-specific URLs, params and response
    field names are isolated here; callers get the normalised output schema."""

    def __init__(self, client: UpstreamClient) -> None:
        self._client = client

    async def list_leagues(self, *, request_id: str) -> list[dict[str, Any]]:
        data = await self._client.get_json(
            "/api/getavailableleagues", request_id=request_id, operation_type=_LIST_LEAGUES
        )
        return [_league(item) for item in _as_list(data)]

    async def get_league_matches(
        self, *, league_shortcut: str, season: str, request_id: str
    ) -> list[dict[str, Any]]:
        data = await self._client.get_json(
            f"/api/getmatchdata/{league_shortcut}/{season}",
            request_id=request_id,
            operation_type=_GET_LEAGUE_MATCHES,
        )
        return [_match(item) for item in _as_list(data)]

    async def get_team(
        self, *, team_id: int, league_shortcut: str, season: str, request_id: str
    ) -> dict[str, Any]:
        # OpenLigaDB has no stable get-team-by-id endpoint, so we fetch the
        # league/season teams and select the requested id.
        data = await self._client.get_json(
            f"/api/getavailableteams/{league_shortcut}/{season}",
            request_id=request_id,
            operation_type=_GET_TEAM,
        )
        for item in _as_list(data):
            if isinstance(item, dict) and item.get("teamId") == team_id:
                return _team(item)
        raise UpstreamError(
            "Upstream API failed", details={"reason": "team_not_found", "teamId": team_id}
        )

    async def get_match(self, *, match_id: int, request_id: str) -> dict[str, Any]:
        data = await self._client.get_json(
            f"/api/getmatchdata/{match_id}", request_id=request_id, operation_type=_GET_MATCH
        )
        if isinstance(data, list):  # some match endpoints return a single-item list
            data = data[0] if data else {}
        return _match(data)


# --- normalisers: OpenLigaDB fields -> stable output schema -------------------


def _as_list(data: Any) -> list[Any]:
    return data if isinstance(data, list) else []


def _league(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "leagueId": item.get("leagueId"),
        "name": item.get("leagueName"),
        "shortcut": item.get("leagueShortcut"),
        "season": item.get("leagueSeason"),
    }


def _team(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "teamId": item.get("teamId"),
        "name": item.get("teamName"),
        "shortName": item.get("shortName"),
        "iconUrl": item.get("teamIconUrl"),
    }


def _match(item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    results = item.get("matchResults") or []
    final = results[-1] if results else {}
    return {
        "matchId": item.get("matchID"),
        "date": item.get("matchDateTime"),
        "finished": item.get("matchIsFinished"),
        "team1": _team(item.get("team1", {})),
        "team2": _team(item.get("team2", {})),
        "goalsTeam1": final.get("pointsTeam1"),
        "goalsTeam2": final.get("pointsTeam2"),
    }
