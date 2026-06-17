from __future__ import annotations

from pydantic import BaseModel, Field


class EmptyPayload(BaseModel):
    """For operations that take no parameters (e.g. ListLeagues)."""

    model_config = {"extra": "forbid"}


class GetLeagueMatchesPayload(BaseModel):
    league_shortcut: str = Field(alias="leagueShortcut", min_length=1)
    season: str = Field(min_length=1)

    model_config = {"populate_by_name": True, "extra": "forbid"}


class GetTeamPayload(BaseModel):
    team_id: int = Field(alias="teamId", gt=0)
    league_shortcut: str = Field(alias="leagueShortcut", min_length=1)
    season: str = Field(min_length=1)

    model_config = {"populate_by_name": True, "extra": "forbid"}


class GetMatchPayload(BaseModel):
    match_id: int = Field(alias="matchId", gt=0)

    model_config = {"populate_by_name": True, "extra": "forbid"}
