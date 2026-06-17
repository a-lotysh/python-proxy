from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import httpx
import pytest
from asgi_lifespan import LifespanManager  # type: ignore[import-not-found]

from proxy.core.http_client import UpstreamClient
from proxy.core.ratelimit import RateLimiter
from proxy.main import create_app


def make_transport(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


async def build_client(transport: httpx.MockTransport) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()

    async with LifespanManager(app):
        # Replace the real upstream client's transport with the mock; disable
        # rate limiting so tests run without artificial delays.
        mock_httpx = httpx.AsyncClient(transport=transport, base_url="https://www.openligadb.de")
        app.state.upstream_client = UpstreamClient(mock_httpx, RateLimiter(0))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
        await mock_httpx.aclose()


@pytest.fixture
async def success_client() -> AsyncIterator[httpx.AsyncClient]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/getavailableleagues":
            return httpx.Response(
                200, json=[{"leagueId": 1, "leagueName": "Bundesliga", "leagueShortcut": "bl1"}]
            )
        if request.url.path == "/api/getmatchdata/bl1/2023":
            return httpx.Response(200, json=[{"matchID": 100}])
        if request.url.path == "/api/getmatchdata/100":
            return httpx.Response(
                200,
                json={
                    "matchID": 100,
                    "team1": {"teamId": 7, "teamName": "FC X"},
                    "team2": {"teamId": 8, "teamName": "FC Y"},
                    "matchResults": [{"pointsTeam1": 2, "pointsTeam2": 1}],
                },
            )
        if request.url.path == "/api/getavailableteams/bl1/2023":
            return httpx.Response(200, json=[{"teamId": 7, "teamName": "FC X"}])
        return httpx.Response(404, json={})

    async for c in build_client(make_transport(handler)):
        yield c


async def test_list_leagues(success_client: httpx.AsyncClient) -> None:
    resp = await success_client.post(
        "/proxy/execute", json={"operationType": "ListLeagues", "payload": {}}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["operationType"] == "ListLeagues"
    # Normalised output: leagueName -> name.
    assert body["data"][0]["name"] == "Bundesliga"
    assert body["data"][0]["shortcut"] == "bl1"
    assert "requestId" in body
    assert resp.headers["x-request-id"]


async def test_get_match_normalised(success_client: httpx.AsyncClient) -> None:
    resp = await success_client.post(
        "/proxy/execute", json={"operationType": "GetMatch", "payload": {"matchId": 100}}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["matchId"] == 100
    assert data["team1"]["name"] == "FC X"
    assert data["goalsTeam1"] == 2
    assert data["goalsTeam2"] == 1


async def test_get_team_selects_by_id(success_client: httpx.AsyncClient) -> None:
    resp = await success_client.post(
        "/proxy/execute",
        json={
            "operationType": "GetTeam",
            "payload": {"teamId": 7, "leagueShortcut": "bl1", "season": "2023"},
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "FC X"


async def test_unknown_operation(success_client: httpx.AsyncClient) -> None:
    resp = await success_client.post(
        "/proxy/execute", json={"operationType": "Nope", "payload": {}}
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "unknown_operation"
    assert "GetMatch" in body["details"]["allowed"]


async def test_payload_validation_error(success_client: httpx.AsyncClient) -> None:
    resp = await success_client.post(
        "/proxy/execute",
        json={"operationType": "GetMatch", "payload": {"matchId": -5}},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "validation_error"
    assert body["details"]


async def test_request_id_passthrough(success_client: httpx.AsyncClient) -> None:
    resp = await success_client.post(
        "/proxy/execute",
        json={"operationType": "ListLeagues", "payload": {}, "requestId": "custom-123"},
    )
    assert resp.json()["requestId"] == "custom-123"


@pytest.fixture
async def failing_client() -> AsyncIterator[httpx.AsyncClient]:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    async for c in build_client(make_transport(handler)):
        yield c


async def test_upstream_failure_after_retries(failing_client: httpx.AsyncClient) -> None:
    resp = await failing_client.post(
        "/proxy/execute", json={"operationType": "GetMatch", "payload": {"matchId": 1}}
    )
    assert resp.status_code == 502
    body = resp.json()
    assert body["error"] == "upstream_failed"
    assert body["message"] == "Upstream API failed"
