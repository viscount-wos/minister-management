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
| 429 | `RATE_LIMITED` | too many public FID lookups / submissions from one IP (see "Rate limits"); `Retry-After` header + `details.retry_after` seconds |
| 503 | `RETRY` | database busy (another write held the lock); retry after `Retry-After` seconds |
| 404 | `NOT_FOUND` | resource (profile, application, round, endpoint) not found |
| 404 | `UNKNOWN_EVENT` | event key not in the fixed set |
| 404 | `NO_CURRENT_ROUND` | event has no open round |
| 405 | `METHOD_NOT_ALLOWED` | |
| 409 | `ROUND_ALREADY_OPEN` | would create a second open round for an event |
| 409 | `CONFLICT` | concurrent write collided (e.g. two first submissions for one FID); retry |
| 500 | `INTERNAL_ERROR` | bug; details are logged server-side only |

### Rate limits (public player endpoints, v2.1.0)
In-process sliding window per client IP (`TRUSTED_PROXY_HOPS` decides which `X-Forwarded-For` entry is the
client, as for the login throttle; production runs ONE instance so per-process state is enough):

| Bucket | Endpoints | Default | Env |
|---|---|---|---|
| lookup | `GET /api/profile/{fid}`, `GET /api/events/{event}/current/application/{fid}`, `GET /api/events/{event}/previous-application/{fid}`, `GET /api/events/ministry/current/assignments/{fid}` | 30 / minute | `RATE_LIMIT_LOOKUPS_PER_MIN` |
| submit | `PUT /api/events/{event}/current/application/{fid}`, `PUT /api/profile/{fid}` | 10 / minute | `RATE_LIMIT_SUBMITS_PER_MIN` |

`0` disables a bucket (the e2e compose and the backend/MCP test suites do). Over the limit: `429 RATE_LIMITED`
with `Retry-After`. Requests with a valid admin token are not limited. Code: `backend/core/ratelimit.py`.

### Response headers (every response, v2.1.0)
`backend/core/security.py`: `Content-Security-Policy` (`default-src 'self'`; `script-src 'self'` + the SHA-256 of the
inline pre-paint script in the served `index.html`, computed at runtime; `style-src 'self'`; `img-src 'self' data:`;
`connect-src 'self'`; `object-src 'none'`; `base-uri 'self'`; `form-action 'self'`; `frame-ancestors 'none'`),
`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`,
`Permissions-Policy` (camera, microphone, geolocation, payment, usb off), `Cross-Origin-Opener-Policy: same-origin`,
and `Strict-Transport-Security: max-age=31536000; includeSubDomains` in production (FLASK_ENV != development) or
when the request came over https. Text responses are brotli/gzip compressed (Flask-Compress). `/assets/*` (hashed
names) are `Cache-Control: public, max-age=31536000, immutable` (a missing asset is a 404, never index.html);
index.html / SPA routes and `/api/*` are `no-cache` (`/api/admin/*` `no-store`).

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
`200 {"state_number": "2807", "state_generation": 17}` (`state_number` is `null` until an admin sets it; v1.4 defaulted
to `"2694"`, the UI now hides its welcome line instead). `state_generation` (v2.2.0) = the state's hero generation,
1..the newest generation in the hero library (17), default 17.

### GET /api/heroes (v2.2.0)
The hero library (foundation of the SVS planner). `?max_gen=1..17` (default: `state_generation`), `?troop=infantry|
lancer|marksman` (optional). Bad values → 400 `VALIDATION_ERROR` (`field` = `max_gen` / `troop`).
```json
{"version": 1, "state_generation": 17, "max_gen": 8, "max_generation": 17,
 "attribution": "Hero names and artwork (c) Century Games. ...", "total": 37,
 "heroes": [{"slug": "smith", "name": "Smith", "troop": "infantry", "generation": null, "has_generation": false,
             "rarity": "rare", "image": "/heroes/smith.webp"},
            {"slug": "jeronimo", "name": "Jeronimo", "troop": "infantry", "generation": 1, "has_generation": true,
             "rarity": "mythic", "image": "/heroes/jeronimo.webp"}, ...]}
```
Rare/epic heroes have no generation and are ALWAYS included (`has_generation: false`). Order: no-generation heroes
first, then by generation. Data: `backend/gamedata/heroes.json` (versioned; built by `scripts/heroes/build_heroes.py`
from the hero-test scrape); images are static SPA files `frontend/public/heroes/<slug>.webp` (256 px WebP).
Hero names and art © Century Games: any page that shows heroes carries a credit line.

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
- `GET /api/admin/settings` → `{"state_number": "2807", "state_generation": 17}`
- `PUT /api/admin/settings` any of `{"state_number": "2807", "state_generation": 8}` → same shape. `state_generation`
  is a whole number 1..17 (int or digit string); everything is validated before anything is written. MCP:
  `set_state_generation`.

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
- `PATCH /api/admin/rounds/{ref}` `{"name"}` (only the name; 1-100 chars) → round. Works on ANY round, closed ones
  included (the name is a label, e.g. renaming "Imported from previous system"). MCP: `rename_round`.
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
- `POST /api/admin/rounds/{ref}/applications` (v2.2.0, every event) **"Add player"**: body `{"fid", "profile"?: {...},
  "answers"?: {...}}` → 201 the new application (admin shape: ids, profile, event decorations such as ministry points
  or `joiner_strength`) + `"profile_created": bool`. `fid` required (a NEW profile needs a canonical digits-only FID
  and `profile.game_name`; an existing profile needs nothing else). Uses the event's own validation in ADMIN mode:
  answers a player must give (SVS hours/VC, SVS troop levels) may be blank; anything sent must be valid (SVS
  tiers 10/11, tyrant window ids, ...). Profile troops merge (see SVS). No closing-time check; closed rounds → 409
  `ROUND_CLOSED`. FID already signed up in that round → **409 `APPLICATION_EXISTS`** ("FID … already has a sign-up in
  this round; edit that one instead"). `{ref}` = id or `current` + `?event=`. MCP: `add_player`.
- `GET /api/admin/applications/{id}` → one, same shape.
- `PUT /api/admin/applications/{id}` `{"profile"?: {...partial...}, "answers"?: {...partial, merged then validated...}}` → updated application. No closing-time check. Validated in admin mode (SVS: blanks allowed).
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
{"profile": {"game_name": "Tyra", "alliance": "woo", "discord_id": "tyra#0001", "power": 410500000,
             "troops": {"infantry": {"furnace_level": "FC5", "tier": 10}, "lancer": {"furnace_level": "FC9", "tier": 9},
                        "marksman": {"furnace_level": null, "tier": 11}}},
 "answers": {"availability": ["w1", "w3"], "discord_vc": true, "gem_spend": 10000,
             "roles": ["rally_leader", "joiner"], "language": "en"}}
```
- `answers.availability`: window ids of the current round (`GET /api/events/tyrant/current` → `settings.windows`),
  returned in window order. `discord_vc` bool (default false). `gem_spend` whole number 0-10^9 or null. `roles` ⊆
  `rally_leader, joiner, gathering, battle_mgmt, event_prep` (returned in that order). `language` one of the 9 UI
  languages or null. Any other key → 400 `VALIDATION_ERROR` (`field` = `answers.<key>`).
- `profile.troops` (tyrant submits only): keys ⊆ infantry/lancer/marksman, each null or `{furnace_level, tier}`;
  `furnace_level` is that troop type's CAMP level, `tier` 1-11 (the UI offers T8-T11). Stored with all three keys.
  Errors name the exact field, e.g. `profile.troops.infantry.tier`.
- **No main furnace (owner decision p2e)**: Tyrant does not ask the city furnace. A `profile.furnace_level` sent
  on a tyrant submit or tyrant admin edit is IGNORED (not validated, not stored), so older clients keep working and
  the shared profile's furnace (asked by Minister) is left alone. Tyrant admin rows, summary and exports carry no
  furnace; the generic profile routes still return it.
- **Fire Crystal camps only (owner rule p2d)**: on tyrant submits (player and admin edit) every
  `profile.troops.<type>.furnace_level` must be `FC1`..`FC10` (or null); a pre-FC code `1`..`30` →
  `VALIDATION_ERROR` with that field. Any combination of camp level and tier is allowed. The generic profile /
  Minister routes still accept `1`..`30`. Camp values stored earlier (pre-FC) are not migrated: they are returned
  and exported as stored, and only rejected when re-sent on a tyrant submit. The API keeps every troop field
  optional; the Tyrant wizard requires each camp level + tier.

Round settings (`PUT /api/admin/rounds/{id}` `{"settings": {"windows": [...]}}`):
`windows` = 1-12 `{"id": "w1", "start": "11:01", "end": "11:15", "rush": true}` (UTC; id `[a-z0-9_]{1,24}`, unique;
end after start; sorted by start on save). Defaults: w1 11:01-11:15 rush, w2 11:15-13:00, w3 13:00-15:00,
w4 15:00-16:30, w5 16:30-18:00. Carried over by start-new-round.

Admin (`{ref}` = tyrant round id or `current`; a non-tyrant round id → 404):
- **Filters** (query params, all optional, combined with AND; the SAME set on list, summary and both exports, so a
  filtered view, its counts and its download agree; the admin UI keeps the same keys in its own URL). Parser:
  `backend/events/tyrant/filters.py`. A bad value → 400 `VALIDATION_ERROR` with `field` = the parameter.

  | param | meaning |
  |---|---|
  | `q` | FID, in-game name or Discord ID contains (case-insensitive) |
  | `alliance` | one tag or a comma list (any of them), case-insensitive |
  | `min_power`, `max_power` | absolute power (whole numbers; the UI converts from millions) |
  | `min_gems`, `max_gems` | per-player est. max gem spend (a blank never matches a bound) |
  | `windows` | comma list of window ids: available in ALL of them |
  | `rush` | `1`: available in at least one opening-rush window |
  | `vc` | `yes` / `no` (`any` = no filter) |
  | `troop` | `infantry` / `lancer` / `marksman` / `all` (default): which troop types `min_camp`/`min_tier` apply to |
  | `min_camp` | `FC1`..`FC10`: camp level at least this; pre-FC and blank camps never match |
  | `min_tier` | `1`..`11` or `T11`: tier at least this |
  | `infantry_camp`, `lancer_camp`, `marksman_camp` | EXACT camp level of that type: a code (also legacy `25`) or `none` |
  | `infantry_tier`, `lancer_tier`, `marksman_tier` | EXACT tier of that type: `1`..`11`/`T11` or `none` |
  | `roles` + `roles_mode` | comma list of role ids; `any` (default: has any of them) or `all` |
  | `submitted_from`, `submitted_to` | `YYYY-MM-DD` (UTC, inclusive) |
  | `days` | submitted in the last N days (1-3650) |

  "FC10 camps with T11" = `?min_camp=FC10&min_tier=11` (troop defaults to all three); "who has T11" = `?min_tier=11`.
  There is no main-furnace filter (p2e); an old URL's `min_furnace` is ignored like any unknown parameter.
- `GET /api/admin/tyrant/rounds/{ref}/applications?<filters>&sort=&dir=&limit=&offset=` →
  `{round_id, total, applications: [admin application + profile + joiner_strength]}` (`total` after filters).
  `sort` ∈ submitted (default) | updated | name | alliance | fid | power | gems | strength,
  `dir` asc|desc (blanks always last). **Joiner strength** = Σ over infantry, lancer, marksman of (camp FC number,
  FC1=1 .. FC10=10, pre-FC or blank = 0) + (tier number, blank = 0): 0..63, 63 = FC10 camps with T11 everywhere;
  `null` when no camp level or tier is filled in at all.
- `GET /api/admin/tyrant/rounds/{ref}/summary?<filters>` → counts for the FILTERED set:
  `{round_id, round_total (unfiltered), filters (the active, canonical filters), alliance_options (every tag of the
  round, unfiltered), total, opening_rush, discord_vc, windows: [{id,start,end,rush,count}],
  alliances: [{alliance, count}], roles: {role: n}, troop_tiers: {infantry: {"T11": n, ..., "none": n}, ...},
  camp_levels: {infantry: {"FC10": n, ..., "FC1": n, "25": n, "none": n}, ...}}` (highest first; legacy pre-FC
  codes after FC1; blanks last). No main-furnace counts (p2e) and no aggregate gem total (owner rules).
- `GET /api/admin/tyrant/rounds/{ref}/export?<filters>` (also `/api/admin/rounds/{id}/export`, unfiltered) → xlsx
  (sheet "Tyrant Poll Results" + "Summary" with camp-level and tier counts per troop type); `GET .../export.csv?<filters>`
  → CSV (UTF-8 BOM). Columns: FID, In-Game Name, Alliance, Discord ID, one Yes/No column per window, Discord VC,
  Power (M), Est. Max Gem Spend, `<Troop> Camp Level` / `<Troop> Tier` ×3 (Infantry, Lancer,
  Marksman), Joiner Strength, five role Yes/No columns, Language, Submitted/Updated At (UTC). Formula-safe.
- Delete: `DELETE /api/admin/applications/{id}` (profile kept). Edit: `PUT /api/admin/applications/{id}`.

## SVS (`svs`, v2.2.0)

Player calls are the generic ones with `{event}` = `svs`.

```json
// GET /api/events/svs/current -> settings
{"battle_start": "11:00", "battle_hours": 5, "hours": ["11:00", "12:00", "13:00", "14:00", "15:00"]}
// PUT /api/events/svs/current/application/{fid}
{"profile": {"game_name": "Sva", "alliance": "woo",
             "troops": {"infantry": {"furnace_level": "FC10", "tier": 11}, "lancer": {"furnace_level": "FC9", "tier": 10},
                        "marksman": {"furnace_level": "FC10", "tier": 11}}},
 "answers": {"hours": ["12:00", "13:00"], "discord_vc": true, "language": "en"}}
```
- **Round settings**: `battle_start` "HH:MM" UTC (default "11:00"), `battle_hours` 1-24 (default 5); public settings
  add the derived `hours` (start, start+1h, ... wrapping past midnight). Carried over by start-new-round. Other keys → 400.
- **Answers** (player submit, all required): `hours` ⊆ the round's hours, at least one (returned in battle order);
  `discord_vc` bool; `language` or null. Unknown key → 400. **No role** (owner decision: SVS sign-up does not ask
  the role; the battle planner assigns leaders): a `role` sent by an old client is ignored (not stored, no 400);
  roles stored before the change stay in the data but are not shown, filtered or exported.
  An hour the admin has since removed (start/duration changed) is kept when re-sent unchanged; a new unknown hour → 400.
  Admin create/edit: every answer may be blank (`hours: []`, `discord_vc: null`).
- **Profile**: `game_name`; `alliance` required only when the shared profile has none (new player); `troops`: what is
  SENT must be FC1-FC10 camps and tiers **10 or 11 only** (`T11`/`11`; T8/T9 → 400 naming e.g.
  `profile.troops.infantry.tier`); it is MERGED into the shared profile, and a player submit then needs the merged
  troops complete (FC camp + T10/T11 for all three types), so a returning player with valid stored troops may omit
  them, while a stored T8/T9 or pre-FC camp (e.g. from Frost Dragon Tyrant) must be replaced. Ignored (dropped, never
  stored through SVS): `furnace_level`, `power`, `discord_id`, `timezone`.
- **Troop merge rule** (shared profile, `core/troops.py`; SVS and, since v2.2.0, Frost Dragon Tyrant): per troop type
  and per field (camp level, tier) a value sent replaces the stored one; a blank/missing value never clears it; types,
  fields and extra keys not sent stay as stored.
- **Admin**: `GET /api/admin/svs/rounds/{ref}/applications?<filters>&sort=submitted|updated|name|alliance|fid|strength|hours
  &dir=&limit=&offset=` → `{round_id, total, applications}` (current profile, `joiner_strength` as Tyrant, no furnace).
  `GET .../summary?<filters>` → `{round_id, round_total, filters, total, avg_hours (battle hours per player,
  1 decimal), all_t11 (T11 in all three troop types), discord_vc, hours: [{hour, count}], alliances, troop_tiers, camp_levels, alliance_options}`.
  `GET .../export?<filters>` (xlsx: "SVS Sign-ups" + "Summary") and `.../export.csv?<filters>`: FID, In-Game Name,
  Alliance, one Yes/No column per hour (`11:00 UTC`), Discord VC, camp level + tier ×3, Joiner Strength,
  Language, Submitted/Updated At. Also `GET /api/admin/rounds/{id}/export` (unfiltered xlsx).
- **Filters** (one parser `events/svs/filters.py`, list + summary + exports + MCP; same keys in the admin URL; AND):
  `q` (FID/name), `alliance` (comma list), `hours` (comma list: attends ALL), `vc` yes|no|none,
  `troop` + `min_camp` (FC code) + `min_tier` (10/11), exact `<type>_camp` / `<type>_tier` (chips; `none` = blank),
  `submitted_from`/`submitted_to`, `days`, `in_plan` yes|no (placed anywhere in the round's battle plan; v2.2.1).
  Bad values → 400 naming the parameter. List rows carry `plan_place` (`{position: leader|named_joiner|extra_joiner|
  extra_group, group_id, group_kind, leader_id, slot}` or null); the summary adds `plan: {in, out}`.


### SVS battle planner (v2.2.0)
- `GET /api/admin/svs/rounds/{ref}/plan` (admin) → `{round_id, round_name, revision (0 = never saved), updated_at,
  plan, share: {enabled, token, path, created_at}, battle: {start, end, hours}, pet_buff_times: {open, two_hours,
  last_hour}, state_generation, people: {fid: {game_name, alliance, signed_up}}, view}` (`view` = the resolved read-only
  plan, as the public view but real names always shown). Before the first save: an empty main + counter plan.
- `PUT /api/admin/svs/rounds/{ref}/plan` body `{revision, plan}` → the GET shape with `revision + 1`.
  `revision` must be the one loaded, else **409 `PLAN_CONFLICT`** (`details.revision` = current; nothing written).
  400 `VALIDATION_ERROR` (`field` = plan path, e.g. `plan.leaders[0].rally.ratio`; a hero above the state generation →
  `details.hero`), **422 `DOUBLE_BOOKED`** (`details = {group_id, group_name, group_kind, leader_id, leader_label,
  position: leader|named_joiner|extra_joiner|extra_group}`), 409 `ROUND_CLOSED`.
  Plan document: `{strategy: single|main_counter, show_real_names, groups: [{id, kind: main|counter|extra, name,
  alliance_tag?, notes?, min_requirements? {infantry|lancer|marksman: {min_camp, min_tier}}, players? (extra only)}],
  leaders: [{id, group_id, order, player, disguise {pfp_hero, alias}, split, rally {heroes[3], ratio {inf,lan,mks}},
  garrison?, pet_buff, named_joiners[≤4] {player, rally {lead_hero, ratio?}, garrison?}, other_joiner_heroes {rally[≤4],
  garrison[≤4]}, extra_joiners[≤14] {player}}]}`; player = `{fid}` or `{name}`; ratios = integers summing to 100.
- `POST /api/admin/svs/rounds/{ref}/plan/place` (v2.2.1, "Add to rally") body `{fid | fids: [≤100], as:
  auto|named|extra|leader|group (default auto), leader_id?, group_id?, slot? (0-3, named), move?: bool,
  expected_revision?: int}`. Applied atomically to the STORED plan (same validation + double booking as PUT), so other
  editors' changes are kept. `auto` = named joiner if the leader has a free named slot (of 4), else extra (of 14);
  `named`/`extra`/`auto` need `leader_id`; `leader` + `group_id` (main/counter) = a NEW leader card, `leader` +
  `leader_id` = fill an EMPTY card; `group` + `group_id` = an extra group. A player already elsewhere: one `fid` →
  **422 `DOUBLE_BOOKED`** (details as PUT) unless `move: true` (taken out of the old place first, like the planner's
  Move here); `fids` → listed in `result.skipped`. No room: `fid` → 422 `RALLY_FULL` (`details {named_used, named_max,
  extra_used, extra_max, leader_id, position}`) / `GROUP_FULL` / `SLOT_TAKEN`; `fids` → `result.overflow`. 404
  `LEADER_NOT_FOUND` / `GROUP_NOT_FOUND` / `PLAYER_NOT_FOUND` (no profile; bulk → `result.not_found`), 409
  `PLAN_CONFLICT` (only when `expected_revision` is stale), 409 `ROUND_CLOSED`, 400 `VALIDATION_ERROR` (`as`, `slot`,
  `group_id` of the wrong kind, `fids`). → the GET shape (revision +1 only when something changed) + `changed` +
  `result {placed: [{player, as, group_id, leader_id, slot, from?}], moved, unchanged: [{player, where}], skipped:
  [{player, reason: already_placed, where}], overflow, not_found}`.
- `POST /api/admin/svs/rounds/{ref}/plan/share` body `{action: create|rotate|disable}` → `{round_id, share}`. create is
  idempotent; rotate = new 128-bit token (old link dies at once); disable = off. Does not change the revision.
- `GET /api/svs/plan/{token}` (public, rate-limited like lookups; `X-Robots-Tag: noindex`, `Referrer-Policy:
  no-referrer`, `Cache-Control: no-store`) → `{round_name, revision, updated_at, attribution, battle, pet_buff_times,
  show_real_names, groups: [{…, leaders: [{label, alias, pfp_hero, player?, rally {heroes, ratio, other_joiner_heroes},
  garrison?, pet_buff, pet_buff_time, named_joiners, extra_joiners}]}]}` (heroes resolved to `{slug, name, troop,
  image}`; players as `{name, fid, alliance, signed_up}` so Find me works by FID). Unknown/rotated/disabled token → 404 `PLAN_NOT_FOUND`.

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
