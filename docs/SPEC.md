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
