# wos-events HTTP API (phase 1)

Base URL: same origin as the SPA (`http://127.0.0.1:8091` locally). All bodies are JSON (`Content-Type: application/json`).
The source of truth is `backend/core/*.py` and `backend/events/ministry/routes.py`; tests in `backend/tests/` exercise every endpoint.

## Conventions

- **Success**: a JSON object (lists are always wrapped, e.g. `{"rounds": [...]}`). `201` when something was created.
- **Errors**: always
  ```json
  {"error": "human readable message", "code": "MACHINE_CODE", "field": "answers.fire_crystals"}
  ```
  `field` is `null` unless the error is about one input (dotted path into the request body; `fid` = the URL FID).
  Optional `details` may appear.
- **Timestamps**: ISO-8601 UTC with `Z` (`2026-10-13T18:00:00Z`). Input datetimes may carry any offset; naive = UTC.
- **FID**: always a JSON **string** (never a number: FIDs above 2^53 and leading zeros must survive; `0040021` and
  `40021` are different players). A NEW profile needs digits only, 1-20 chars (surrounding whitespace is trimmed).
  Lookups match the FID exactly, then trimmed. Profiles imported from v1.4 keep their stored FID (the import trims
  stray whitespace when unambiguous) and stay readable AND writable under it, including non-digit legacy FIDs.
- **Absent strings** are `null`, not `''`.
- **Admin lists** (`/api/admin/events/{event}/rounds`, `/api/admin/rounds/{ref}/applications`,
  `/api/admin/profiles`) always include `"total"`; optional `?limit=` (1-1000) and `&offset=` return one page and echo
  `"limit"`/`"offset"`.
- **Events**: fixed keys `ministry`, `tyrant`, `svs`, `tal`. `tal` has no rounds yet. `svs` accepts free-form
  JSON `answers` until its phase lands; `tyrant` is strict (see "Frost Dragon Tyrant").

### Error codes

| HTTP | code | when |
|---|---|---|
| 400 | `VALIDATION_ERROR` | bad input; see `field` |
| 400 | `INVALID_JSON` | body missing / not a JSON object |
| 400 | `EVENT_HAS_NO_ROUNDS` | round/application call on `tal` |
| 400 | `EXPORT_NOT_SUPPORTED` | xlsx export for an event without an exporter |
| 401 | `UNAUTHORIZED` | no `Authorization` header |
| 401 | `INVALID_TOKEN` | forged / tampered / unknown token (incl. the old literal `admin-token`) |
| 401 | `TOKEN_EXPIRED` | token older than 12 h: log in again |
| 401 | `INVALID_PASSWORD` | login failed |
| 403 | `APPLICATIONS_CLOSED` | NEW application after the round's `closing_time` |
| 409 | `ROUND_CLOSED` | admin write (application edit/delete, assignments, auto-assign, publish, import, round settings) on a `closed` round; reopen it first |
| 429 | `TOO_MANY_ATTEMPTS` | admin login throttled after repeated failures; `Retry-After` header + `details.retry_after` seconds |
| 503 | `RETRY` | database busy (another write held the lock); retry after `Retry-After` seconds |
| 404 | `NOT_FOUND` | resource (profile, application, round, endpoint) not found |
| 404 | `UNKNOWN_EVENT` | event key not in the fixed set |
| 404 | `NO_CURRENT_ROUND` | event has no open round |
| 405 | `METHOD_NOT_ALLOWED` | |
| 409 | `ROUND_ALREADY_OPEN` | would create a second open round for an event |
| 409 | `CONFLICT` | concurrent write collided (e.g. two first submissions for one FID); retry |
| 500 | `INTERNAL_ERROR` | bug; details are logged server-side only |

## Auth

Admin endpoints (`/api/admin/**` except login) need `Authorization: Bearer <token>` (a bare token is also accepted, as in v1.4).
Tokens are signed with `SECRET_KEY` (itsdangerous `URLSafeTimedSerializer`, payload `{role}`), valid 12 hours.
Both roles (`admin`, `minister`) have identical permissions. Outside development the app refuses to start without a
real `SECRET_KEY` (missing, known placeholder or <16 chars) or with a well-known default password. A role whose
password env var is unset cannot log in. The v1.4 defaults `admin123`/`minister123` exist only with
`FLASK_ENV=development` + `ALLOW_INSECURE_DEV=1`. Tokens cannot be revoked individually: rotating a password does not
end existing sessions (≤12 h), rotating `SECRET_KEY` ends all of them.

Login throttling: after 5 failed logins from one client address, further attempts wait 1 s, 2 s, 4 s ... (max 15 min)
and get `429 TOO_MANY_ATTEMPTS` (the password is not checked while waiting). A global budget (30 failures/minute)
applies across all addresses. A success clears that address. The client address is the right-most
`TRUSTED_PROXY_HOPS` entry of `X-Forwarded-For` (default 1, Cloud Run).

### POST /api/admin/login
```json
// request
{"password": "..."}
// 200
{"token": "eyJyb2xlIjoiYWRtaW4ifQ.Zx...", "role": "admin", "expires_in": 43200}
// 401
{"error": "Invalid password", "code": "INVALID_PASSWORD", "field": null}
```

### GET /api/admin/me
`200 {"role": "admin"}` — cheap way for the UI to check a stored token.

## Public endpoints

### GET /health
`200 {"status": "healthy"}`

### GET /api/events
```json
{"events": [
  {"key": "ministry", "has_rounds": true,
   "current_round": {"id": 3, "name": "SVS week of 13 Oct", "status": "open",
                     "closing_time": "2026-10-12T18:00:00Z", "is_closed_for_new": false}},
  {"key": "tyrant", "has_rounds": true, "current_round": null},
  {"key": "svs", "has_rounds": true, "current_round": null},
  {"key": "tal", "has_rounds": false, "current_round": null}
]}
```

### GET /api/settings/public
`200 {"state_number": "2807"}` (default `"2694"` as v1.4)

### GET /api/profile/{fid}
```json
{"fid": "1001", "game_name": "Alice", "alliance": "ABC", "timezone": "Europe/London",
 "furnace_level": "FC5", "power": 123456789, "troops": {"infantry": 5}, "discord_id": "alice",
 "avatar_image": null, "stove_lv": null, "stove_lv_content": null}
```
404 `NOT_FOUND` if unknown. `avatar_image`/`stove_lv`/`stove_lv_content` are legacy, read-only (pre-Aug-2026 rows).
**Removed in 1c** (M6): `id`, `created_at`, `updated_at` (no consumer used them; admins get them from
`GET /api/admin/profiles/{fid}`).

### PUT /api/profile/{fid}
Partial profile update (or create; `game_name` required then). Same field rules as below. Players have no login, so
this has the same trust model as the application PUT (knowing the FID is enough). Intended for the MCP
`update_profile` tool. → `{"profile": {...public profile...}, "created": bool}` (201 when created).

### GET /api/events/{event}/current
Current (open) round with public settings. 404 `NO_CURRENT_ROUND`.
```json
{"id": 3, "event": "ministry", "name": "SVS week of 13 Oct", "status": "open",
 "closing_time": "2026-10-12T18:00:00Z", "is_closed_for_new": false,
 "settings": {"research_day": "tuesday", "show_fire_crystals": false,
              "time_slot_scheme": "exact_alignment", "published_days": ["monday"]},
 "created_at": "...", "updated_at": "..."}
```
`is_closed_for_new` = closing time has passed (new applications blocked, edits allowed).

### GET /api/events/{event}/current/application/{fid}
The player's application in the current round, or 404 `NOT_FOUND` → UI shows **"New application for <round>"**;
200 → **"Edit your application for <round>"**.
```json
{"fid": "1001", "event": "ministry", "round_id": 3, "round_name": "SVS week of 13 Oct",
 "answers": {"construction_speedups_days": 2.0, "research_speedups_days": 0.0,
             "troop_training_speedups_days": 0.0, "general_speedups_days": 1.5,
             "fire_crystals": 0, "refined_fire_crystals": 0, "fire_crystal_shards": 0,
             "time_slots_by_day": {"construction": ["10:00"], "research": [], "troop": []}},
 "updated_at": "2026-10-08T09:06:14Z"}
```
**Removed in 1c** from public application responses (M6): `id`, `player_id`, `profile_snapshot`, `created_at`.
The admin application endpoints keep the full shape (`id`, `player_id`, `profile_snapshot`, timestamps, `profile`).

### GET /api/events/{event}/previous-application/{fid}
"Use my last answers": the player's application from the most recent round **earlier** than the current round
(rounds ordered by id). Never the current round, never a later round, never another event. Same shape as above;
404 `NOT_FOUND` if none.

### PUT /api/events/{event}/current/application/{fid}
Upserts the profile and the player's application in the current round.
```json
// request
{"profile": {"game_name": "Alice", "alliance": "abc", "timezone": "Europe/London",
             "furnace_level": "FC5", "power": 123456789, "troops": {"infantry": 5}},
 "answers": {"construction_speedups_days": 2, "general_speedups_days": 1.5,
             "fire_crystals": 0, "refined_fire_crystals": 0, "fire_crystal_shards": 0,
             "research_speedups_days": 0, "troop_training_speedups_days": 0,
             "time_slots_by_day": {"construction": ["10:00", "11:00"], "research": ["05:00"], "troop": []}}}
// 201 (new) / 200 (edit)
{"created": true, "profile_created": true, "application": {...public application as above...},
 "profile": {...public profile...}}
```
Rules:
- `profile` fields are optional/partial for an existing profile (omitted fields are kept). `profile.fid`, if sent,
  must equal the URL FID.
- Profile validation: `game_name` ≤64 chars; `alliance` ≤3 chars, upper-cased; `timezone` ≤64; `furnace_level`
  a code `"FC1"`..`"FC10"` or `"1"`..`"30"` (case-insensitive; ints 1-30 accepted and stored as strings) or null;
  `discord_id` ≤64 or null; `power` int ≥0 or null; `troops` JSON object/array or null. A stored legacy value that breaks
  these limits (e.g. the v1.4 alliance `love`) is accepted when sent back unchanged and kept as stored.
- Ministry requires `game_name` and `alliance` (as v1.4).
- Ministry answers: the 4 speedup fields are numbers 0-99999 (decimals allowed); the 3 crystal fields are whole
  numbers 0-99999 (exception: a fractional value imported from v1.4, e.g. `12.5`, is accepted when re-sent
  unchanged and kept exactly); missing numbers default to 0. `time_slots_by_day` keys ⊆ {construction, research,
  troop}, values lists of `"HH:MM"` (deduplicated, returned sorted). The v1.4 `time_slots` list is accepted and copied to all three day types.
  Answers are replaced wholesale on each PUT (send the full set).
- After `closing_time`: if the player has no application in this round → 403 `APPLICATIONS_CLOSED` (nothing written).
  Existing applications stay editable until an admin closes the round.

### Ministry public (current round)

| | |
|---|---|
| `GET /api/events/ministry/current/heatmap` | `{"construction": {"10:00": 3}, "research": {...}, "troop": {...}}` |
| `GET /api/events/ministry/current/schedule` | `{"round_id": 3, "published_days": ["monday", "thursday"]}` (weekday order; only active days of the round) |
| `GET /api/events/ministry/current/schedule/{day}` | `day` must be monday/tuesday/thursday/friday, else 400 `VALIDATION_ERROR` (field `day`). Unpublished or inactive: `{"published": false, "day": "monday", "round_id": 3}`; published: `{"published": true, "day": "monday", "day_label": "Monday - Construction", "assignments": {"10:00": [{"game_name": "Alice", "alliance": "ABC"}]}, "round_id": 3}` — no points/resources |
| `GET /api/events/ministry/current/assignments/{fid}` | `{"round_id": 3, "published_days": [...], "assignments": {"monday": [{"time_slot": "10:00"}]}}`; 404 if no application this round. **Changed in 1c:** only PUBLISHED days are listed (v1.4 and phase 1 also returned drafts to anyone with the FID). |

### What an FID gives a stranger (M6, accepted by the owner)
Players never log in, so knowing (or guessing; FIDs are short numbers) an FID is enough to:
- **read**: the public profile (fid, game name, alliance, timezone, furnace level, power, troops, legacy avatar/stove),
  the current and the previous-round application (`answers`: 7 resource numbers + preferred hours per day,
  `round_id`, `round_name`, `updated_at`), and that player's slots on **published** days. Everyone can read the heat
  map, published schedules (game name + alliance per slot) and the published-day list.
- **write**: create profiles and applications for new FIDs; change any existing player's name, alliance, timezone,
  furnace level, power, troops; replace their current-round answers (e.g. zero their speedups so they drop at the next
  auto-assign). Free-form answers for tyrant/svs are limited to 50 KB per application.
- **not**: read or change anything admin-only (unpublished schedules, points, other players' resources, rounds,
  settings), internal ids, the profile snapshot, or timestamps other than the application's `updated_at`.
No per-IP limit on public writes and no audit trail yet (possible later: rate limits, an `audit_log`).

## Admin endpoints

### Global settings
- `GET /api/admin/settings` → `{"state_number": "2807"}`
- `PUT /api/admin/settings` `{"state_number": "2807"}` → same shape

### Round references and closed rounds
`{ref}` in `/api/admin/rounds/{ref}`, `/api/admin/rounds/{ref}/applications` and `/api/admin/rounds/{ref}/export` is a
round id or `current` (the open round of `?event=`, default `ministry`; 404 `NO_CURRENT_ROUND` if none).
A `closed` round is read-only: writes answer 409 `ROUND_CLOSED`. Reads and exports always work. Reopen with
`PUT /api/admin/rounds/{id}` `{"status": "draft"}` (or `"open"` if no other round of the event is open); other fields
may change in the same request.

### Rounds
- `GET /api/admin/events/{event}/rounds` → `{"rounds": [round + "application_count", ...], "total": N}` newest first.
- `POST /api/admin/events/{event}/rounds` `{"name", "status"?: "draft"|"open"|"closed" (default draft), "closing_time"?, "settings"?}` → 201 round.
  409 `ROUND_ALREADY_OPEN` if opening a second round.
- `GET /api/admin/rounds/{id}` → round (full settings).
- `PUT /api/admin/rounds/{id}` any of `{"name", "status", "closing_time" (null clears), "settings" (partial, merged)}` → round.
  Switching `research_day` drops the old research day from `published_days`.
  Changing ministry `time_slot_scheme` remaps that round's assignments to the nearest slot of the new grid
  (collisions: higher points keeps the slot) and adds `"remapped": <kept count>` to the response.
- `POST /api/admin/events/{event}/start-new-round` `{"name", "closing_time"?, "settings"?}` → 201
  `{"round": {...new open round...}, "closed_round": {...}|null}`. Closes the current round (nothing deleted).
  Settings carry over from the previous round; ministry resets `published_days` to `[]`.
  This replaces v1.4 "Remove all players".

Ministry round settings: `research_day` (`tuesday`|`friday`), `show_fire_crystals` (bool),
`time_slot_scheme` (`exact_alignment`|`max_slots`), `published_days` (list of active days). Unknown keys → 400.

### Applications
- `GET /api/admin/rounds/{ref}/applications?alliance=ABC` →
  `{"round_id": 3, "total": N, "applications": [application + "profile": {...current profile...} + ministry "monday_points", "research_points", "thursday_points", "research_day"]}`
  newest first. `alliance` is compared Unicode-case-insensitively.
- `GET /api/admin/applications/{id}` → one, same shape.
- `PUT /api/admin/applications/{id}` `{"profile"?: {...partial...}, "answers"?: {...partial, merged then validated...}}` → updated application. No closing-time check.
- `DELETE /api/admin/applications/{id}` → `{"deleted": true, "id": 12}`; also removes that player's assignments in the round. Profile kept.
- `GET /api/admin/rounds/{id}/export` → xlsx (event-specific; ministry below).

### Profiles
- `GET /api/admin/profiles?alliance=ABC&q=ali` → `{"profiles": [profile + "application_count"], "total": N}` (q matches FID
  or name, Unicode-case-insensitive, `%`/`_` literal).
- `GET /api/admin/profiles/{fid}` → profile.
- `PUT /api/admin/profiles/{fid}` `{game_name?, alliance?, timezone?, furnace_level?, power?, troops?, discord_id?}` → `{"profile": {...}, "created": bool}` (201 when created).
- `DELETE /api/admin/profiles/{fid}` → `{"deleted": true, "fid": "1001", "applications_deleted": 2}` (cascades applications + assignments in all rounds).

### Ministry (round-scoped)
`{ref}` = a ministry round id, or `current`. Days are `monday`, the round's `research_day`, `thursday`.

- `POST /api/admin/ministry/rounds/{ref}/auto-assign` `{"day": "monday"}` →
  ```json
  {"day": "monday", "round_id": 3,
   "assignments": {"00:00": [], "10:00": [{"id": 1, "player_id": 1, "fid": "1001", "game_name": "Alice",
                    "points": 2880, "preferred_times": ["10:00"], "avatar_image": null, "stove_lv": null,
                    "stove_lv_content": null, "alliance": "ABC", "is_sticky": false}], "...": []},
   "unassigned": [{...same card shape...}]}
  ```
  v1.4 algorithm: highest points first into the first free slot matching an hourly preference; sticky placements
  are kept; in `max_slots` with adjacent days (Mon↔Tue when research is Tuesday, Thu↔Fri when Friday) the shared 23:50
  boundary goes to the highest COMBINED two-day score and is mirrored onto the other day.
- `GET /api/admin/ministry/rounds/{ref}/assignments/{day}` → `{"day", "round_id", "assignments": {slot: [card + "assignment_id", "position", "is_assigned"]}, "unassigned": [card]}` (only occupied slots listed).
- `PUT /api/admin/ministry/rounds/{ref}/assignments/{day}` `{"assignments": {"10:00": [{"player_id": 1, "is_sticky": true}], ...}}` →
  `{"day", "round_id", "saved": 1}`. Replaces the day; first player per slot only; slot must exist in the round's scheme;
  player must have an application in the round and appear once. Shared 23:50 slot is synced.
- `POST /api/admin/ministry/rounds/{ref}/publish` `{"day": "monday"}` / `.../unpublish` → `{"round_id", "published_days": [...]}`
- `GET /api/admin/ministry/rounds/{ref}/export` → xlsx: sheets `Monday - Construction`, `Tuesday - Research` or
  `Friday - Research`, `Thursday - Troop Training` (assigned rows, then an UNASSIGNED PLAYERS section, as v1.4) and an
  `Unassigned` summary sheet (Day, FID, Alliance, Game Name, Points). Same as `/api/admin/rounds/{id}/export`.
- `GET /api/admin/ministry/rounds/{ref}/export-json` → download
  `{"version": 2, "exported_at" (UTC, ...Z), "round": {"id", "name", "settings"}, "players": [{fid, game_name, alliance, timezone, avatar_image, stove_lv, stove_lv_content, <7 numeric fields>, time_slots_by_day}]}`
- `POST /api/admin/ministry/rounds/{ref}/import` body = an export-json file (v2, or the v1.4 `{"players": [...]}` backup) →
  `{"round_id", "imported": 2, "updated": 0, "errors": 1, "error_details": [{"index": 3, "fid": "bad", "error": "...", "field": "fid"}]}`.
  Upserts profiles and applications in that round. Each entry is applied in its own savepoint: validation AND
  database errors are reported per entry in `error_details`.
- Excel exports write user text that starts with `= + - @`, TAB or CR as quote-prefixed text (never a formula). Ties
  in the UNASSIGNED section are ordered by player id.

## Frost Dragon Tyrant (`tyrant`)

Player calls are the generic ones with `{event}` = `tyrant`. Tyrant requires `profile.game_name` and
`profile.alliance`.

```json
// PUT /api/events/tyrant/current/application/{fid}
{"profile": {"game_name": "Tyra", "alliance": "woo", "discord_id": "tyra#0001", "furnace_level": "FC8",
             "power": 410500000,
             "troops": {"infantry": {"furnace_level": "FC5", "tier": 10}, "lancer": {"furnace_level": "30", "tier": 9},
                        "marksman": {"furnace_level": null, "tier": 11}}},
 "answers": {"availability": ["w1", "w3"], "discord_vc": true, "gem_spend": 10000,
             "roles": ["rally_leader", "joiner"], "language": "en"}}
```
- `answers.availability`: window ids of the current round (`GET /api/events/tyrant/current` → `settings.windows`),
  returned in window order. `discord_vc` bool (default false). `gem_spend` whole number 0-10^9 or null. `roles` ⊆
  `rally_leader, joiner, gathering, battle_mgmt, event_prep` (returned in that order). `language` one of the 9 UI
  languages or null. Any other key → 400 `VALIDATION_ERROR` (`field` = `answers.<key>`).
- `profile.troops` (tyrant submits only): keys ⊆ infantry/lancer/marksman, each null or `{furnace_level, tier}`;
  `furnace_level` a furnace code, `tier` 1-11 (the UI offers T8-T11). Stored with all three keys. Errors name the
  exact field, e.g. `profile.troops.infantry.tier`.

Round settings (`PUT /api/admin/rounds/{id}` `{"settings": {"windows": [...]}}`):
`windows` = 1-12 `{"id": "w1", "start": "11:01", "end": "11:15", "rush": true}` (UTC; id `[a-z0-9_]{1,24}`, unique;
end after start; sorted by start on save). Defaults: w1 11:01-11:15 rush, w2 11:15-13:00, w3 13:00-15:00,
w4 15:00-16:30, w5 16:30-18:00. Carried over by start-new-round.

Admin (`{ref}` = tyrant round id or `current`; a non-tyrant round id → 404):
- `GET /api/admin/tyrant/rounds/{ref}/applications?q=&alliance=&min_furnace=&sort=&dir=&limit=&offset=` →
  `{round_id, total, applications: [admin application + profile]}`. `q` matches FID, name or Discord ID
  (case-insensitive); `min_furnace` a code (FC5 = FC5 and above); `sort` ∈ submitted (default) | updated | name |
  alliance | fid | furnace (by ordinal) | power | gems, `dir` asc|desc (blanks always last).
- `GET /api/admin/tyrant/rounds/{ref}/summary?alliance=` →
  `{round_id, total, opening_rush, discord_vc, gem_spend_total, windows: [{id,start,end,rush,count}],
  alliances: [{alliance, count}], roles: {role: n}, troop_tiers: {infantry: {"T10": n, "none": n}, ...},
  furnace_levels: {"FC10": n, ..., "none": n}}` (furnace highest first).
- `GET /api/admin/tyrant/rounds/{ref}/export` (also `/api/admin/rounds/{id}/export`) → xlsx (sheet
  "Tyrant Poll Results" + "Summary"); `GET .../export.csv` → CSV (UTF-8 BOM). Columns: FID, In-Game Name, Alliance,
  Discord ID, one Yes/No column per window, Discord VC, Furnace Level (code), Power (M), Est. Max Gem Spend,
  <Troop> Furnace Level / T-Level ×3, five role Yes/No columns, Language, Submitted/Updated At (UTC). Formula-safe.
- Delete: `DELETE /api/admin/applications/{id}` (profile kept). Edit: `PUT /api/admin/applications/{id}`.

## v1.4 → v2 endpoint map (for the frontend rewire)

| v1.4 | v2 |
|---|---|
| `POST /api/player/submit` | `PUT /api/events/ministry/current/application/{fid}` |
| `GET /api/player/{fid}` | `GET /api/profile/{fid}` + `GET /api/events/ministry/current/application/{fid}` |
| `POST /api/player/check-duplicate` | `GET /api/profile/{fid}` (404 = free) |
| `GET /api/player/{fid}/assignments` | `GET /api/events/ministry/current/assignments/{fid}` |
| `GET /api/settings/research-day`, `show-fire-crystals`, `time-slot-scheme`, `published-days`, `application-closing-time` | `GET /api/events/ministry/current` (`settings`, `closing_time`, `is_closed_for_new`) |
| `GET /api/settings/state-number` | `GET /api/settings/public` |
| `GET /api/published-schedule/{day}` | `GET /api/events/ministry/current/schedule/{day}` |
| `GET /api/time-preferences/heatmap` | `GET /api/events/ministry/current/heatmap` |
| `PUT /api/admin/settings/{research-day,show-fire-crystals,time-slot-scheme}` | `PUT /api/admin/rounds/{id}` `{"settings": {...}}` |
| `PUT /api/admin/settings/application-closing-time` | `PUT /api/admin/rounds/{id}` `{"closing_time": ...}` |
| `PUT /api/admin/settings/state-number` | `PUT /api/admin/settings` |
| `PUT /api/admin/settings/publish` / `unpublish` | `POST /api/admin/ministry/rounds/{ref}/publish` / `unpublish` |
| `GET /api/admin/players` | `GET /api/admin/rounds/{id}/applications` |
| `PUT/DELETE /api/admin/player/{id}` | `PUT/DELETE /api/admin/applications/{id}` (application id, not player id) |
| `DELETE /api/admin/players/delete-all` | `POST /api/admin/events/ministry/start-new-round` |
| `POST /api/admin/assignments/auto-assign` | `POST /api/admin/ministry/rounds/{ref}/auto-assign` |
| `GET /api/admin/assignments/{day}` | `GET /api/admin/ministry/rounds/{ref}/assignments/{day}` |
| `POST /api/admin/assignments/update` | `PUT /api/admin/ministry/rounds/{ref}/assignments/{day}` |
| `GET /api/admin/export` | `GET /api/admin/rounds/{id}/export` |
| `GET /api/admin/players/export-json`, `POST .../import` | `GET /api/admin/ministry/rounds/{ref}/export-json`, `POST .../import` |

The v1.4 endpoints are **removed** (no compatibility shims); the v1.4 frontend will not work against this backend until rewired.

## Database & migrations

Tables: `schema_version`, `settings` (global), `profiles`, `rounds` (partial unique index: one `open` per event),
`applications` (UNIQUE(round_id, player_id)), `ministry_assignments` (round-scoped). Migrations live in
`backend/core/db.py` (`MIGRATIONS`). Pending migrations run at startup in ONE transaction taken with `BEGIN IMMEDIATE`
before the version is read — except the v1.4 import, which is explicit: on a v1.4 file the app refuses to start
until `python -m core.migrate` (or one boot with `MIGRATE_V14=1`) has run. See docs/DEPLOY-CUTOVER.md.

Migration 1 on a v1.4 file (detected by a `players` TABLE with `construction_speedups_days`): backup copy
`<db>.pre-v2-<UTCtimestamp>.bak` (SQLite backup API; written as `.bak.partial` and renamed after COMMIT, removed if the
import fails), rename old tables to `legacy_*`, create the v2 schema, then:
players → profiles (same ids), one open ministry round "Imported from previous system" with the old research_day,
show_fire_crystals, time_slot_scheme, published days and closing time, one application per player (resource columns +
time preferences by day_type), assignments → `ministry_assignments` with sticky flags. If the old DB had no stored
`time_slot_scheme`, it is inferred from stored slots (`:20`/`:50` ⇒ `max_slots`, else `exact_alignment`). Orphan
assignments whose player no longer exists are left in `legacy_assignments` only. Crystal values are kept exactly
(fractions included), preferred hours sorted, FID whitespace trimmed when unambiguous. Re-running is a no-op.

Migration 3: `profiles.discord_id TEXT` (nullable). Migration 4: `profiles` rebuilt with `furnace_level TEXT`
codes (ints 1-30 → '1'..'30', invalid → NULL; troop `furnace_level` likewise).

Migration 2 (every database): guard VIEWs `players`, `time_preferences`, `assignments`, `admin_users` (v1.4 columns,
no rows) and triggers that reject the v1.4 round-setting keys in `settings`, so a stray v1.4 instance fails loudly.
