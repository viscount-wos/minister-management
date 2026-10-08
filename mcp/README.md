# wos-events MCP server

MCP server (official `mcp` SDK 2.3, streamable HTTP) in front of the wos-events HTTP API. It never touches the
database; every call goes through the API so validation stays in the backend.

- `POST /mcp` — public tools (list_events, get_current_round, get_profile, update_profile, get_application,
  get_previous_application, submit_application, get_published_schedule, get_my_assignments)
- `POST /admin/mcp` — public + admin tools (list_rounds, list_applications, get_application_by_id,
  update_application, start_new_round, rename_round, get_assignments); requires `Authorization: Bearer $MCP_BEARER_TOKEN`
- `GET /health`

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
WOS_API_BASE=http://127.0.0.1:8094 MCP_PORT=8095 MCP_BEARER_TOKEN=... WOS_ADMIN_PASSWORD=... .venv/bin/python -m wos_mcp
.venv/bin/python -m pytest -q
claude mcp add --transport http wos-events http://127.0.0.1:8095/mcp
```

Full documentation (auth design, env vars, tools, safety, Docker, Claude Code, Discord notes):
[../docs/MCP.md](../docs/MCP.md). API gaps found: [../docs/BACKEND_ISSUES.md](../docs/BACKEND_ISSUES.md).
