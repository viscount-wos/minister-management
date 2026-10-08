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
  furnace_level (nullable code, see "Furnace levels"), power (nullable int), troops (JSON, nullable), discord_id
  (nullable, phase 2), legacy avatar_image/stove_lv/stove_lv_content.
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
- ~~The player flow is ONE page~~ (1b, REVERSED by the owner in 1d: "the wizard was part of the appeal, it was far
  clearer for the user"). See "Frontend 1d decisions".
- "Past round read-only" = `status === 'closed'` (the API now also refuses writes: 409 `ROUND_CLOSED`).
- ~~A player's own assignments show every active day~~ (1c: the API lists published days only, see below).
- Server error text is never shown; `code`/`field` map to translated messages.

### Frontend 1d decisions (p1d/wizard)
- The ministry player flow is v1.4's 5-step WIZARD again, at `/ministry/apply` (`ApplicationWizard.tsx`):
  1 Player information (+ speedups/crystals), 2 Construction day, 3 Research day, 4 Troop training day,
  5 Review & confirm. Same step indicator, Back/Next, v1.4 wording, step-1 checks (name, alliance) and the per-day
  "no time slots selected" `confirm()` on Next. `/submit`, `/apply`, `/update`, `/ministry/submit|update` redirect
  here keeping the query (`/update?fid=123` opens straight in edit mode).
- Rounds on top: step 1 starts with the FID (Next = look it up). Then the wizard is
  - EDIT mode "Edit your application for <round>" when the FID applied in the current round: every step pre-filled,
    v1.4's update page parts kept (current-assignments box at the top of step 1, "Update" submit button);
  - NEW mode "New application for <round>": profile fields pre-filled, round answers (speedups, crystals, hours)
    blank. "Use my last answers" (only when an earlier application exists, NEW mode only) sits on step 1 above the
    speedups and copies the previous round's numbers AND hours, with a "copied from <round>" notice.
  - New FID + closing time passed -> the "applications closed" card; an existing application stays editable.
    403 `APPLICATIONS_CLOSED` on submit -> closed card; 404 `NO_CURRENT_ROUND` / 409 `ROUND_CLOSED` -> "not open".
    A server `VALIDATION_ERROR` sends the player back to the step holding that field.
- The step indicator follows the page direction like v1.4 (Arabic: step 1 on the right). Back/Next arrows are
  mirrored in RTL (v1.4 did not mirror them).
- The timezone is chosen on the time steps (as v1.4), not on step 1; it is saved to the profile.
- Own assignments: only published days are listed (API 1c); with none published the box says "You have not been
  assigned to any slots yet." instead of "None" per day.
- Fractional crystal counts imported from v1.4 are shown and re-sent unchanged (never truncated).
- Test ids: `wizard` (data-mode), `wizard-steps` (data-step), `wizard-step-indicator-N` (data-state
  done|current|todo, aria-current), `wizard-step-N`, `wizard-step-title`, `wizard-back`, `wizard-next`,
  `wizard-submit` (data-mode), `slot-<day>-<HH:MM>`, `slot-grid-<day>`, `review-*`, `review-slots-<day>`.

## Frost Dragon Tyrant (phase 2, p2/tyrant)
Port of the live tyrantpoll app (`project_from_viscount/tyrant/tyrantpoll`, poll.html + admin.html) onto rounds +
shared profiles. Event key `tyrant`; backend `events/tyrant/` (validation.py, logic.py, routes.py); frontend
`events/tyrant/` (TyrantPage landing, TyrantWizard, admin/).

### Profile vs round split (decided)
- **PROFILE** (per FID, reused by ministry/SVS): `game_name`, `alliance` (required for tyrant, as tyrantpoll),
  `discord_id` (NEW nullable column, migration 3, free text ≤64), `furnace_level` (code, see "Furnace levels";
  NOT asked or written by Tyrant since p2e, see "No main furnace in Tyrant"), `power` (absolute integer; the wizard
  asks "Power in Millions" like tyrantpoll and multiplies by 10^6),
  `troops` = `{infantry|lancer|marksman: {furnace_level: code|null, tier: 1-11|null}}`. The tyrant spec validates
  `troops` strictly on tyrant submits (`EventSpec.validate_profile` hook, new); other events keep free-form JSON.
  Rationale: these describe the account and change slowly; SVS needs the same data.
- **ROUND answers** (per application): `availability` (window ids of the round), `discord_vc` (bool), `gem_spend`
  (whole number of gems or null; tyrantpoll had a free-text box), `roles` ⊆ {rally_leader, joiner, gathering,
  battle_mgmt, event_prep}, `language` (UI language at submit, as tyrantpoll stored it). Unknown keys → 400.
  Rationale: availability, VC, gem budget and roles depend on the event date and the player's plans.
- A window id the admin later removed from the round is kept when the stored answers are re-sent (admin edits keep
  working); a new unknown id is a VALIDATION_ERROR. "Use my last answers" copies only ids that exist now.

### Round settings
- `windows`: 1-12 `{id: [a-z0-9_]{1,24}, start: "HH:MM", end: "HH:MM" (> start), rush: bool}` (UTC), stored sorted
  by start. Default = tyrantpoll's: w1 11:01-11:15 rush, w2 11:15-13:00, w3 13:00-15:00, w4 15:00-16:30,
  w5 16:30-18:00. Carried over by start-new-round. Any other setting key → 400. `closing_time` is the round column.
- "Opening rush" = windows with `rush: true` (shown as "Opening Rush" + time tag); the summary counts players
  available in any rush window.

### Wizard (owner: keep the wizard)
tyrantpoll's 6 steps in its order: 1 Player Identity (FID first, then name, read-only FID, Discord ID, alliance),
2 Availability (UTC note, Select All, windows, divider, Discord VC), 3 Player Stats (power in millions, est. max gem
spend; the furnace dropdown was removed in p2e), 4 Troop Levels (camp FC level dropdown + T8-T11 per troop),
5 Roles Wanted, 6 Review with Edit per section, Submit/Update. Round flow exactly as the ministry wizard: FID lookup → NEW "New sign-up for
<round>" (profile pre-filled, answers blank, "Use my last answers" on step 1 when an earlier tyrant application
exists) or EDIT "Edit your sign-up for <round>" (all pre-filled); "Not you? Use a different FID"; closing time →
closed card for new FIDs, edit still allowed; no round → "not open". Reuses ministry's `WizardSteps` (direction
follows the page: Arabic step 1 on the right, as both tyrantpoll and ministry do) and arrows mirrored in RTL.

### Admin
Runs inside the shared Event Management shell (see "Event Management admin"): `/admin/dashboard?event=tyrant`.
Players tab (stats cards: total, opening
rush, Discord VC, alliances, est. gems; breakdowns per window/role/alliance/troop tier; search name/FID/Discord,
alliance filter, camp/tier filters (no furnace filter since p2e), sortable server-paged table, delete; CSV + Excel
export), Settings tab (windows editor, closing time). Endpoints in docs/API.md "Frost Dragon Tyrant". Admin guide: `/admin/guide?event=tyrant`.
- Exports use the CURRENT profile (as ministry), not the snapshot. CSV: UTF-8 BOM, formula-injection-safe (leading
  `= + - @ TAB CR` prefixed with `'`); xlsx: tyrantpoll's styled sheet + a Summary sheet, quote-prefixed text cells
  (`core/exports.py`, shared helpers).

### Troop camps and admin filters (owner rules, p2d/tyrant-camps)
Game facts (owner): each troop type has its own CAMP with its own FC level, which can lag the furnace (FC9 furnace,
FC7 infantry camp). Asking only the furnace makes players look stronger than they are, so camp levels are the key
strength signal. The best joiner has FC10 camps with T11 troops.
- **FC1-FC10 only** in Tyrant, for each camp (`FurnaceLevelSelect fcOnly`: FC10..FC1, no pre-FC group). Any
  combination is allowed: NO rule tying T11 to a camp level (the owner rejected cross-field rules as
  overcomplicated). Tiers stay T8-T11 in the UI (API 1-11). Minister (and SVS) keep the full list incl. 1-30.
  Backend: `TyrantEvent.validate_profile` → `core.furnace.validate_fc_level`, so a pre-FC camp code on a tyrant
  submit (player or admin edit) is `VALIDATION_ERROR` naming the field; the generic profile route and Minister
  still accept 1-30. (p2d also required the main furnace as FC1-FC10; superseded, see below.)
- **No data migration** (the owner's LAN copy holds pre-FC tyrant sign-ups): stored values stay as they are, are
  shown as they are in the admin (summary line, chips, exports), and the rule applies on submit. In the wizard a
  saved pre-FC camp shows as unselected and must be re-picked.
- **Wizard step 4**: per type "Infantry Camp (FC level)" etc. + one hint "Camps can be lower than your furnace: pick
  your camp's level" (9 languages). Camp level AND tier are required for all three types (the API keeps them
  optional so MCP/API clients are unchanged).
- **No main furnace in Tyrant (owner decision p2e, SUPERSEDES p2d's "main furnace required in Tyrant")**: owner:
  "we really don't need to ask furnace level of the city - but we do need to know the camp level of each troop type
  (fc7, fc8, etc)". So: the wizard has no furnace field (step 3 = power + gems; the review has no furnace row); the
  API ignores a `profile.furnace_level` sent on a tyrant submit / tyrant admin edit (`EventSpec.ignored_profile_fields`,
  dropped before validation: old MCP/API clients don't break and cannot change the shared furnace through Tyrant);
  the admin has no Furnace column, no "Furnace at least" filter, no furnace sort and no furnace stats; tyrant rows,
  summary, CSV/Excel and MCP results carry no furnace; `min_furnace` is gone from the filters (an old URL's
  `min_furnace` is ignored; the MCP `filters` object refuses it). Camp levels + tiers + Strength are the strength
  signal. Untouched: the shared profile's `furnace_level` (stored values stay) and Minister, which still asks the
  furnace with FC10..FC1 + 30..1.
- **Joiner strength** (admin sort `strength`, column "Strength", export column, MCP rows): Σ over infantry, lancer,
  marksman of camp FC number (FC1=1..FC10=10; pre-FC or blank 0) + tier (blank 0). 0..63; 63 = FC10 camps + T11
  everywhere; null (sorted last) without any troop data. A SUM (not a min): one weak camp ranks a player below an
  otherwise equal one, but still above a player weak everywhere; it is simple to explain and to check by hand.
- **Admin filters** (owner, replaces the earlier "minimum furnace" filter): one parser `events/tyrant/filters.py`
  used by the list, the summary and both exports (exports follow the current filters), and by the MCP tools. Keys,
  identical in the API query and the admin URL: q, alliance (multi), min/max_power, min/max_gems,
  windows (ALL of), rush, vc, troop + min_camp + min_tier, exact `<type>_camp` / `<type>_tier` (the chips), roles +
  roles_mode, submitted_from/to, days. All AND. Details: docs/API.md.
- **Admin UI** (`TyrantPlayers.tsx`): a filter card on top: search, alliance (multi), windows incl. "Opening rush",
  troop type (All three / one type), camp at least (FC10..FC1), tier (any / T10 or better / T11 only), and a "More
  filters" expander (VC, power and gems ranges, roles any/all, submitted last N days / from-to).
  Active filters are removable pills + one "Clear filters". The summary is recomputed for the filtered set
  ("N of M"); the troop card shows per type the CAMP level counts and the TIER counts as 44px chips; tapping a chip
  toggles the exact filter (highlighted, aria-pressed), several combine with AND; window/role/alliance bars are
  clickable too. Table: the name cell carries a compact line "Inf FC10 T11 · Lan FC9 T10 · Mks FC10 T11" (readable
  without scrolling sideways), a sortable Strength column, 44px sort headers. State lives in the URL
  (`useUrlFilters`, replace-history), so a filtered view is shareable and survives reload.
- **No aggregate gem total** anywhere (stats card, API summary, MCP, Excel Summary); per-player gems stay.
- **Reusable pieces** for Minister / SVS: `shared/filters/useUrlFilters.ts` (URL filter state, list helpers),
  `shared/filters/FilterControls.tsx` (`FilterPills`, `ChipButton`, `CheckboxMenu`); generic strings in
  `common:filters.*`.

### Import of existing tyrantpoll submissions (NOT done; how it could be done)
tyrantpoll's `players` table has one row per submission (duplicates per FID possible). An explicit, one-off
`python -m events.tyrant.import_tyrantpoll --db tyrantpoll.db --round "<name>"` could: open the file read-only,
create one CLOSED tyrant round (or an open one if wanted), take the LATEST row per trimmed FID, upsert the profile
only where our field is empty (game_name, alliance upper-cased and cut to 3, discord_id, furnace 'FCn' kept,
power = float(total_power) × 10^6, troops from `*_furnace`/`*_tlevel` 'FCn'/'Tn'), and save answers: availability
from `slot_opening_rush`→w1, `slot_11_13`→w2, `slot_13_15`→w3, `slot_15_16`→w4, `slot_16_18`→w5; `discord_vc`;
`gem_spend` = digits of the free text or null (log the raw value); roles from `role_*`; `language`; created_at =
`submitted_at`. Report skipped/odd rows like the v1.4 import, run it twice to prove idempotence.

### Known gaps / accepted
- `discord_id` is part of the public profile (anyone with an FID can read it, M6), like the name and alliance.
- Profile-level troop values written by tyrant are visible in ministry (shared profile, by design). Tyrant no
  longer writes the furnace (p2e).

## Event Management admin (p2b/admin-shell)
Owner: the admin was branded ministry-only ("Minister Administration" even on Frost Dragon Tyrant, login always landed
on ministry). Decided: ONE blanket admin called **Event Management**, context-aware.
- **Branding**: `admin:title` = "Event Management" (9 languages) on the login page, the dashboard header and the admin
  boxes of Home / Minister / Tyrant pages. The dashboard shows a CONTEXTUAL subtitle per event (registry `subtitle`
  key, e.g. "Minister: applications and assignments", "Frost Dragon Tyrant: sign-ups, stats and exports"). Shared
  chrome (header, switch, round selector, Start new round, logout, guide button, read-only banner, tabs) carries no
  event wording; event screens may.
- **One shell + registry** (`frontend/src/admin/`): `AdminShell` (dashboard), `AdminLogin`, `AdminGuidePage`,
  `AdminEventSwitch`, `StartNewRoundDialog`; `registry.ts` lists `AdminEventModule`s (`types.ts`: key, label,
  subtitle, icon, publicPath, tabs[{key,label,icon,needsRound,render(ctx)}], Guide, defaultRoundName). Each event
  owns `events/<key>/admin/adminModule.tsx`. Adding SVS = write its module + add one line to `ADMIN_EVENTS`.
  TAL joins when it has rounds; SVS when its module is built. Rounds come from the generic
  `GET /api/admin/events/<key>/rounds`.
- **URLs** (`admin/paths.ts`): `/admin?event=<key>` (login), `/admin/dashboard?event=<key>`, `/admin/guide?event=<key>`.
  Without `?event=` the last event administered on this device (`localStorage.adminLastEvent`, set when a dashboard
  opens) is used, else ministry; the URL is then rewritten with `?event=`. Old `/admin`, `/admin/dashboard`,
  `/admin/guide` keep working.
- **Landing**: event pages link to `/admin?event=<key>` -> after login that event's dashboard; Home links to `/admin`
  (last event or ministry); a valid token skips the login; a 401 goes to `/admin?event=<key>&expired=1` and back to
  the same event after login. The event switch only changes `?event=` (token kept). Logout goes to the event's page.
- **Guides**: the dashboard's guide button opens `/admin/guide?event=<current>`; the guide page has the same event
  switch. New Frost Dragon Tyrant admin guide (`guide:tyrantAdmin.*`, 9 languages): rounds, Start new round, time
  windows editor, closing time, stats, search/filters/sort, exports, delete, workflow.
- **Page titles**: index.html is "State Events · Whiteout Survival"; every page sets `document.title` via
  `shared/usePageTitle` = parts + `common:appTitle` ("State Events"), e.g. "Frost Dragon Tyrant · State Events",
  "Frost Dragon Tyrant · Event Management · State Events", translated, follows language changes.
- **State number**: no hardcoded 2694 anywhere in the UI; the welcome line is hidden until an admin sets one
  (wording "Welcome, State #N" since p2c/mobile).
  Backend change (trivial, noted): `core/settings.py` `DEFAULTS['state_number']` is now `None` (public settings
  return `null` when unset; v1.4 defaulted to "2694").
- 'TAG' placeholder: none left (alliance placeholders are translated `profile:alliancePlaceholder`).

## "Minister", not "Ministry" (owner rule, p2b/admin-shell)
"Ministry" was a long-standing typo: the in-game term is minister positions.
- Every user-visible "Ministry/ministry" is now "Minister/minister" in English (tile, pages, schedule, application,
  guides, changelog subtitle, admin subtitle, default round name "Minister <date>", theme "Minister Dark", titles,
  admin download names `minister_round_<id>_...`). Other languages use the word for the PERSON/position, not the
  department: es Ministro, fr Ministre, de Minister, pl Minister/ministrów, tr Bakan, ar وزير/الوزراء, ko 장관 (was
  already; one 부처 fixed), zh 大臣 (was 部长; 大臣 per coordinator, to confirm against the Chinese client).
- Canonical routes: `/minister`, `/minister/apply`, `/minister/schedule/:day`, `/minister/guide`. `/ministry/...`,
  `/minister/submit|update`, and the v1.x `/submit`, `/apply`, `/update`, `/schedule/:day`, `/guide` redirect there;
  `/ministry/admin` -> `/admin?event=ministry`. `LegacyRedirect` keeps (and merges) the query string and hash.
- NOT renamed (not front-facing): event key `ministry` in API/DB/MCP, file/folder names, i18n key names, test ids.
  The backend's generic xlsx export still names its file `ministry_<round>_<date>.xlsx` (only reached via
  the API/MCP; the UI names its downloads itself).

## Phone-first (owner rule, p2c/mobile)
Most players use the site on a phone. Every milestone gets a 360-390px check (no sideways scroll, tap targets
>= 44px, step indicator inside the card, Arabic RTL); `e2e/test_mobile.py` enforces it.
- **Header** (`shell/Header.tsx`, `shell/CompactSelect.tsx`): ONE row on every width: the "All events" link (icon
  only below `sm`) and three compact dropdowns, each a 44px chip with a NATIVE `<select>` stretched invisibly over
  it: timezone (clock + short zone: `UTC`, `KST`, `ET`, or the city of a detected zone), language (globe + the
  current language in its own script; options = the 9 native names), theme (palette + theme name; icon only below
  `sm`). Why native selects under a chip: phones get their own picker (iOS wheel, Android sheet), keyboards and
  screen readers get a real labelled select (`common:header.timezone|language`, `common:theme.title`), no custom
  popup to maintain, and the visible part stays small. At 360px the row uses about 300px. Test ids:
  `header-timezone`, `language-select`, `theme-select` (+ `-chip` on the visible box), `site-header`, `nav-home`.
  The pills are gone (e2e `ui.switch_language` selects the option).
- **Language auto-detect** (`i18n/detect.ts`): saved choice (`localStorage.preferred_language`, written only when
  the player picks one) > first supported language in `navigator.languages`, matched on the base code (`es-MX` ->
  es, `zh-TW`/`zh-HK` -> zh, `ar-*` -> ar) > English. No IP / geolocation (wrong for expats and VPN users, needs a
  third party or a permission prompt). The language IS remembered now (v1.4 started in English every visit).
- **First paint**: an inline script in `index.html` applies the same rules (and the saved theme) before the first
  paint, so `<html dir/lang>` is right before any JS bundle loads: no LTR flash for Arabic. Keep it in step with
  `detect.ts` / `theme.ts`.
- **Timezone auto-detect** (`shared/timezone.ts`): saved choice (`preferred_timezone`) > the browser's
  `Intl.DateTimeFormat().resolvedOptions().timeZone`, mapped onto the list (aliases such as `Etc/UTC` -> UTC,
  `Asia/Istanbul` -> Europe/Istanbul); a zone outside the list is offered as an extra option labelled by city and
  current offset ("Berlin (UTC+2)") > UTC. The detected zone is not saved; only a choice is.
- **Welcome line**: "Welcome, State #2807" (`common|ministry|tyrant:home.welcome`, 9 languages, the game's word for
  state: Estado, État, Staat, Stan, 주, 州, Eyalet, الولاية); still hidden while the state number is unset.
- **Wizards** (`shared/WizardChrome.tsx`, shared by Minister and Tyrant): phone paddings, step circles 32px with
  flexible connectors (always inside the card), step titles 2xl, and the Back/Next bar (`wizard-nav`) is STICKY at
  the bottom of the screen below `sm` (static row from `sm` up), 48px buttons. Hour grids: 4 columns, 48px buttons,
  local time + UTC fit without clipping. Inputs are 16px (no iOS zoom on focus) and >= 44px; keyboards: FID
  `numeric`, speedup days `decimal`, crystals `numeric`, Tyrant power `decimal`, gems `numeric`.
- **Tiles** (`shared/Tile.tsx`): a compact row (icon beside text) on phones, the original tall card from `sm` up.
- **p2d phone-audit fixes**: the Minister review heading names the zone the times are shown in ("Time Preferences
  (KST)", was a fixed "(UTC)"); time chips render through `shared/TimeWithUtc.tsx` with each time an LTR isolate
  (`<bdi dir="ltr">`), so Arabic reads "20:00 (11:00 UTC)" instead of "(UTC 11:00) 20:00", and the "Times shown in"
  zone is isolated too; the assignment board's "Wants:" line shows the admin's display zone (was raw UTC); Tyrant
  admin settings: time inputs 16px / 44px, "Opening Rush" checkboxes in 44px rows, sort headers and pager 44px.
- **Admin on phones: usable, not perfect.** Event switch, tab bar and day tabs scroll sideways inside their own
  container; tables scroll inside `overflow-x-auto`; round selector full width; buttons 44px. Assignment board:
  `MouseSensor` (5px), `TouchSensor` (long press 250 ms, tolerance 8px, so a swipe still scrolls) and
  `KeyboardSensor`; plus a TAP-TO-MOVE fallback below `lg`: the move icon on a card (`move-<fid>`) picks it, every
  slot then shows "Move here" / "Swap here" (`move-here-<slot>`, `move-here-unassigned`), with a cancel banner
  (`move-banner`). Same move/swap/sticky rules as drag-and-drop (one `moveTo`). The hover tooltip is mouse-only.

## Furnace levels (owner rule, phase 2; applies to EVERY event)
- Two kinds: pre-FC furnaces 1-30, Fire Crystal furnaces FC1-FC10 (nothing above FC10). Most players are FC.
- Stored everywhere as a canonical STRING code: `'FC1'..'FC10'` or `'1'..'30'` (profile `furnace_level`, and each
  tyrant troop's `furnace_level`). The API normalises `fc5`/`5`/`5.0` to `FC5`/`5` and answers anything else with
  `VALIDATION_ERROR` + field. `core/furnace.py` (`FURNACE_LEVELS`, `validate_furnace`, `furnace_ordinal`) and
  `frontend/src/shared/furnace.ts` are the only definitions.
- Order (dropdowns, admin sorting, stats): FC10, FC9 ... FC1, then 30, 29 ... 1. `furnace_ordinal`: '1'=1 ... '30'=30,
  'FC1'=31 ... 'FC10'=40, blank/invalid 0.
- UI: ALWAYS a dropdown, never free text: the one shared `shared/FurnaceLevelSelect.tsx` (empty "Select...", then an
  optgroup "Fire Crystal" FC10..FC1, then "Pre-FC" Lv. 30..1; group names and "Lv." translated). Used by the ministry
  wizard (ProfileFields), the Tyrant per-troop camp levels and the Tyrant admin camp filter (the Tyrant stats-step
  furnace and the admin furnace filter were removed in p2e).
  Exception (owner, p2d): Frost Dragon Tyrant uses `fcOnly` (FC10..FC1 only); see "Troop camps and admin filters".
- Codes are shown as-is in exports, tables and review steps.
- Migration 4 rebuilds `profiles` with `furnace_level TEXT` (SQLite cannot change a column type and INTEGER affinity
  would turn '30' back into 30): integers 1-30 become '1'..'30', valid codes are kept, anything else becomes NULL;
  troop entries' `furnace_level` get the same conversion. Legacy v1.4 `stove_lv*` columns are untouched (display only).

## MCP server (phase 1b, in front of the API)
Separate process `mcp/` (Python, official `mcp` SDK, streamable HTTP), talks to the app ONLY via the HTTP API above.
Tools (first cut): list_events, get_current_round, get_profile, update_profile, get_application, submit_application,
admin: list_applications, list_rounds, start_new_round. Admin tools need an MCP-side bearer token (env) and use the
admin password via the API. Nothing in the MCP server bypasses API validation.

## Frontend layout (target)
```
frontend/src/
  shell/        Layout, Header (timezone/language/theme dropdowns in one row), Home with one tile per event, Changelog
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

## v2.1.0 polish (p3/polish)
- **Security headers + CSP** on every response (`core/security.py`, details in docs/API.md). The inline pre-paint
  script in index.html stays inline (it must run before the first paint) and is allowed by its SHA-256 hash, computed
  from the served file at runtime, so a rebuild never needs a hand-edited hash. No `'unsafe-inline'` for scripts or
  styles (React `style={{}}` goes through the CSSOM, which CSP does not block). HSTS only in production or over https.
  The e2e suite fails any test during which a page logs a CSP violation (`e2e/conftest.py`, every browser context).
- **Performance**: brotli/gzip (Flask-Compress; compressed `/assets/*` bodies cached in memory), immutable caching
  for `/assets/*`, every page but Home is a lazy chunk (`src/pages.ts`, the current URL's chunk is preloaded in
  parallel with the language), and each language is one chunk (`locale-<lang>`) loaded on demand; render waits for it
  (`i18nReady`). A chunk that fails to load (old file name after a deploy) reloads the page once.
- **Rate limits** on public FID lookups (30/min/IP) and submissions (10/min/IP): `429 RATE_LIMITED` + `Retry-After`,
  env `RATE_LIMIT_LOOKUPS_PER_MIN` / `RATE_LIMIT_SUBMITS_PER_MIN` (0 = off), translated message in the UI.
- **Dates/times**: ONE helper (`shared/datetime.ts` `formatDateTime`, `<DateTime>` / `useFormatDateTime`): the
  header's display timezone, the UI language's month/weekday names (en uses en-GB order; ar Latin digits), no
  seconds, the zone in brackets, Unicode-isolated for RTL: "Sat 10 Oct, 15:06 (London)". Admin closing-time inputs
  read/write the same display timezone (`isoToZonedInput` / `zonedInputToIso`) and say which zone. The landing
  pages' "All times are in UTC" notes became "Times are shown in {zone} time". Game windows defined in UTC (Tyrant
  windows, minister slots) keep their explicit "(UTC)" / "game time (UTC)" labels.
- **Find your player ID**: `shared/FidHelp.tsx` (a native `<details>`) under the FID input of both wizards.
- **Event Management link** on event pages is a small muted link (test ids `ministry-admin-tile`, `tyrant-admin-tile`
  kept) under the sign-up card instead of a second big card.
- **Round renaming** moved to the shared Event Management header ("Rename", every event, any round incl. closed ones)
  via `PATCH /api/admin/rounds/{ref}`; the ministry Settings tab's own round-name card was removed (one place only).

## SVS sign-up (phase 4, p4/svs-signup, v2.2.0)
Owner brief: `catalogue/SVS-battle-setup-brief.md`. Phase 1 = sign-up + foundations; the drag-and-drop battle
planner it describes comes later.

### Player wizard (`/svs/apply`, phone-first, `WizardChrome` like Tyrant)
1. **Player**: FID (with "Where do I find my player ID?"), in-game name, alliance. Pre-filled from the shared
   profile. The alliance is required ONLY when the profile has none (a new player); a known one may be changed.
2. **Hours**: one big chip per battle hour, label = game time "HH:00 UTC" (LTR-isolated) with the player's local
   time in small text underneath (from the browser zone). At least one. "I can do every hour" / clear.
3. **Troops**: per infantry / lancer / marksman the CAMP level (`FurnaceLevelSelect fcOnly`, FC10..FC1) and the tier
   as two big radio buttons **T11, T10** (never T8/T9 in SVS). All six required. Pre-filled from the shared profile;
   a stored T8/T9 (e.g. from Frost Dragon Tyrant) shows unselected and must be chosen.
4. **Voice chat**: NO role question (owner decision: "SVS sign-up does not ask the role; the planner assigns
   leaders"; an old client's `role` is ignored, stored roles stay but are never shown). **Discord voice chat**
   yes/no (required).
5. **Review** + submit (Update when editing). NO gems, NO main furnace, NO power, NO Discord ID, NO role.
- Edit/resubmit by FID; closed round = Tyrant behaviour (new FIDs blocked after the closing time, existing sign-ups
  stay editable; no round = "not open"). Rate limits apply (generic routes).

### Round settings (decided: settings, because the owner is "not 100% sure" of the window)
`battle_start` "HH:MM" UTC, default **11:00**, and `battle_hours` 1-24, default **5** → hours 11:00..15:00 (the
battle ends at 16:00). Derived `hours` wrap past midnight. Copied by start-new-round. Changing them later keeps the
hours players already chose (re-sent unchanged), but a new pick must be a current hour.

### Shared troops with Frost Dragon Tyrant (the merge rule, `backend/core/troops.py`)
Both events read and write the same per-FID `profile.troops` (`{type: {furnace_level = CAMP level, tier}}`).
- **Per troop type and per field, a value SENT replaces the stored one; a blank/missing value never clears it;
  types, fields and extra keys not sent stay as stored.** Used by SVS, Tyrant (since v2.2.0) and admin add/edit.
- Why "replace" and not "keep the higher": the latest statement is the truth (camps and tiers only go up in-game, and
  a downgrade typed by mistake is fixed by the player re-submitting). The "never downgrade Tyrant's richer data"
  requirement is met because SVS can only ever send FC1-FC10 + T10/T11 (it can't write T8/T9, pre-FC camp codes,
  power, gems or roles), and a blank never wipes a stored value: an SVS sign-up only touches what the player
  actually picked, and an admin add with half the troops filled in never erases the rest.
- An SVS player submit needs the MERGED troops complete (FC camp + T10/T11 ×3): a returning player with valid stored
  troops need not re-send them; a stored T8/T9 or pre-FC camp must be replaced (400 names the field).
- SVS ignores (never stores) `furnace_level`, `power`, `discord_id`, `timezone` from its form.

### Admin (Event Management → SVS: Players / Settings / Heroes; desktop-first)
- Headline stats: total, average battle hours per player, players with T11 in all three troop types, Discord VC (for the filtered set; "of N" when filtered).
- "Players per hour (UTC)" bars, then alliance bars (shared `shared/filters/Breakdowns.tsx`, extracted from
  Tyrant), then per-troop camp-level chips and tier chips (T11, T10, none); every bar/chip toggles a URL filter.
- Filter bar (`shared/filters` `useUrlFilters` + `FilterControls`): search, alliances, hours (attends ALL chosen),
  troop + min camp + min tier; More: Discord VC, submitted from/to, last N days. Pills + Clear.
- Table: name / FID / alliance, hours, VC, troop line "Inf FC10 T11 · Lan FC9 T10 · Mar …", Strength (the
  Tyrant joiner-strength definition), submitted; sortable (incl. Strength); edit / delete; CSV + Excel exports
  respect the filters (`*_filtered` file names).
- Settings: battle start (UTC) + duration with a live preview of the hours, closing time. Admin guide in 9 languages.

### Admin "Add player" (every event: Minister, Tyrant, SVS)
- Button in each players view → `admin/AddPlayerDialog.tsx`: FID + Look up (a known profile pre-fills name /
  alliance / troops), in-game name (required for a new FID), alliance, then the event's own fields, all optional:
  Minister speedups/resources + day slots left empty; Tyrant windows, VC, troops (T8-T11), roles; SVS hours, role, VC,
  troops (T10/T11).
- Backend: `POST /api/admin/rounds/{ref}/applications` reuses the event's validation in ADMIN mode
  (`EventSpec.validate_profile/answers(..., admin=True)`, `admin_required_profile_fields = ('game_name',)` for a new
  profile): answers a player must give may be blank, anything given must be valid. 409 `APPLICATION_EXISTS` if the
  FID already signed up in that round (the dialog says "edit that one instead"). Admin edits use the same lenient mode.

### Admin Edit / Remove in the SVS and Frost Dragon Tyrant lists (v2.2.1, p8/admin-edit)
Owner: "in the admin section for SVS we should also be able to edit players"; Tyrant had the same gap, so both.
Minister already had its own edit (unchanged).
- Each row: a pencil (Edit) and a bin (Remove) icon button, 44px, `aria-label` "Edit <name>" / "Remove <name>" and
  the same tooltip (`admin/PlayerRowActions.tsx`). SVS keeps Add to rally in front of them.
- Edit = `AddPlayerDialog` in EDIT mode (one form for add and edit, not a second one): FID read-only, name, alliance,
  then the event's fields prefilled. SVS: hour chips from the round's hours plus any hour this sign-up kept from an
  earlier start/duration (dashed chip, "old"), Discord VC (blank allowed), camp FC + tier T10/T11 per troop. Tyrant:
  time windows (+ kept old window ids), Discord VC, roles, power (millions), gem spend, Discord ID, camp FC + tier
  T8-T11. A note says what is SHARED with other events (name, alliance, troops; Tyrant also power and Discord ID).
- Save = `PUT /api/admin/applications/{id}` (admin mode, so blanks are allowed where the API allows them). Only what
  changed is sent for name, alliance, power, Discord ID and troops (a legacy 4-character tag or an off-form T9 is never
  re-sent by an edit that doesn't touch it); answers are sent whole (merged by the API anyway). Troops follow the one
  merge rule: a blank level keeps what is stored (hint under the troop cards).
- Errors land on their field: the dialog puts {field, message} in `admin/dialogErrors.tsx` context, each field shows
  `InlineError` + `aria-invalid`, focus moves to the first invalid control, and the bottom alert only shows errors no
  field claimed. Client checks reuse the wizard's messages (Tyrant power/gems); server errors use `errorText` (codes
  translated, field labels added for Tyrant answers).
- After save the row is patched in place (`setApps(map)`), only the summary is re-fetched: filters (URL), page, sort
  and scroll stay. A toast (`useToast`, fixed bottom, `role=status`) confirms. Focus returns to the row's pencil.
- Remove = a confirm dialog naming the player ([TAG] name · FID; Cancel focused, Esc cancels). SVS re-reads the plan
  when it opens and, if the player is in it, says where: "They are Joiner 2 with Rally Caller 01 (Main); they will be
  removed from the battle plan too" (leader / joiner / extra / extra-group sentences).
- **Decision: remove from the plan server-side, atomically** (not "block while in the plan"): blocking would force a
  trip to the planner for every no-show, and the planner already has the "take a player out" semantics. The SVS
  `EventSpec.on_application_deleted` hook takes the write lock (`BEGIN IMMEDIATE`) and, in the SAME transaction as the
  DELETE, removes every placement of that FID with the planner's Move semantics (`plan._remove_at`: a leader card
  stays with its heroes and no player, a named slot keeps its heroes/ratio, an extra joiner / group entry goes) and
  bumps the plan revision by 1, so an open planner gets 409 PLAN_CONFLICT instead of silently re-adding the player.
  The DELETE response adds `plan_removed` (where they were, with the planner's labels) and `plan_revision`; nothing
  changes when they weren't in the plan. A rollback undoes both.
- Closed rounds: Edit/Remove stay visible but `aria-disabled` with the tooltip "This round is closed..." (plus one
  sr-only description), clicks do nothing; the server refuses with 409 ROUND_CLOSED anyway. Add to rally stays hidden.
- Tyrant `decorate_application` now adds `joiner_strength` too, so the PUT response can replace a row as-is.
- Fixed on the way: the SVS table's horizontal scroller is `relative`; the Plan column's sr-only "Not in plan" text
  (position:absolute) escaped it and widened the page to 579px on a 390px phone.
- Known gaps: deleting a whole PROFILE (`DELETE /api/admin/profiles/{fid}`) still does not touch SVS plans (that
  route deletes applications in SQL, without the event hook); the What's new block title stays "Rallies from the
  players list" (shared with a parallel branch).

### Hero library foundation (for the planner, later)
- Data: `backend/gamedata/heroes.json` (version 1; 65 heroes: slug, name, troop, generation 1-17 or null for
  rare/epic, rarity, image) + `frontend/public/heroes/<slug>.webp` (256 px), built reproducibly by
  `scripts/heroes/build_heroes.py` from the hero-test scrape.
- `GET /api/heroes?max_gen=N&troop=` (public); default max_gen = the global setting **State hero generation**
  (`state_generation`, 1..17, default 17, core settings like `state_number`; edited in Event Management: Minister
  Settings and the SVS Heroes tab). Rare/epic heroes (no generation) are always included, `has_generation: false`.
- `shared/heroes/HeroCard.tsx`: big picture, name, troop icon, small "Gen N" (or the rarity), forwardRef + rest props
  so the future dnd-kit picker can wrap it; `HeroCredit` (© Century Games) shown once on every page with heroes;
  README "Credits". Admin "Heroes" tab = the filtered library by troop.

### MCP
`list_applications(event="svs", hours, vc, alliance, troop, min_camp, min_tier, svs_filters)`,
`get_svs_summary`, `add_player(event, fid, profile?, answers?)`, `get_heroes(max_gen?, troop?)` (public),
`set_state_generation(generation)` (admin). See docs/MCP.md.

### Known gaps / accepted
- No import of past SVS data; no per-hour capacity planning.
- Hero data is a one-off scrape (re-run the build script when new heroes ship; bump `version`).

## SVS battle planner (phase 2, p5/svs-planner, v2.2.0)
Owner brief: `catalogue/SVS-battle-setup-brief.md` (incl. its Decisions). Desktop-first in Event Management → SVS →
**Battle plan** (full-width tab), plus a phone-first read-only **shared plan view** `/svs/plan/<token>`.

### Decisions (owner)
- **SVS sign-up does not ask the role; the planner assigns leaders.** Pickers rank sign-ups by strength
  (FC number + tier summed over the three troop types, max 63) and show hours + Discord VC; no "calls rallies" preference.
- One plan per SVS round, a validated JSON document with a `revision` (table `svs_plans`, migration 5).
- `strategy`: `single` (one main group) | `main_counter` (one main + one counter). Up to 5 light `extra` groups
  (e.g. Turrets: name, players, notes) via "Add another group".
- Main/counter groups: name, alliance tag, notes, `min_requirements` per troop type `{min_camp FC1..FC10|null,
  min_tier 10|11|null}`. Shown on the plan view as the joining rules for "everyone else"; in the planner a named joiner
  below them gets a WARNING badge (never blocked).
- Leaders (unlimited, ordered per group): player, disguise `{pfp_hero, alias}` (what the ENEMY sees; collapsed when
  empty, at the top of the card), `split` ("Separate rally and garrison"), `rally {heroes[3], ratio}`, `garrison`
  (only when split), `pet_buff` `open|two_hours|last_hour|null`, ≤4 `named_joiners {player, rally {lead_hero,
  ratio?}, garrison? {lead_hero, ratio?}}`, `other_joiner_heroes {rally[≤4], garrison[≤4]}` (repeats allowed),
  ≤14 `extra_joiners {player}` (names only).
- Ratios: integers inf/lan/mks summing to 100. Joiners inherit the leader's ratio per side; an optional override per
  joiner per side. When split the SAME joiners have separate rally and garrison lead heroes + ratios.
- Pet buffs: a per-leader choice of three moments, labelled with real times from the round's battle start/duration
  ("At open (11:00 UTC)", "Two hours in (13:00 UTC)", "Last hour (15:00 UTC)"). No auto-assignment, no coverage warnings.
- Player ref: `{fid}` (a profile/sign-up) or quick add `{name}`; quick add WITH an FID creates the SVS sign-up via the
  admin add-player route; name-only stays in the plan, marked "not signed up".
- **Double booking**: a player (fid, or the same quick-add name, case-insensitive) appears ONCE across the plan (leader,
  named joiner, extra joiner or extra group). Server: 422 `DOUBLE_BOOKED` + `details.where` (group, leader label,
  position). UI: search results badge "Already with Rally Caller 01"; picking them is refused with that message;
  "Move here" is the explicit move.
- Hero choices: generation ≤ `state_generation`; rare/epic (no generation) allowed, listed after. A hero ALREADY in the
  stored plan stays valid when the generation is lowered (the planner flags it); new ones above the limit → 400.
- Autosave: every change saves (debounced ~0.8 s) with the revision; "Saved · just now". A stale revision → 409
  `PLAN_CONFLICT` and a conflict banner with Reload; nothing is overwritten silently. A failed save is not retried in a
  loop: the next edit or Retry saves.
- Share: 128-bit random token (stored + looked up by sha256); create (idempotent) / rotate ("New link": the old one dies
  at once) / disable ("Turn off sharing"). Per-plan toggle "Show real names to the state" (default ON) only affects our
  page: a disguised leader shows the alias + PFP hero, plus the real name when ON.

### Planner UI
- Toolbar: strategy switch, Add another group, hint, save status, Share popover (link, copy, new link, turn off,
  real-names toggle).
- Group columns side by side, distinct colour accents (theme tokens `team.main/counter/extra`) and labels; compact
  minimums editor (camp + tier select per troop type) and notes.
- Leader card: drag handle (dnd-kit, mouse/touch/keyboard; between groups and within a group; also a ⋮ "Move to
  Counter/Main" menu, up/down, remove), number badge, player name (hover = troops, hours, VC), disguise block, hero
  slots ×3 + ratio editor (three inputs, live total, stacked bar), split toggle, pet-buff segmented control (with
  times), named joiners (4 rows: search + lead hero slot(s) + collapsed ratio override + below-minimum badge),
  "Everyone else may use" slots, extra joiner chips + add-by-search.
- Sticky side panel: **Heroes** (big HeroCards, troop tabs, search; drag onto any slot, or click a slot then a hero:
  the next empty slot of that march arms itself; × clears; Esc disarms) and **Sign-ups** (unplaced, strongest first,
  filter by text/VC; drag onto a joiner row, the extra-joiner box or a group's "new leader" drop zone).
- Player search: ARIA combobox over the round's sign-ups (name, FID, alliance), strongest first, shows troop line,
  hours, VC, the "already placed" badge; "Quick add" at the bottom (name + optional FID).

### Add to rally (players table, v2.2.1)
Owner: "from the players page, it would be great to add to an already defined rally in the players table".
- Players tab table: a **Plan** column with the planner's wording: "Leader · Rally Caller 01 (Main alliance)",
  "Joiner 2 · Rally Caller 01 (Main alliance)", "Extra · FrostHeart (Counter alliance)", "Turrets", or "—" (leader =
  alias, else the leader's name, else "Rally leader N"; labels from `plan/labels.ts`, shared with the planner's
  "Already with …" badge). Deviation: the group is shown for joiners too (the brief's example omitted it).
- Filter `in_plan` yes|no as two count chips ("In plan: n", "Not in plan: n", counts for the filtered set) + a pill;
  same key in the URL, API, exports and MCP.
- Per row "Add to rally" (icon button → popover, `role=dialog`): the plan's EXISTING leaders grouped by main/counter
  with "Named n/4 · Extra n/14" (full leaders disabled); choose one, then "As named joiner" / "As extra joiner"
  (default and focused: named if there is room, else extra; the lead hero stays empty for the planner). Also "Make
  rally leader in <group>" (a new leader card) and "Add to <extra group>". A placed player sees "Now: …" and the
  buttons read "Move here …" (the planner's move: a moved leader leaves an empty card). No leaders yet: a message +
  "Open the Battle plan" (switches tab).
- Bulk: row checkboxes (+ select page), a sticky bar "N selected · Clear · Add N selected to rally…"; per leader "named
  places first, then extra" or "all as extra joiners", or an extra group. Already-placed players are skipped and named
  in the result, players that don't fit are named as "no room left" (never silently dropped).
- Safety: one server call `POST …/plan/place` applies the change atomically to the stored plan (other edits kept) with
  the menu's revision as `expected_revision`; on 409 the client re-reads and retries ONCE if the player's placement and
  the target's room are unchanged, else shows "The plan changed while you were choosing". 422s are shown translated
  (DOUBLE_BOOKED with where, RALLY_FULL); other 422s show the server message. An open Battle plan tab with an older
  revision gets the usual conflict banner on its next save; the tab reloads the plan whenever it is opened.

### Shared plan view (`/svs/plan/<token>`)
- Phone-first, 9 languages + RTL, noindex (meta + `X-Robots-Tag`), `Referrer-Policy: no-referrer`, no-store,
  rate-limited like the lookups; invalid/rotated/disabled token → friendly "not found" page (one answer for all).
- Per group (colour + name + tag + joining rules + notes) the leaders in order: alias/PFP (and real name per toggle),
  heroes as pictures with names, ratio bar + numbers, pet-buff moment with UTC time, named joiners (lead hero per side,
  own ratio only when overridden; a note says joiners otherwise use the leader's ratio), "everyone else" heroes,
  extra joiners; extra groups with their players. Battle times in UTC plus "your time".
- "Find me" (name or FID): highlights the player's place, scrolls to it and says it in a sentence
  ("You join Rally Caller 01 as joiner 2 (Main rallies)").

### Demo data
`scripts/demo/seed_svs.py --base-url … --password … [--plan] [--new-round]`: ~60 dummy sign-ups across 8 alliances
(fixed FIDs 990001…, seeded randomness: re-runs update the same rows), FC5-FC10, T10/T11, varied hours, VC; `--plan`
saves a sample main + counter plan (4 leaders, disguises, split, pet buffs, joiners, a Turrets group) if still empty.
Refuses the live site. Uses the admin token on every call (admin requests are not throttled).

### Known gaps / accepted
- Plan editing over MCP is limited to `svs_plan_place` (placing players; v2.2.1).
- No undo history (autosave + revision conflict only).

