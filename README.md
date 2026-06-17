# moonshot-proxy

Tiny reverse proxy over external sports APIs. One endpoint validates input,
routes by `operationType`, calls a pluggable provider adapter (OpenLigaDB), and
returns a normalized response — with structured audit logging, request/response
middleware, rate limiting, and retries with jittered exponential backoff.

## Run

```bash
make install        # uv sync
make dev            # uvicorn --reload
# or: pip install -e . && uvicorn proxy.main:app --reload --app-dir src
```

## Endpoint

`POST /proxy/execute`

```json
{ "operationType": "GetMatch", "payload": { "matchId": 12345 }, "requestId": "optional" }
```

→ `{ "requestId": "...", "operationType": "GetMatch", "data": { ... } }`

## Operations

| operationType      | payload                                              | normalized response |
|--------------------|-----------------------------------------------------|---------------------|
| `ListLeagues`      | `{}`                                                | list of `{leagueId, name, shortcut, season}` |
| `GetLeagueMatches` | `{leagueShortcut, season}`                          | list of matches (see below) |
| `GetTeam`          | `{teamId, leagueShortcut, season}`                  | `{teamId, name, shortName, iconUrl}` |
| `GetMatch`         | `{matchId}`                                         | `{matchId, date, finished, team1, team2, goalsTeam1, goalsTeam2}` |

```bash
curl -s localhost:8000/proxy/execute -d '{"operationType":"GetMatch","payload":{"matchId":12345}}'
```

## How it works

- **Decision mapper** (`mapper.py`): a table mapping each `operationType` to its
  validation schema + provider method. Dispatch = resolve → validate → call.
- **Adapter** (`providers/`): `SportsProvider` interface; `OpenLigaDBProvider`
  implements it with all OpenLigaDB URLs + response normalization isolated
  inside. Swap providers via `PROVIDER_NAME` (registered in `providers/registry.py`).
- **Upstream client** (`core/http_client.py`): rate limiting + retries with
  jittered exponential backoff, plus audit logging per call.

## Config

Env vars / `.env` (defaults in `core/config.py`):

| var | default | meaning |
|-----|---------|---------|
| `PROVIDER_NAME` / `PROVIDER_BASE_URL` | `openligadb` / openligadb.de | provider selection + host |
| `UPSTREAM_RATE_PER_SEC` | `5.0` | max upstream req/s (0 = off) |
| `UPSTREAM_MAX_RETRIES` | `3` | retries on 429/5xx/timeout |
| `UPSTREAM_BACKOFF_BASE_S` | `0.2` | backoff base: `base * 2^(n-1)` + jitter |

## Errors

`{ "error": "...", "message": "...", "requestId": "...", "details": [...] }`

- Unknown `operationType` → `400 unknown_operation`
- Payload validation failure → `400 validation_error`
- Upstream failure after retries → `502 upstream_failed` (`Upstream API failed`)

## Logging

Structured `key=value` lines to stdout, correlated by `requestId` (from body →
`X-Request-Id` header → generated). Sensitive headers redacted; bodies truncated.

```
event=request_in requestId=ab12 method=POST path=/proxy/execute headers=authorization:***REDACTED*** bodySize=58
event=audit_validation requestId=ab12 operationType=GetMatch outcome=pass
event=upstream_call requestId=ab12 operationType=GetMatch provider=openligadb targetUrl=.../api/getmatchdata/100 attempt=1 status=200 latency_ms=42.1 outcome=completed
event=audit_end requestId=ab12 operationType=GetMatch provider=openligadb outcome=success
event=request_out requestId=ab12 status=200 bodySize=180 latency_ms=44.0
```

## Dev

```bash
make test           # pytest (upstream mocked)
make lint           # ruff
make typecheck      # mypy --strict
```
