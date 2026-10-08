# wos-events MCP server

An [MCP](https://modelcontextprotocol.io) server in front of the wos-events HTTP API, for Claude/agents now
and Discord bots later. Code: `mcp/` (package `wos_mcp`). It talks to the app **only** through the HTTP API in
[API.md](API.md) — never the database — so every write goes through the backend's validation.

- SDK: official `mcp` Python SDK, pinned `mcp==2.3.0` (current as of Oct 2026). In mcp 2.x `FastMCP` was renamed
  `MCPServer` (`from mcp.server.mcpserver import MCPServer`); `mcp.server.fastmcp` no longer exists. Other projects
  on this machine pin `mcp<2` for that reason; this one targets 2.x deliberately. Upgrade by changing the pin and
  re-running the tests.
- Transport: streamable HTTP, **stateless** with JSON responses (no server-side sessions, so any number of Cloud Run
  instances work). Negotiates protocol 2026-07-28 with 2.x clients and the initialize handshake (2025-03-26 …
  2025-11-25) with older clients such as Claude Code; both are tested.
- Python 3.11+ (image: `python:3.11-slim`; tests pass on 3.11 and 3.14).

## Endpoints and authorisation

| Path | Tools | Auth |
|---|---|---|
| `POST /mcp` | public tools only | none, or `Authorization: Bearer $MCP_PUBLIC_BEARER_TOKEN` if that is set |
| `POST /admin/mcp` | public **+ admin** tools | `Authorization: Bearer $MCP_BEARER_TOKEN` (a bare token is also accepted) |
| `GET /health` | – | none; `{"status": "healthy", "admin_enabled": bool}` |

**Design (recommended option: separate admin endpoint + bearer header).**

1. Admin tools are registered only on a second MCP server mounted at `/admin/mcp`. On `/mcp` they are not listed
   and calling one fails as "unknown tool", so a public client (or a prompt-injected model on it) cannot even see
   them.
2. Every HTTP request to `/admin/mcp` must carry `Authorization: Bearer <MCP_BEARER_TOKEN>`; it is checked with a
   constant-time compare *before* the MCP layer, on every request (the transport is stateless, so there is no
   session to hijack). Missing/wrong → HTTP 401 `{"code": "UNAUTHORIZED"}`.
3. Defence in depth: each admin tool re-checks the same header from the request context and returns a 401
   tool error if it doesn't match.
4. If `MCP_BEARER_TOKEN` is unset or shorter than 32 characters the admin endpoint is **disabled** (HTTP 503
   `ADMIN_DISABLED`); public tools keep working.
5. The MCP server holds the app's admin password (`WOS_ADMIN_PASSWORD`) itself. It logs in lazily
   (`POST /api/admin/login`), caches the signed token in memory, refreshes it 5 minutes before the 12 h expiry,
   and re-logs in once if the API answers 401 `TOKEN_EXPIRED`/`INVALID_TOKEN` (e.g. backend restarted with a new
   key). Callers never see the password or the API token. A failed login returns `ADMIN_LOGIN_FAILED` without
   detail; an unset password returns `ADMIN_NOT_CONFIGURED`.

Why not one endpoint with an auth header that unlocks admin tools? It works, but the tool list would then depend
on a header, every admin tool would rely solely on its own per-call check, and a misconfigured client could see
admin tools it can't use. Two paths make the boundary structural and easy to reason about (and easy to put behind
separate Cloud Run ingress/IAM later). OAuth (the SDK supports it) is the upgrade path once there are real
per-user identities.

The admin bearer is a **shared secret**: anyone holding it acts as the app admin. The backend sees every MCP admin
call as role `admin` (no per-user audit yet — see [BACKEND_ISSUES.md](BACKEND_ISSUES.md)).

## Configuration (env)

| Variable | Required | Meaning |
|---|---|---|
| `WOS_API_BASE` | yes | API base URL, e.g. `http://127.0.0.1:8094` (no trailing `/api`) |
| `MCP_BEARER_TOKEN` | for admin | ≥32 chars; clients send it on `/admin/mcp`. Generate: `python -c "import secrets;print(secrets.token_urlsafe(32))"` |
| `WOS_ADMIN_PASSWORD` | for admin | the app's `ADMIN_PASSWORD`; used server-side to obtain/refresh the signed admin token |
| `MCP_PUBLIC_BEARER_TOKEN` | no | if set, `/mcp` also requires a bearer. **Recommended in production** (see Safety) |
| `MCP_HOST` / `MCP_PORT` | no | bind address (default `127.0.0.1` / `8094`; falls back to `PORT` for Cloud Run) |
| `MCP_RATE_LIMIT_PER_MINUTE` | no | per-client HTTP requests/min on the MCP paths (default 120, `0` = off); excess → 429 `RATE_LIMITED` |
| `MCP_TRUST_PROXY` | no | `1` = rate-limit by the right-most `X-Forwarded-For` hop (Cloud Run); default off |
| `MCP_ALLOWED_HOSTS` | no | comma-separated Host values for DNS-rebinding protection (auto-on for 127.0.0.1 binds; set it when binding 0.0.0.0, e.g. `wos-events-mcp-xxxx.a.run.app`) |
| `WOS_API_TIMEOUT_SECONDS` | no | API call timeout (default 15) |

## Run locally

```bash
cd wos-events-wt/mcp-server            # or the main checkout
# 1. backend on 8094 (temp DB, dev mode)
cd backend && FLASK_ENV=development ADMIN_PASSWORD=change-me DATABASE_PATH=/tmp/wos-mcp-dev.db \
   PORT=8094 venv/bin/python app.py &           # or: docker compose on another port
cd ..
# 2. MCP server on 8095
python3 -m venv mcp/.venv && mcp/.venv/bin/pip install -r mcp/requirements.txt
export WOS_API_BASE=http://127.0.0.1:8094 MCP_PORT=8095 WOS_ADMIN_PASSWORD=change-me
export MCP_BEARER_TOKEN=$(python3 -c "import secrets;print(secrets.token_urlsafe(32))")
cd mcp && .venv/bin/python -m wos_mcp
curl -s http://127.0.0.1:8095/health
```

(`python app.py` in development mode runs Flask's debug reloader; fine for local use.)

Docker (build context is `mcp/`; not deployed anywhere yet):

```bash
docker build -t wos-events-mcp mcp/
docker run --rm --network host -e WOS_API_BASE=http://127.0.0.1:8094 -e MCP_HOST=127.0.0.1 -e MCP_PORT=8095 \
  -e MCP_BEARER_TOKEN -e WOS_ADMIN_PASSWORD wos-events-mcp
```

The image runs as a non-root user, defaults `MCP_HOST=0.0.0.0`, `MCP_TRUST_PROXY=1`, honours Cloud Run's `PORT`,
and has a `/health` healthcheck. As a Cloud Run service it would get `WOS_API_BASE` = the app's URL and the two
secrets from Secret Manager (`--set-secrets`), never `--set-env-vars`.

## Register with Claude Code

```bash
# public tools (player-facing)
claude mcp add --transport http wos-events http://127.0.0.1:8095/mcp

# admin tools (includes the public ones) - the token ends up in ~/.claude.json; keep it local-scope
claude mcp add --transport http --scope local wos-events-admin http://127.0.0.1:8095/admin/mcp \
  --header "Authorization: Bearer $MCP_BEARER_TOKEN"

claude mcp list        # both show "✔ Connected" (verified with Claude Code 2.1.290)
```

Do not commit an admin entry in a project-scoped `.mcp.json` with the literal token. If a shared `.mcp.json` is
wanted, use Claude Code's env expansion: `"headers": {"Authorization": "Bearer ${WOS_MCP_ADMIN_TOKEN}"}`.

## Tools

All tools return the API's JSON body unchanged as `structuredContent` (and as JSON text). Errors are **results,
not exceptions**: `isError: true` with

```json
{"error": "Profile not found", "code": "NOT_FOUND", "field": null, "http_status": 404}
```

i.e. the API's `{error, code, field[, details]}` plus the HTTP status. Codes are the API's (see API.md) plus
MCP-side: `UNAUTHORIZED` (admin check), `ADMIN_NOT_CONFIGURED`, `ADMIN_LOGIN_FAILED`, `API_UNREACHABLE`,
`API_TIMEOUT`, `UPSTREAM_ERROR` (non-JSON reply), and `VALIDATION_ERROR` with `field` = `event`/`fid`/`day` when a
path value is not 1-64 of `[A-Za-z0-9_-]` (so it can't alter the URL; everything else is validated by the API).
Arguments that fail the tool's JSON schema (wrong type, limit out of range) are rejected by the MCP SDK before
any API call.

### Public (`/mcp` and `/admin/mcp`)

| Tool | API | Notes |
|---|---|---|
| `list_events()` | `GET /api/events` | events + current round summary |
| `get_current_round(event)` | `GET /api/events/{event}/current` | `NO_CURRENT_ROUND`, `UNKNOWN_EVENT`, `EVENT_HAS_NO_ROUNDS` |
| `get_profile(fid)` | `GET /api/profile/{fid}` | |
| `update_profile(fid, fields)` | `PUT /api/profile/{fid}` | partial; creates when new (`game_name` required) |
| `get_application(event, fid)` | `GET /api/events/{event}/current/application/{fid}` | 404 = not applied this round |
| `get_previous_application(event, fid)` | `GET /api/events/{event}/previous-application/{fid}` | "use my last answers" |
| `submit_application(event, fid, answers, profile?)` | `PUT /api/events/{event}/current/application/{fid}` | `APPLICATIONS_CLOSED` after closing time for new apps |
| `get_published_schedule(day?)` | `GET /api/events/ministry/current/schedule[/{day}]` | no day = list of published days |
| `get_my_assignments(fid)` | `GET /api/events/ministry/current/assignments/{fid}` | **filtered to published days** (the API returns all; the UI filters) |

### Admin (`/admin/mcp` only)

| Tool | API | Notes |
|---|---|---|
| `list_rounds(event, limit=20)` | `GET /api/admin/events/{event}/rounds` | adds `total`, `limit` (max 100) |
| `list_applications(round_id="current", event="ministry", alliance?, offset=0, limit=50)` | `GET /api/events/{event}/current` (for "current") + `GET /api/admin/rounds/{id}/applications` | paged by the MCP server (max 200): `{round_id, total, offset, limit, returned, applications}` |
| `get_application_by_id(application_id)` | `GET /api/admin/applications/{id}` | |
| `update_application(application_id, profile?, answers?)` | `PUT /api/admin/applications/{id}` | answers partial/merged; no closing-time check |
| `start_new_round(event, name, closing_time?, settings?, confirm=false)` | `POST /api/admin/events/{event}/start-new-round` | without `confirm=true` returns a preview of the round it would close and changes nothing |
| `get_assignments(day, round_id="current")` | `GET /api/admin/ministry/rounds/{ref}/assignments/{day}` | includes unpublished days |

Tool annotations mark read-only tools `readOnlyHint` and `start_new_round` `destructiveHint`.

## Safety

- **No bypass**: the server has no DB access and only calls documented endpoints; admin calls use the normal
  admin token. Extra MCP-side checks (path-segment charset, list caps) only ever refuse more.
- **Secrets**: `MCP_BEARER_TOKEN`, `MCP_PUBLIC_BEARER_TOKEN`, `WOS_ADMIN_PASSWORD` and the API token are never
  logged (config `repr` hides them; httpx logging is silenced; uvicorn access log off). A test greps every server
  log for the secrets and for `Bearer `.
- **Prompt injection**: every tool description and the server `instructions` tell the model that names, alliance
  tags, round names and answers are untrusted data. Player text is returned verbatim inside JSON and never
  interpolated into descriptions. Write tools tell the model to act on a player's own FID and to confirm values.
- **Caps**: list tools are paged/capped; request bodies are limited by the SDK (default max body size); per-client
  rate limit (default 120 req/min). The admin applications list is still fetched whole from the API and sliced
  (API has no paging yet).
- **Trust model of public tools** is the API's: knowing a FID is enough to edit that player's profile/application.
  Exposing `/mcp` on the internet adds no new capability over the public API, but it makes mass edits easy for an
  agent. Set `MCP_PUBLIC_BEARER_TOKEN` for any deployed instance unless anonymous MCP access is really wanted.

## Tests

```bash
cd mcp && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q          # 30 tests, ~11 s
```

The suite starts the real Flask backend (`../backend`, using `../backend/venv/bin/python` or
`$WOS_BACKEND_PYTHON`) on a random free port with a temp SQLite DB, `FLASK_ENV=development` and a random
`ADMIN_PASSWORD`; creates rounds through the admin API; starts `python -m wos_mcp` as a subprocess (several
times, with different env); and drives every tool through a real MCP client over streamable HTTP. Covered:
success paths for all 15 tools, `NOT_FOUND`, `UNKNOWN_EVENT`, `NO_CURRENT_ROUND`, `EVENT_HAS_NO_ROUNDS`,
`APPLICATIONS_CLOSED`, `VALIDATION_ERROR` (API-side with `field`, and MCP path checks), admin refused without /
with a wrong token (HTTP 401 and client failure), admin tools absent from `/mcp`, admin disabled without a token,
wrong/missing admin password, optional public bearer, rate limiting, re-login after a rejected API token,
published-day filtering, handshake-era clients (2025-03-26/06-18/11-25) via raw JSON-RPC, and no secrets in logs.

Run on the production Python too:

```bash
docker run --rm -v "$PWD":/src:ro -e PYTHONDONTWRITEBYTECODE=1 python:3.11-slim sh -c '
  python -m venv /tmp/bv && /tmp/bv/bin/pip install -q -r /src/backend/requirements.txt &&
  python -m venv /tmp/mv && /tmp/mv/bin/pip install -q -r /src/mcp/requirements-dev.txt &&
  cd /src/mcp && WOS_BACKEND_PYTHON=/tmp/bv/bin/python /tmp/mv/bin/python -m pytest -q -p no:cacheprovider'
```

## Toward a Discord bot

A bot can call `/mcp` (or the API directly) today, but it still needs, mostly outside this server:

- **Identity**: a verified Discord user ↔ FID link; otherwise any Discord user can edit any FID (API trust model).
- **Authorisation**: map Discord roles to admin actions inside the bot; the bot would hold the single admin bearer,
  so it must enforce who may call which admin tool.
- **Audit**: the API records no actor; admin changes via MCP all look like "admin" (see BACKEND_ISSUES.md).
- **Per-user rate limits** (this server limits per IP, and a bot is one IP).
- **Localisation**: errors are English messages + stable `code`s; the bot should translate by `code`
  (9 languages incl. Arabic RTL).
- **Push**: no webhook/notification when a schedule is published or a round opens; the bot must poll.
- **More admin tools**: publish/unpublish, auto-assign, save assignments, delete application, profile search,
  edit round (closing time/settings) are API features not yet exposed as tools; also the public heatmap.
- **Time zones**: slots are UTC; convert using the profile `timezone`.
