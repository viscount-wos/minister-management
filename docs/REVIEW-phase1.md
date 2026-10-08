# Phase 1 backend: independent review + v1.4 parity (milestone 1b)

Reviewer: separate agent, did not write this code. Branch `p1b/parity-review`, based on `c8c2a61`
(p1/integration). Compared against v1.4.0 as live (`5454016`). No backend/frontend code changed.

## Verdict

**Ministry logic is a faithful port.** On 15 dummy v1.4 databases (3 seeds, Tuesday/Friday research,
both slot schemes, 300-player, and "no stored scheme" installs), with 1,652 step comparisons, every
difference is explained by one of:

- the documented deviations,
- cosmetic changes the docs don't mention,
- or **two narrow data-migration regressions**.

Neither regression touches the algorithms. The points maths is identical, and so are the auto-assign
choices (given the documented sorted preference walk), sticky handling, the shared 23:50 combined-score
winner and its mirroring, manual saves, publish/unpublish, the scheme-switch remap, the Excel layout and
the closing-time rule. With the crystal truncation neutralised, the harness finds **zero** unexplained
differences, and its self-test proves it would catch a real logic bug.

**Do not deploy yet.** Three things block it (H1 to H3): the migration runs implicitly at startup on the
shared production file, so Cloud Run revision overlap or a rollback breaks v1.4 or strands data;
`max-instances 3` on GCS FUSE; and the frontend on this branch still calls the removed v1.4 endpoints.

---

## 1. Parity results

`python3 scripts/parity/run_parity.py` (exit 1 because the two regressions below are real).
`--self-test` injects a wrong shared-slot winner into the new app at runtime. The harness flags 7
unexplained regressions (S2 auto-assign, assignments and schedule) → **SELF-TEST PASSED**.

```
scenario             steps   OK  EXP BENIGN REGR pref-order* hash-sens**  verdict (C=crystal truncation, F=FID whitespace, ?=unexplained)
s2807-tue-max          112   63    1     12   36          22          48  REGRESSIONS (C:29 F:7)
s2807-tue-exact        108   59    1     12   36          22          48  REGRESSIONS (C:29 F:7)
s2807-fri-max          112   63    1     12   36          22          48  REGRESSIONS (C:29 F:7)
s2807-fri-exact        108   59    1     12   36          22          48  REGRESSIONS (C:29 F:7)
s7-tue-max / s7-tue-exact / s7-fri-max / s7-fri-exact             (identical counts)  REGRESSIONS (C:29 F:7)
s42-tue-max / s42-tue-exact / s42-fri-max / s42-fri-exact         (identical counts)  REGRESSIONS (C:29 F:7)
s99-fri-max-300p       112   63    1     12   36          22          48  REGRESSIONS (C:29 F:7)
noscheme-max           112   63    1     12   36          22          48  REGRESSIONS (C:29 F:7)
noscheme-exact         108   59    1     12   36          22          48  REGRESSIONS (C:29 F:7)
```

`?` (unexplained) is **0 in every scenario**.

- **pref-order:** steps where live v1.4 (hash-ordered preferences) differs from the new app, but v1.4
  with the documented sorted walk matches.
- **hash-sens:** steps where live v1.4's own output changes with `PYTHONHASHSEED`. The documented fix is
  real: the live scheduler is nondeterministic across restarts.

### Regressions (both are migration/data, not algorithm)

| id | root cause | effect in the harness |
|---|---|---|
| C | `core/db.py:301-303` migrates crystals with `_num(..., integer=True)`, so `12.5` fire crystals becomes `12` and `7.75` shards becomes `7` | Fixture "Half Crystal": Monday 25,000 → 24,000 and research 7,750 → 7,000 points. Every list that ranks by points shifts (29 steps per scenario). Against `old_int` (v1.4 with the values pre-truncated) all 29 steps match exactly. See M1. |
| F | Legacy FID `'330000777 '` (trailing space) becomes unreachable: `get_profile_row` strips (`core/profiles.py:39`) | That player's public assignments go from 200 to 404 and lookup from 200 to 404. A resubmit forks a second profile and application (player count +1). See M2. |

### Expected (documented)

- The preference walk is sorted. v1.4 iterated a set, so slot choice depended on hash order: 22 steps
  per scenario differ from live v1.4 and match the sorted oracle.
- `preferred_times` on cards is now that day's own preferences.
- The Excel export has an extra `Unassigned` sheet. Day sheet names, headers (12 columns, identical),
  row counts and row contents match. The "UNASSIGNED PLAYERS" section is identical except for the order
  of tied rows.
- No stored `time_slot_scheme`: the scheme is inferred from the stored slots. A v1.4 restart would have
  pinned `max_slots`.
- The scheme-switch remap count excludes orphan rows.
- A 4-character alliance (`love`) is rejected on resubmit (SPEC: ≤3 characters).

### Benign (undocumented, cosmetic → add a line to SPEC)

1. Card and export string fields return `''` instead of `null` for alliance, avatar, stove_lv_content
   and timezone (`events/ministry/logic.py:186-190, 211-214`).
2. Tied-points order in the Excel UNASSIGNED section and in the unassigned lists. The new app orders
   ties by `created_at DESC`; v1.4's Excel used `id ASC` (`logic.py:165, 509-510`).
3. Hours inside `time_slots_by_day` keep insertion order. v1.4 read them through the unique index, so
   they came back sorted (`core/db.py:265-266`).
4. The heatmap no longer counts preference rows of deleted players. v1.4 counted these orphans (3 in the
   fixture). The new behaviour is the correct one.

Verified explicitly in every scenario:

- Sticky rows are never lost by auto-assign (`sticky_kept` checks).
- The shared 23:50 winner is the same player as v1.4 at each stage, including the combined-score pick
  after stickies are cleared (S2) and the mirror after a manual move (S3). Both days always hold the
  same player.
- Publish/unpublish and the public schedules are identical.
- export-json content is identical apart from the benign items above.
- Closing time: an edit of an existing application is accepted and a new one gets 403, in both apps.

---

## 2. Findings

Each finding has a severity, a file:line, why it matters and a suggested fix. Evidence comes from
`scripts/parity/probe_migration.py` unless noted.

### Critical
None found in the backend. There is no auth bypass and no SQL injection. Every `/api/admin/**` route
(url_map sweep) returns 401 both without a token and with the literal `admin-token`.

### High

**H1. The v1.4 migration runs implicitly at startup on the shared production DB, so revision overlap or
a rollback breaks v1.4 or strands data.**
`backend/app.py:70` → `core/db.py:61-63, 334-353`.

Cloud Run starts the new revision (which migrates) while the old v1.4 revision still serves traffic.
From then on, every v1.4 request hits renamed tables (`no such table: players` → 500).

If the deploy is rolled back, or the old instance restarts, v1.4's `init_db` recreates empty `players`,
`assignments` and `time_preferences` and shares the new `settings` table. Probe result: v1.4 accepted a
submit (200), and it **landed in a ghost `players` table**. The new app never sees it: `migrate()` is a
no-op (version 1), and the v2 profile count stays 0. To players the system looks empty, and their
submissions are silently lost.

Fix:
- Make the v1.4 import opt-in, e.g. env `MIGRATE_V14=1` or a one-off `flask migrate` job, so that a
  normal boot on a legacy file refuses to start.
- Write a cut-over runbook:
  1. Maintenance window: scale v1.4 to 0, or set it read-only.
  2. Copy the bucket object (or enable GCS object versioning).
  3. Deploy with `--max-instances 1`.
  4. Verify counts.
  5. Rollback means restoring the `.bak`, not just redeploying v1.4.
- Optional guard: after migrating, create a VIEW named `players` (and the other v1.4 table names).
  v1.4's `CREATE TABLE IF NOT EXISTS` then becomes a no-op and its writes fail loudly instead of
  silently.

**H2. Multiple instances on GCS FUSE: migration race and per-instance secrets.**
`DEPLOYMENT.md:299` (`--max-instances 3`), `core/db.py:336, 370` (version and legacy detection read
*outside* the migration transaction), `backend/app.py:40-48`.

Running two migrations at once locally: one instance dies with `OperationalError: database is locked`,
and 2 `.bak` files are written. Data is correct only because local POSIX locks work. gcsfuse does not
give cross-host SQLite locking, so on the bucket it is last-writer-wins. That loses writes, and in the
worst case a migration.

Separately, if `SECRET_KEY` is unset, each instance invents its own key, so admin tokens randomly 401
depending on which instance serves the request.

Fix:
- `--max-instances 1` in DEPLOYMENT.md and the deploy script. claude.md already says single writer.
- In `migrate()`, use `BEGIN IMMEDIATE` *before* `current_version`/`is_legacy_v14`, and re-check inside
  the transaction.
- In production, refuse to start when `SECRET_KEY` is missing or a placeholder, rather than using a
  random key.

**H3. The frontend on this branch still calls only v1.4 endpoints, and they are removed.**
For example `frontend/src/shell/Home.tsx:37` calls `/api/settings/state-number`. That is now 404, so the
home page silently shows state **2694** instead of 2807. 28 distinct `/api/...` v1.4 paths are used
across the ministry pages, and none exist in v2. Every player and admin flow is broken against this
backend, and the e2e suite cannot run against v2.

This is known (SPEC: "frontend must be rewired", branch `p1b/frontend-wiring`). It is listed because
nothing on `p1/integration` is deployable until that merges.

### Medium

**M1. Points regression: the migration truncates fractional crystal values.**
`core/db.py:190-199, 301-303`.

v1.4 could store them:
- The crystal inputs have no `step`.
- The form posts `parseFloat(value)` (v1.4 `PlayerForm.tsx:80`).
- The backend does `float()` when the value contains `.`.

The truncation changes Monday/research points and therefore auto-assign order (parity root cause C).

Fix:
- Before cut-over, run on a copy of prod:
  `SELECT fid, fire_crystals, refined_fire_crystals, fire_crystal_shards FROM players WHERE typeof(fire_crystals)='real' OR typeof(refined_fire_crystals)='real' OR typeof(fire_crystal_shards)='real'`.
- Migrate the exact value (`_num(v)` without `integer`) and log the affected rows. Also let
  `validate_answers` accept an unchanged legacy fractional value, otherwise admin edits of those
  applications fail with "must be a whole number".
- Or choose and document an explicit rounding policy in SPEC.

**M2. Legacy FIDs outside `^\d{1,20}$` are stranded and can be forked.**
`core/profiles.py:38-39` (lookup strips), `core/validation.py:59-65`, `core/applications.py:131, 208`.

For a stored `'330000777 '`:
- Public GET profile, application and assignments all return 404.
- Admin `GET` and `DELETE /api/admin/profiles/330000777%20` return 404.
- Admin `PUT /api/admin/applications/<id>` returns 400 `game_name is required`, because `upsert_profile`
  re-looks-up by stripped FID, misses, and treats it as a create. With `game_name` supplied it would hit
  UNIQUE → 409.
- A player resubmit creates a duplicate profile and application (or a 403 after closing).

v1.4's own form trimmed FIDs, so live rows probably only come from JSON import or admin edits, but nobody
can repair them through the API.

Fix:
- Pre-migration audit: `SELECT fid FROM players WHERE fid <> trim(fid) OR fid GLOB '*[^0-9]*'`.
- In the migration, trim when there is no collision and log the rest.
- Make `get_profile_row` match exactly first and fall back to stripped.
- Have `upsert_profile` update by `id` once the row is known.
- Admin profile routes should never `strip`.

**M3. Admin login can be brute-forced.**
`core/auth.py:85-97`; `CORS(app)` allows any origin (`backend/app.py:66`).

Signed tokens closed the v1.4 hole. The shared password is now the only barrier. Nothing throttles or
locks out, both roles have full power, and failures are only logged.

Fix:
- A simple in-process per-IP limiter (single instance), e.g. 5 attempts/min, then exponential backoff.
- Require long passwords in production.
- Restrict CORS to the app origin (the API is same-origin anyway).

**M4. Dev mode accepts forged tokens, and compose exposes it on all interfaces.**
`docker-compose.yml:7, 11-12` sets `FLASK_ENV=development` and the public placeholder key
`dev-secret-key-change-in-production`, and binds `8080:8080` on 0.0.0.0. `_harden_config` keeps
placeholder keys in dev (`backend/app.py:41-43`), and dev also enables `admin123`/`minister123`.

Verified: a token signed by hand with that placeholder → `200` on `/api/admin/me`. That is fine on a
laptop. It is full admin for anyone who can reach the port, or if `FLASK_ENV=development` ever leaks into
Cloud Run.

Fix:
- Bind `127.0.0.1:` in compose.
- Randomise placeholder keys in dev too, unless an explicit `ALLOW_INSECURE_DEV_KEY=1` is set.

**M5. Excel formula injection (pre-existing in v1.4, but now easier to reach).**
`events/ministry/logic.py:464-468, 508, 520-521`.

`game_name` (and FID/alliance) are written raw. openpyxl stores `=...` as a formula. The probe found 6
formula cells from the fixture name `=HYPERLINK("x","y"),;`. Any stranger can set a name through
`PUT /api/profile/<fid>`.

Fix: for string values starting with `= + - @` (or a tab/CR), set `cell.data_type = 's'` or prefix `'`.
Apply this to the Unassigned sheet too.

**M6. Public exposure with only an FID.**
This is accepted by the owner and listed here for the record: `core/profiles.py:105-122`,
`core/applications.py:99-151`, `events/ministry/routes.py:35-67`, `events/__init__.py:37-45`.

A stranger who knows or enumerates FIDs (short numeric, guessable) can **read**:
- the full profile: fid, name, alliance, timezone, furnace_level, power, troops, legacy avatar/stove,
  created/updated, internal `id`;
- the current and previous-round application: all 7 resource numbers, preferences per day, a profile
  snapshot, `player_id`;
- that player's slots **including unpublished days** (as v1.4; `published_days` is returned so the UI
  filters);
- the heatmap and published schedules.

They can **write**:
- create unlimited profiles and applications;
- rename any player or change their alliance. The probe shows the public published schedule immediately
  displaying `'renamed by a stranger'`, because it joins the live profile name;
- zero someone's speedups (they drop out of slots at the next auto-assign) or inflate their own;
- store up to 50 KB of free-form answers per tyrant/svs application.

There are no rate limits and no audit trail.

Cheap mitigations that keep the no-login model:
- per-IP rate limits on public PUTs;
- an `audit_log` (fid, ip, before/after JSON) so admins can see and revert vandalism;
- consider freezing `game_name` on applications in a round with published days.

### Low

**L1. Each failed migration attempt leaves a full `.bak`.**
`core/db.py:337`. A boot crash loop writes a new full copy to the bucket every time. `schema_version` is
also created before the transaction (harmless).

Fix: skip the backup if one with the same content hash exists, or delete it on rollback.

Positive evidence: a simulated crash after the import (before COMMIT) left every v1.4 table and row
intact. The re-run then migrated, and a third run was a no-op.

**L2. Read-modify-write races under `--threads 2`.**
`events/ministry/routes.py:101-119` (publish/unpublish) and `core/rounds.py:150-181` (settings merge)
read the settings JSON outside a write transaction, so concurrent admin actions can lose an update.
`SQLITE_BUSY` after 5 s surfaces as a generic 500 (`core/errors.py:86-89`).

Fix: `BEGIN IMMEDIATE` around read-modify-write, and map `OperationalError: database is locked` to 503
`RETRY`.

**L3. The scheme-switch remap does not re-sync the shared 23:50 boundary.**
`events/ministry/logic.py:383-415`. This is pre-existing v1.4 behaviour, and parity is OK. After
exact→max, Tuesday `23:50` is occupied while Monday `23:50+` is empty (seen in every `*-exact` scenario
at S5). The next Monday auto-assign or save then overwrites Tuesday's boundary.

Fix: after a remap, call `sync_shared_boundary` for the linked earlier day, or document it.

**L4. Restoring a v1.4 JSON backup is stricter than v1.4.**
`events/ministry/logic.py:572-575, 594`. Per-entry rejection of legacy FIDs and 4-character alliances is
reported. However, any non-`ApiError` (e.g. `sqlite3.IntegrityError`) aborts the whole import as a 409.

Fix: also catch `sqlite3.Error` per entry.

**L5. `export-json` uses a naive local timestamp.**
`exported_at` is `datetime.now()` (`events/ministry/logic.py:551`). Use `now_iso()` (UTC `Z`) per the
API.md convention.

**L6. Timezone and closing time.**
- `closing_time` with no offset is treated as UTC (`core/validation.py:16-23`). That matches API.md, but
  the admin UI being rewired must send UTC (`toISOString()`), as v1.4 did.
  Probe: `+02:00` → converted correctly; a naive value → UTC; `12/10/2026` → 400; milliseconds dropped.
- An unparseable legacy closing time leaves the round open, with only a warning (same as v1.4). Show
  `settings.legacy_closing_time_raw` to admins.
- `profiles.timezone` is free text ≤64 characters, not checked against IANA (`core/profiles.py:57-58`).

**L7. Case handling is ASCII-only.**
SQLite `UPPER`/`LOWER` only fold ASCII, so the alliance filter and the `q` search treat non-ASCII tags
and names case-sensitively (`core/applications.py:165`, `core/profiles.py:131-138`).

**L8. Tokens cannot be revoked.**
Rotating `ADMIN_PASSWORD` does not invalidate issued tokens (12 h). Only rotating `SECRET_KEY` does. A
bare token is still accepted. This is acceptable; document it in the auth module.

**L9. Frontend shell / i18n (light review).**
- `node frontend/scripts/check-i18n.mjs` → OK: 9 languages × 9 namespaces, 348 keys, 355 static usages.
- RTL is set in `i18n/index.ts:57` and `shell/Layout.tsx:11`.
- Shell components (`Home`, `Header`, `Changelog`, `LegacyRedirect`) use only `t()` and theme tokens.
- Hardcoded: `placeholder="TAG"` in `events/ministry/admin/PlayerManagement.tsx:414`.
- Off-token colours: `text-white` and `bg-black/50` overlays in `PlayerManagement.tsx:258, 379, 547...`,
  `AdminDashboard.tsx:56` and `AssignmentManagement.tsx:593`. All are pre-existing in v1.4.
- Missing versus the SPEC layout: `shared/` api client, FID lookup, profile fields and
  "Use my last answers" (expected on the rewire branch).

### Verified OK (no action)

- **Auth:** `hmac.compare_digest` is used. The itsdangerous `URLSafeTimedSerializer` has a salt and a
  12 h max_age. A role with an unset password env var cannot log in. Forged and literal tokens are
  rejected (url_map sweep plus `tests/test_auth.py`).
- **SQL:** every query is parameterised. The f-strings interpolate only constant table names
  (`core/db.py:143, 341`).
- **Errors:** an unhandled exception returns `{"error":"Internal server error","code":"INTERNAL_ERROR"}`
  and the trace is only logged. 404 and 400 bodies echo only the user's own input.
- **SQLite:** `PRAGMA journal_mode=DELETE` and `foreign_keys=ON` are set on every connection. There is one
  connection per request via `g`. The migration runs in a single transaction, with a backup through the
  SQLite backup API first. Re-running is idempotent.
- **Path traversal:** SPA static serving goes through `send_from_directory` (safe_join).

### SPEC items not (yet) implemented

- Frontend rewire and the SPEC `shared/` components (H3, L9).
- MCP server: phase 1b, on another branch.
- E2E against v2: blocked by H3.

The backend HTTP API in SPEC/API.md is otherwise complete. The deviations section is accurate, apart from
the four benign items above, which should be added.

---

## 3. Tests

- `cd backend && <venv>/bin/python -m pytest` → **74 passed** (Python 3.14 venv, 91 s).
- The same suite in `python:3.11-slim` (production version), in a throwaway `docker run` with the source
  mounted read-only → **74 passed**.

## 4. Reproduce

```bash
python3 scripts/parity/run_parity.py              # full table, exit 1 while C/F exist
python3 scripts/parity/run_parity.py --self-test  # proves a real logic bug is caught
<backend venv>/bin/python scripts/parity/probe_migration.py
```

---

## 5. Milestone 1c resolution (branch `p1c/backend-fixes`)

Re-checked against every finding above after the fixes. Tests: `cd backend && venv/bin/python -m pytest` →
127 passed (Python 3.14); same suite in `python:3.11-slim` → 125 passed, 2 skipped (no `git` in the container
for the v1.4-source test). Parity: `python3 scripts/parity/run_parity.py` → exit 0, "no regressions (15 scenarios,
1652 step comparisons)", 0 BENIGN; `--self-test` still catches the injected bug.

| id | status | how / why |
|---|---|---|
| C (parity) | Fixed | Crystals imported exactly (`_exact_number`); points match v1.4 (Half Crystal: 25,000 / 7,750). |
| F (parity) | Fixed | FID trimmed on import when unambiguous, exact-then-trimmed lookup everywhere, updates by id: no 404, no fork. Harness classifies the trim as EXPECTED (documented). |
| H1 | Fixed | Normal boot refuses a v1.4 file (`LegacyDatabaseError`); import via `python -m core.migrate` / `MIGRATE_V14=1`. Migration 2 adds guard VIEWs + settings triggers; the real v1.4 code (`git show 5454016`) cannot boot on a migrated or fresh v2 DB and its submit/settings writes fail with nothing written (`tests/test_legacy_import.py::test_stray_v14_instance_fails_loudly`). Runbook: `docs/DEPLOY-CUTOVER.md` (not executed). |
| H2 | Fixed | `--max-instances 1` in DEPLOYMENT.md and the runbook; `BEGIN IMMEDIATE` before version/legacy checks, one transaction (two-process race test: one migrates, one no-op, one backup); production refuses missing/placeholder `SECRET_KEY`. |
| H3 | Deferred (other branch) | Frontend rewire is owned by `p1b/frontend-wiring`; out of scope here. API changes it must adopt are listed in docs/API.md ("Removed in 1c", "Changed in 1c"). |
| M1 | Fixed | Exact crystal import + rows logged (`fractional_crystal_fids`); unchanged legacy fraction accepted on resubmit/admin edit; new fractions still 400. |
| M2 | Fixed | Rules in SPEC "Milestone 1c decisions": strings end to end, leading zeros significant, >2^53 safe, trim-when-unique on import, exact-then-trimmed lookup (admin routes included), canonical FID only for NEW profiles, legacy rows writable under their stored FID, `upsert_profile` by id; 4-char legacy alliance accepted when unchanged. |
| M3 | Fixed | In-process limiter per IP (right-most trusted X-Forwarded-For hop) + global budget, exponential backoff, 429 `TOO_MANY_ATTEMPTS`; SHA-256 digests compared with `compare_digest` for both roles; CORS off unless `CORS_ORIGINS`. Long passwords: warning only (refusing could lock out the live admin). |
| M4 | Fixed | Compose binds `127.0.0.1`; placeholder key/passwords only with `FLASK_ENV=development` + `ALLOW_INSECURE_DEV=1`, otherwise `ConfigError`; forged placeholder-key token → 401 in production. |
| M5 | Fixed | Cells starting with `= + - @` TAB CR written as quote-prefixed text in every sheet incl. `Unassigned`; 0 formula cells (probe + test). |
| M6 | Accepted (owner) + minimised | Documented in API.md "What an FID gives a stranger". Public profile drops `id`/`created_at`/`updated_at`; public application drops `id`/`player_id`/`profile_snapshot`/`created_at`; own assignments now published days only. No rate limit / audit log on public writes (deferred, noted in SPEC). |
| L1 | Fixed | Backup written as `.bak.partial`, renamed after COMMIT, deleted on failure; stale partials removed under the lock; `schema_version` created inside the transaction. |
| L2 | Fixed | `BEGIN IMMEDIATE` around round update and publish/unpublish; `database is locked` → 503 `RETRY` + `Retry-After`. |
| L3 | Fixed | Remap re-syncs the shared 23:50 boundary (earlier day if occupied, else later). Parity oracle applies the same rule via a v1.4 re-save; no differences. |
| L4 | Fixed | Import runs each entry in a savepoint; `sqlite3.Error` reported per entry. |
| L5 | Fixed | `exported_at` = UTC ISO `Z`; xlsx filename date in UTC. |
| L6 | Accepted | Documented in SPEC "Known / accepted" (naive = UTC, unparseable legacy closing time, free-text timezone). |
| L7 | Fixed | SQLite `casefold()` function (Python, Unicode-aware) for alliance filters and `q` search; LIKE wildcards escaped. |
| L8 | Accepted | Documented in `core/auth.py`, API.md and SPEC (no per-token revocation; rotate `SECRET_KEY`). |
| L9 | Deferred (other branch) | Frontend items belong to the frontend branches. |
| Benign 1-4 | Fixed / documented | null instead of `''`; Excel ties by id ASC; prefs sorted on import and input; heat-map orphans documented. Added to SPEC deviations; harness reports 0 BENIGN. |
| BACKEND_ISSUES (frontend-wiring 1, 2; mcp 1-4) | Fixed | Published days pruned on research-day switch and filtered publicly; closed rounds → 409 `ROUND_CLOSED` (reopen via status); own assignments = published only; `current` on generic admin round routes; `?limit/offset` + `total`; unknown public schedule day → 400. MCP 5-8 (actor header, public rate limits, change notifications) not addressed. |
