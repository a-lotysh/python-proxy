from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

from pydantic import BaseModel, ValidationError

from proxy.core.exceptions import PayloadValidationError, UnknownOperationError, jsonable_errors
from proxy.providers.base import SportsProvider
from proxy.schemas.operations import (
    EmptyPayload,
    GetLeagueMatchesPayload,
    GetMatchPayload,
    GetTeamPayload,
)

_Call = Callable[[SportsProvider, BaseModel, str], Awaitable[Any]]


@dataclass(frozen=True)
class Operation:
    """One row of the decision map: which schema validates the payload and
    which provider method serves it."""

    input_schema: type[BaseModel]
    call: _Call


async def _list_leagues(p: SportsProvider, _: BaseModel, rid: str) -> Any:
    return await p.list_leagues(request_id=rid)


async def _league_matches(p: SportsProvider, payload: BaseModel, rid: str) -> Any:
    m = cast(GetLeagueMatchesPayload, payload)
    return await p.get_league_matches(
        league_shortcut=m.league_shortcut, season=m.season, request_id=rid
    )


async def _team(p: SportsProvider, payload: BaseModel, rid: str) -> Any:
    m = cast(GetTeamPayload, payload)
    return await p.get_team(
        team_id=m.team_id, league_shortcut=m.league_shortcut, season=m.season, request_id=rid
    )


async def _match(p: SportsProvider, payload: BaseModel, rid: str) -> Any:
    m = cast(GetMatchPayload, payload)
    return await p.get_match(match_id=m.match_id, request_id=rid)


OPERATIONS: dict[str, Operation] = {
    "ListLeagues": Operation(EmptyPayload, _list_leagues),
    "GetLeagueMatches": Operation(GetLeagueMatchesPayload, _league_matches),
    "GetTeam": Operation(GetTeamPayload, _team),
    "GetMatch": Operation(GetMatchPayload, _match),
}


def all_operations() -> list[str]:
    return sorted(OPERATIONS)


def resolve(operation_type: str) -> Operation:
    op = OPERATIONS.get(operation_type)
    if op is None:
        raise UnknownOperationError(operation_type, allowed=all_operations())
    return op


def validate_payload(op: Operation, raw: dict[str, Any]) -> BaseModel:
    try:
        return op.input_schema.model_validate(raw)
    except ValidationError as exc:
        raise PayloadValidationError(jsonable_errors(exc.errors())) from exc
