# Backend issues found while building the MCP server

Things the MCP server works around or cannot do because of the current API (docs/API.md). None of these were
changed in the backend by the MCP work; each is a proposal.

1. **Public assignments include unpublished days.** `GET /api/events/ministry/current/assignments/{fid}` returns
   every day (as v1.4) and relies on the UI to filter by `published_days`. Anyone can therefore see a player's
   draft slots via the API. The MCP `get_my_assignments` tool filters; the API should too (or offer
   `?published_only=1`).
2. **No paging on admin lists.** `GET /api/admin/rounds/{id}/applications` (and `/api/admin/profiles`) return
   everything. The MCP server fetches the whole list and slices it (`offset`/`limit`, max 200). Proposal:
   `?limit=&offset=` and a `total`, maybe `?fields=summary` (fid, game_name, alliance, points only).
3. **`current` not accepted by generic admin round routes.** Ministry routes take `rounds/<id|current>`, but
   `/api/admin/rounds/<int:id>/applications` needs an id, so the tool resolves "current" with a second call
   (tiny race if a round is started in between). Proposal: accept `current` + `?event=` there too.
4. **Unknown day on the public schedule is not an error.** `GET /api/events/ministry/current/schedule/funday`
   returns `200 {"published": false}`, while admin day routes return `400 VALIDATION_ERROR`. Proposal: 400 for
   days that are not one of the round's three days.
5. **No actor / audit trail.** Admin tokens carry only `{role}`. Everything done through the MCP admin endpoint
   (or a future Discord bot) is indistinguishable from the web admin. Proposal: optional `X-Acting-As` header
   (trusted only from the MCP service) recorded on writes, or per-user admin accounts (auth.py is the one place to
   change).
6. **Public writes have no abuse protection.** `PUT /api/profile/{fid}` and the application PUT accept anyone who
   knows a FID and have no rate limit. Fine for the web form's trust model, weak for bots. Proposal: per-IP rate
   limit in the API, and a FID-ownership mechanism (e.g. Discord link) before bot writes.
7. **No admin login rate limit.** `POST /api/admin/login` can be hammered; the MCP server keeps the password
   server-side so it is not an MCP vector, but the API itself should throttle failed logins.
8. **No change notifications.** Bots must poll `GET /api/events` / schedule endpoints; a lightweight
   `updated_at`/ETag on round and schedule responses (or a webhook) would make polling cheap.
