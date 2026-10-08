# wos-events: build spec (phase 1)

wos-events grows out of minister_management (v1.4.0, live at ministry.hunterisadonkey.com) into a combined state
event app for Whiteout Survival state #2807. Planning doc (the "why"): ~/ai/fun/wos/catalogue/PLAN-event-app.md.
This file is the contract that parallel workers build against. If you must deviate, document it here in your commit.

## Non-negotiables
- 9 languages on EVERY user-visible string: en es fr de pl ko zh tr ar. Arabic is RTL. No hardcoded English in components.
- No player login. Players identify by FID (furnace/player ID) only.
- Admin: shared passwords from env (ADMIN_PASSWORD, MINISTER_PASSWORD, same permissions), behind ONE auth module so
  proper accounts can replace them later.
- Ministry behaviour for players and admins must not regress (points maths, time-slot schemes incl. max_slots/23:50 shared
  slot, sticky assignments, publish/unpublish, closing time, heat map, Excel export, themes, changelog, guides).
- SQLite, `PRAGMA journal_mode=DELETE` (GCS FUSE), single gunicorn worker. Same Dockerfile/Cloud Run pattern.
- Flask stays (no FastAPI rewrite). React 18 + TS + Vite + Tailwind stays. Theme tokens only (see claude.md).
- Nothing is deployed to Google in this phase. Local only (docker compose on 127.0.0.1:8091).
- Never commit secrets. `.env` files are gitignored.

## SECURITY FIX (must be in phase 1)
v1.4 returns fixed tokens 'admin-token'/'minister-token' and accepts them as auth, so ANY client can call admin
endpoints without the password (verified locally). Replace with signed, expiring tokens
(itsdangerous URLSafeTimedSerializer with SECRET_KEY; payload {role}; max_age 12h). Tests must prove a forged/literal
token is rejected.

## Concepts
- PROFILE: one per FID, persistent across events: fid, game_name, alliance (<=3 chars, upper), timezone,
  furnace_level (nullable), power (nullable int), troops (JSON, nullable), legacy avatar_image/stove_lv/stove_lv_content.
- EVENT: fixed set of keys: `ministry`, `tyrant`, `svs`, `tal` (tal = Tundra Arms League, "coming soon": no rounds yet).
- ROUND: one occurrence of an event (e.g. "SVS ministry, week of 13 Oct"). Fields: id, event, name, status
  ('draft'|'open'|'closed'), closing_time (ISO UTC, nullable), settings (JSON, event-specific), created_at.
  At most ONE open round per event = the "current round".
- APPLICATION: one per (round, player). answers (JSON, event-specific), profile_snapshot (JSON copy of profile at
  submit time), created_at, updated_at. UNIQUE(round_id, player_id).
- Each round is a NEW application. A player with no application in the current round sees "New application for
  <round>"; with one, "Edit your application for <round>". Round-specific answers start BLANK, with a
  "Use my last answers" button that copies answers from that player's most recent application for the same event.
  Profile fields always pre-fill.
- Closing time: as v1.4, after closing_time NEW applications are blocked (403 code APPLICATIONS_CLOSED); existing ones
  can still be edited until the round is closed by an admin.

## Ministry specifics (ported, now per round)
- answers: construction/research/troop_training/general speedup days, fire_crystals, refined_fire_crystals,
  fire_crystal_shards, time_slots_by_day {construction, research, troop}.
- Per-round settings (move out of global settings): research_day, show_fire_crystals, time_slot_scheme,
  published days, closing_time. Global settings stay global: state_number.
- assignments gain round_id; all assignment endpoints are scoped to a round (default: current round).
- "Remove all players" is replaced by "Start new round" (closes the current round, opens a new one). Nothing deleted.

## Backend layout (target)
```
backend/
  app.py                 create_app() factory; registers blueprints; serves SPA
  core/db.py             connection, schema, versioned migrations (schema_version table)
  core/auth.py           login, token sign/verify, @require_admin
  core/profiles.py       profile CRUD
  core/rounds.py         round CRUD, current round, open/close
  core/applications.py   generic application CRUD + "latest previous" lookup + snapshot
  core/settings.py       global settings
  events/ministry/       routes.py, logic.py (points, slots, auto-assign, export), validation.py
  events/tyrant/         (phase 2)
  events/svs/            (phase 3)
  tests/                 pytest; run with `cd backend && python -m pytest`
```

## Migration from v1.4 DB (must be automatic, idempotent, tested)
Detect old schema (players has construction_speedups_days). Before migrating, copy DB file to
`<db>.pre-v2-<timestamp>.bak`. Then:
- players -> profiles (keep fid, game_name, alliance, timezone, legacy avatar/stove columns).
- create ONE ministry round "Imported from previous system" (status open, settings from old global settings incl.
  closing time, research_day, show_fire_crystals, time_slot_scheme, published days).
- each old player row -> application in that round (resource columns + time_preferences by day_type).
- assignments -> same, with round_id. Sticky flags preserved.
- Old tables are renamed `legacy_*`, not dropped.
Test with a realistic v1.4 dummy DB (see tests/fixtures), including: pre-August rows with avatar/stove fields, max_slots
scheme with shared 23:50 slot, players with no time prefs, sticky assignments, unassigned players, published days.

## HTTP API (target; document final shape in docs/API.md)
Public:
- GET  /health
- GET  /api/events                          -> [{key, current_round: {id,name,status,closing_time}|null}]
- GET  /api/settings/public                 -> {state_number}
- GET  /api/profile/<fid>                   -> profile | 404
- GET  /api/events/<event>/current          -> current round (with public settings) | 404
- GET  /api/events/<event>/current/application/<fid>   -> application | 404
- GET  /api/events/<event>/previous-application/<fid>  -> most recent application in an EARLIER round | 404
- PUT  /api/events/<event>/current/application/<fid>   body {profile:{...}, answers:{...}} -> upserts profile + app
- ministry public: heatmap, published schedule per day, player's own assignments (current round)
Admin (Authorization: Bearer <signed token>):
- POST /api/admin/login {password} -> {token, role}
- GET  /api/admin/events/<event>/rounds ; POST (create) ; PUT /api/admin/rounds/<id> (name/status/settings/closing)
- POST /api/admin/events/<event>/start-new-round {name}
- GET  /api/admin/rounds/<id>/applications?alliance= ; PUT/DELETE /api/admin/applications/<id>
- GET  /api/admin/profiles ; PUT/DELETE /api/admin/profiles/<fid>
- GET  /api/admin/rounds/<id>/export (xlsx)
- ministry: auto-assign / get / update assignments, publish/unpublish, export-json/import, scoped by round id.

## MCP server (phase 1b, in front of the API)
Separate process `mcp/` (Python, official `mcp` SDK, streamable HTTP), talks to the app ONLY via the HTTP API above.
Tools (first cut): list_events, get_current_round, get_profile, update_profile, get_application, submit_application,
admin: list_applications, list_rounds, start_new_round. Admin tools need an MCP-side bearer token (env) and use the
admin password via the API. Nothing in the MCP server bypasses API validation.

## Frontend layout (target)
```
frontend/src/
  shell/        Layout, Header (language/theme/timezone selectors), Home with one tile per event, Changelog
  shared/       api client, FID lookup, profile fields, field components, "use my last answers"
  events/ministry/ events/tyrant/ events/svs/ events/tal/
  i18n/         index.ts + locales/<lang>/<namespace>.json  (namespaces: common, profile, ministry, tyrant, svs, tal, admin, guide, changelog)
scripts/check-i18n.mjs   fails (exit 1) if any key is missing/extra in any language vs en, or any value empty
```
Routes: `/` home tiles; `/ministry/...` (existing pages move under here); `/tyrant`, `/svs`, `/tal`; `/admin/...`.
Old routes (`/apply`, `/update`, etc.) redirect to the new ones.

## Testing (every milestone)
- Backend: pytest, real SQLite temp files, covering auth (forged token rejected), rounds, applications,
  "previous application", closing-time rule, ministry points/auto-assign/schemes, migration from fixture.
- Frontend: `npm run build` (tsc) clean + `node scripts/check-i18n.mjs` clean.
- E2E: Playwright (python) smoke against docker compose: home -> ministry apply in en and ar (RTL),
  edit via FID, admin login, start new round, "use my last answers".
- Reviewer pass: a separate agent critiques each milestone against this spec before it is accepted.
