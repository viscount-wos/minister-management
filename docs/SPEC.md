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

## Migration from v1.4 DB (must be EXPLICIT, idempotent, tested)
Changed in milestone 1c (review H1): the import is no longer automatic. A normal boot on a v1.4 file refuses to
start; the operator runs `python -m core.migrate` (or boots once with `MIGRATE_V14=1`) as described in
docs/DEPLOY-CUTOVER.md. Detect old schema (players TABLE has construction_speedups_days). Before migrating, copy DB
file to `<db>.pre-v2-<timestamp>.bak` (written as `.bak.partial`, renamed after COMMIT). Then:
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

### Backend phase 1 deviations / decisions (p1/backend-core)
Final shape is in docs/API.md. Where it differs from the sketch above:
- All list responses are wrapped in an object (`GET /api/events` -> `{"events": [...]}`) so every response is a JSON
  object (simpler for the MCP server and error handling). Errors are always `{error, code, field}`.
- `closing_time` lives only in the `rounds.closing_time` column, not inside `rounds.settings`.
- The round-scoped assignments table is named `ministry_assignments` (event-specific; tyrant/svs will have their own).
  `player_id` everywhere = `profiles.id`; v1.4 player ids are kept as profile ids by the migration.
- Ministry admin routes are `/api/admin/ministry/rounds/<id|current>/...` (auto-assign, assignments/<day>, publish,
  unpublish, export, export-json, import). Generic xlsx export is `/api/admin/rounds/<id>/export`.
- Added: `GET /api/admin/me`, `GET/PUT /api/admin/settings`, `PUT /api/profile/<fid>` (public, for MCP
  update_profile; same trust model as the application PUT), `GET /api/admin/rounds/<id>`, `GET /api/admin/applications/<id>`,
  `GET /api/admin/profiles/<fid>`, `is_closed_for_new` on rounds.
- v1.4 endpoints are removed, not shimmed: the frontend must be rewired (map in docs/API.md).
- Fresh installs start with NO rounds; an admin opens one with start-new-round.
- Migration: when the v1.4 DB has no stored `time_slot_scheme`, it is inferred from stored slots (:20/:50 = max_slots)
  rather than v1.4's "pin max_slots if any assignments" (a running v1.4 without the key was using exact_alignment).
  Orphan v1.4 assignments (player deleted) stay only in `legacy_assignments`. Migration tests use an inline v1.4
  fixture (tests/test_migration.py); tests/fixtures is owned by the e2e/fixtures worker.
- Small behaviour fixes vs v1.4: auto-assign walks a player's preferences in sorted order (v1.4 iterated a Python set,
  so slot choice depended on hash order); `preferred_times` on assignment cards is the day's own preferences (v1.4
  returned every day type's, with duplicates); a sticky placement on a slot that doesn't exist in the current scheme
  is re-placed instead of the player vanishing; manual assignment saves reject unknown slots/players and duplicates.
- Excel export keeps v1.4's per-day sheets (with their UNASSIGNED section) and adds an `Unassigned` summary sheet.
- Auth: a SECRET_KEY that is missing or a known placeholder stops the app outside development (1c; it used to be
  replaced by a random per-process key); a role whose password env var is unset cannot log in (v1.4 silently fell
  back to admin123/minister123).
- `PRAGMA foreign_keys=ON` on every connection (v1.4 never enabled it).
- Benign differences found by the parity harness (milestone 1b), now intended:
  - absent strings (alliance, avatar_image, stove_lv_content, timezone) are `null` in cards and exports, never `''`
    (v1.4 mixed both);
  - equal-points ties: the Excel UNASSIGNED section and `Unassigned` sheet order ties by player id ASC (as v1.4's
    Excel); the admin unassigned list orders ties newest application first;
  - hours inside `time_slots_by_day` are stored and returned sorted (v1.4 read them back sorted);
  - the heat map counts only applicants of the round (v1.4 also counted preference rows of deleted players).

### Milestone 1c decisions (review fixes, docs/REVIEW-phase1.md)
- **Explicit v1.4 import** (H1): normal boot refuses a v1.4 file (`LegacyDatabaseError`); import via
  `python -m core.migrate [--db PATH] [--check]` or `MIGRATE_V14=1`. Migration 2 creates guard VIEWs named
  `players`, `time_preferences`, `assignments`, `admin_users` (no rows, v1.4 columns) and triggers rejecting the v1.4
  round-setting keys in `settings`. A v1.4 instance on a v2 file cannot boot (its init hits the views) and every
  write fails loudly. An empty ghost v1.4 table found later is dropped; a non-empty one stops the app with a message.
- **Locking** (H2): `migrate()` takes `BEGIN IMMEDIATE` before reading `schema_version` or detecting a legacy file and
  runs all pending migrations in that transaction. Production runs ONE instance (`--max-instances 1`).
- **Secrets** (H2/M4): outside development a missing/placeholder/short (<16) `SECRET_KEY` or a well-known default
  password stops the app (`ConfigError`). Placeholders and the `admin123`/`minister123` defaults are accepted only
  with `FLASK_ENV=development` AND `ALLOW_INSECURE_DEV=1` (docker-compose sets both, binds 127.0.0.1). Development
  without a key gets a random per-process key.
- **Crystals** (M1): imported exactly as v1.4 stored them (`12.5` stays `12.5`; points match v1.4). New input must be
  a whole number; an imported fractional value re-sent unchanged (player resubmit, admin edit) is accepted and kept.
- **FIDs** (M2):
  - FIDs are strings end to end; leading zeros are significant (`0040021` ≠ `40021`); FIDs above 2^53 are never
    parsed as numbers.
  - Lookup everywhere (public and admin): exact match first, then the whitespace-trimmed FID.
  - Import: surrounding whitespace is trimmed when the trimmed FID is non-empty and unique among legacy FIDs;
    otherwise the FID is kept byte-for-byte (and stays reachable by exact match). Trimmed, kept and non-digit FIDs are
    logged.
  - A NEW profile needs a canonical FID (digits only, 1-20). An EXISTING profile keeps its stored FID, may resubmit,
    and is always updated by id, so legacy rows never fork.
  - Legacy values over today's limits (e.g. the 4-char alliance `love`, a long name) are accepted when re-sent
    unchanged (alliance compared case-insensitively) and kept exactly as stored; any new value must meet the limits.
- **Admin login throttling** (M3): in-process limiter, per client IP (right-most `TRUSTED_PROXY_HOPS` entry of
  X-Forwarded-For, default 1 = Cloud Run) plus a global budget; after 5 failures exponential backoff (1 s ... 15 min),
  429 `TOO_MANY_ATTEMPTS` with `Retry-After`, without checking the password. Adequate because there is one instance;
  state resets on restart. Passwords are compared as SHA-256 digests with `hmac.compare_digest`, both roles always.
- **CORS** is off unless `CORS_ORIGINS` is set (the SPA is same-origin; Vite proxies `/api` in dev).
- **Excel** (M5): user text starting with `= + - @`, TAB or CR is written as a quote-prefixed text cell: shown exactly,
  never evaluated.
- **Public data with only an FID** (M6, accepted by the owner): see docs/API.md "What an FID gives a stranger". Public
  profile/application responses no longer include internal ids, the profile snapshot or created_at timestamps.
- **Closed rounds are read-only**: application/assignment/publish/import/settings writes on a `closed` round return
  409 `ROUND_CLOSED`. `PUT /api/admin/rounds/<id>` with `status: open|draft` reopens it (subject to the one-open-round
  rule) and may change other fields in the same request. Deleting a whole profile stays allowed (profile-level).
- **Published days** only ever contain active days: switching `research_day` drops the old day, and public endpoints
  ignore stale entries. A player's own assignments (`/current/assignments/<fid>`) list **published days only**
  (v1.4 also returned drafts to anyone with the FID; the MCP tool already filtered). Admins see drafts via admin routes.
- **Public schedule day**: anything other than monday/tuesday/thursday/friday → 400 `VALIDATION_ERROR`; a possible
  but inactive day (e.g. friday when research is tuesday) → `{"published": false}`.
- **Admin routes**: `/api/admin/rounds/<id|current>` (+`/applications`, `/export`; `?event=`, default ministry).
  Admin lists (`rounds`, `applications`, `profiles`) take optional `?limit=` (1-1000) `&offset=` and always report
  `total`.
- Scheme switch re-syncs the shared 23:50 boundary (L3): after remapping, the boundary is mirrored from the earlier
  day if occupied, else from the later day. Export timestamps are UTC ISO `Z` (L5). Name/alliance filters use Python
  `casefold()` (Unicode-aware, L7). Read-modify-write of round settings/publish runs under `BEGIN IMMEDIATE`; a
  locked database answers 503 `RETRY` (L2). JSON import runs each entry in a savepoint; database errors are reported
  per entry (L4). A failed migration leaves no backup; one `.bak` per successful import (L1).

### Known / accepted (not fixed)
- **L6**: a `closing_time` without offset is UTC (the admin UI must send `toISOString()`); an unparseable legacy closing
  time leaves the round open with only a log warning and `settings.legacy_closing_time_raw`; `profiles.timezone` is
  free text ≤64 chars, not validated against IANA.
- **L8**: admin tokens cannot be revoked individually. Rotating `ADMIN_PASSWORD` does not invalidate issued tokens
  (≤12 h); rotating `SECRET_KEY` invalidates all. A bare token (no `Bearer`) is accepted.
- **M6**: anyone with an FID can read and change that player's profile and current application (no login by design);
  there is no per-IP limit on public PUTs and no audit trail yet.
- Assignments of an old research day stay stored (unreachable) after a `research_day` switch.

### Frontend 1b decisions (p1b/frontend-wiring)
- All HTTP goes through `frontend/src/shared/api.ts` (typed, error codes, one CONFLICT retry, 401 -> login).
- The player flow is ONE page, `/ministry/apply`: FID first, then "New application for <round>" or
  "Edit your application for <round>". It replaces v1.4's 5-step wizard + separate update page
  (`/submit`, `/update`, `/apply`, `/ministry/submit|update` redirect there). Empty-slot `confirm()` kept.
- "Past round read-only" = `status === 'closed'` (UI only; the API still accepts writes, see
  docs/BACKEND_ISSUES.md #2).
- A player's own assignments show every active day (as v1.4), not only published ones.
- Server error text is never shown; `code`/`field` map to translated messages.

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
