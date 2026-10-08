# Backend issues (collected)

## From frontend wiring (p1b/frontend-wiring)

Found by the frontend-wiring worker against the merged phase-1 backend. Not fixed here (scope:
frontend + e2e); the frontend works around them minimally where noted. Repro commands assume a
local stack on `http://127.0.0.1:8093` with `ADMIN_PASSWORD=admin123` and an open ministry round.

```bash
B=http://127.0.0.1:8093
TOK=$(curl -s -XPOST $B/api/admin/login -H 'Content-Type: application/json' \
      -d '{"password":"admin123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
RID=$(curl -s $B/api/events/ministry/current | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
H=(-H "Authorization: Bearer $TOK" -H 'Content-Type: application/json')
```

## 1. Switching research day keeps the old research day in `published_days`

`PUT /api/admin/rounds/{id}` with `{"settings": {"research_day": "friday"}}` merges settings but does
not drop `tuesday` from `published_days`. The public API then reports a day that is no longer an
active day as published, and serves its schedule.

```bash
curl -s -XPOST $B/api/admin/ministry/rounds/$RID/publish "${H[@]}" -d '{"day":"tuesday"}'
curl -s -XPUT  $B/api/admin/rounds/$RID "${H[@]}" -d '{"settings":{"research_day":"friday"}}'
#  -> settings: {"research_day": "friday", ..., "published_days": ["tuesday"]}
curl -s $B/api/events/ministry/current/schedule          # {"published_days": ["tuesday"], ...}
curl -s $B/api/events/ministry/current/schedule/tuesday  # {"published": true, "day": "tuesday", ...}
```

Expected: `validate_settings` (events/ministry/validation.py) should drop published days that are not
in `valid_days(new research_day)` (or reject the change). The same applies to stored
`ministry_assignments` rows for the old research day (they become unreachable but stay in the table).

Frontend workaround: the Settings tab sends `published_days` without the old research day together
with the research-day switch, and the ministry home only lists published days that are active days.

## 2. Closed (past) rounds are fully writable through the admin API

The admin UI treats a `closed` round as read-only (SPEC: "past rounds are read-only"), but the API
accepts every write on it: round settings, closing time, auto-assign, assignment saves, publish,
application edits/deletes and imports (settings and auto-assign verified with the repro below; the
others by reading `core/applications.py` / `events/ministry/routes.py`, none of which checks the
round status).

```bash
OLD=$(curl -s $B/api/admin/events/ministry/rounds "${H[@]}" \
      | python3 -c 'import sys,json;print([r["id"] for r in json.load(sys.stdin)["rounds"] if r["status"]=="closed"][0])')
curl -s -o /dev/null -w '%{http_code}\n' -XPUT  $B/api/admin/rounds/$OLD "${H[@]}" -d '{"settings":{"show_fire_crystals":true}}'   # 200
curl -s -o /dev/null -w '%{http_code}\n' -XPOST $B/api/admin/ministry/rounds/$OLD/auto-assign "${H[@]}" -d '{"day":"monday"}'     # 200 (rewrites assignments)
```

Possible fix: a `ROUND_CLOSED` (409) error for writes to a closed round, except
`PUT /api/admin/rounds/{id}` with only `status` (to reopen deliberately) and reads/exports.
Decide whether reopening should be allowed at all (it collides with the one-open-round rule).

Frontend: the round selector marks closed rounds read-only and hides/disables every write control
(edit/delete/import, auto-assign, drag & drop, lock, publish, all round settings). Nothing else needed.

## 3. Minor / for the API doc

- `GET /api/events/ministry/current/assignments/{fid}` returns assignments for unpublished days too
  (documented, same as v1.4). The UI keeps the v1.4 behaviour (all active days + "subject to change"
  note). If players should only see published days, filter server-side so drafts are not exposed.
- Server error messages are English only; the UI never shows them and maps `code` (+ `field` for
  `VALIDATION_ERROR`) to translated text instead. Keep `code`/`field` stable.

## From MCP server (p1b/mcp-server)

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
