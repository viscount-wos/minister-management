# Legacy v1.4 fixture DB

`make_legacy_db.py` builds a **dummy** SQLite DB in the exact minister_management v1.4.0 schema,
for testing the v1.4 → wos-events migration. All data is invented. No real player data is used or
fetched. Generated `.db` files are gitignored; never commit one.

```bash
python backend/tests/fixtures/make_legacy_db.py /tmp/legacy.db                 # 150 rows, seed 2807
python backend/tests/fixtures/make_legacy_db.py /tmp/legacy.db --force \
       --players 300 --seed 7 --research-day friday --scheme max_slots
python backend/tests/fixtures/make_legacy_db.py /tmp/legacy.db --check         # counts only, read-only
```

From pytest:

```python
import sys; sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
from make_legacy_db import build_legacy_db, table_counts, CASES
before = build_legacy_db(tmp_path / "legacy.db")          # returns table_counts()
assert before["players"] == 144
fid = CASES["shared_slot_winner"]                         # look up awkward rows by case name
```

Options: `--players N` (rows inserted, default 150; the final count is lower because some are
deleted, see below), `--seed S` (default 2807), `--research-day tuesday|friday` (default tuesday),
`--scheme max_slots|exact_alignment` (default max_slots), `--force` (overwrite). Stdlib only.

**Deterministic:** same args give byte-identical table contents. `--check` prints
`content_sha256` (hash of every row of every table) so a test can prove a migration did not touch
the source, or that the generator did not change. `--check` opens the DB with
`mode=ro&immutable=1`, so it never writes `-journal`/`-shm` files.

## Schema fidelity

The DDL is copied statement-for-statement from v1.4 `backend/database.py::init_db` (commit
5454016): the original `CREATE TABLE`s, then the `ALTER TABLE ... ADD COLUMN` migrations in
order. So the ALTER-added columns sit at the END (`players`: `... created_at, updated_at,
avatar_image, stove_lv, stove_lv_content, alliance, timezone`; `assignments`: `... created_at,
is_sticky`), as in the live DB. Verified when this was written by running the real v1.4 `init_db`
on an empty file and comparing: `sqlite_master` SQL, `PRAGMA table_info` and `PRAGMA index_list`
are identical. Running v1.4 `init_db` on the fixture changes nothing (same `content_sha256`), and
the v1.4 app served `/api/admin/players`, `/api/admin/assignments/<day>`, `/api/published-schedule/*`,
`/api/admin/export` and `/api/admin/players/export-json` from it with HTTP 200.
`--check` reports `schema_ok` (column order matches) and exits 1 if not.

## Reference counts (default args: `--players 150 --seed 2807`)

| table | rows |
|---|---|
| players | 144 (150 inserted, 6 deleted) |
| time_preferences | 1697 (3 orphaned) |
| assignments | 144 (monday 46, tuesday 46, thursday 47, stale friday 5; 1 orphaned; 20 sticky) |
| settings | 6 |
| admin_users | 0 (table exists, v1.4 never uses it) |

Other: 47 players with avatar/stove data, 96 avatar NULL, 1 avatar `''`; 31 players with no time
prefs at all; 60 players with no assignment; alliance NULL on 18, `''` on 1;
`content_sha256 41fa73a2…` (changes whenever the generator changes; update tests deliberately).
With `--research-day friday` the linked pair is thursday/friday and the stale rows are on tuesday.

## Awkward cases (what the migration must survive)

FIDs are fixed; get them from `CASES[name]`.

**Legacy columns and NULL vs empty**
- `pre_aug_full`, `pre_aug_stove_only`, `pre_aug_fc_level_high`, `legacy_prefs_all_days` + ~40
  random rows: created before 2026-08-01 with `avatar_image`/`stove_lv`(/`stove_lv_content`)
  populated (the old "Load from WOS"). `stove_lv_content` is NULL on some of them even when
  `stove_lv` is set (furnace < FC). `pre_aug_fc_level_high` was created at 2026-07-31 23:59:59.
- Rows created after August have all three NULL.
- Pre-August rows often have `alliance` NULL and `timezone` NULL (those columns came later).
- `import_empty_strings`: the v1.4 JSON import path writes `''` (not NULL) for avatar,
  stove_lv_content, alliance and timezone. A migration that does `COALESCE` or `IS NULL` only
  will treat these differently.
- `import_lowercase_long_tag`: alliance `'love'` (lowercase, 4 chars; the import path skips the
  UI's upper-case/3-char rule). The new profile spec says `<=3 chars, upper` — decide: keep,
  truncate or reject, but don't crash.

**FIDs (TEXT)**
- `fid_leading_zero` `'0040021'`: must stay a string. `int()` would turn it into `40021`.
- `fid_trailing_space` `'330000777 '`: v1.4 `/api/player/submit` saves the raw value (only
  `check-duplicate` strips). Stripping on migration could collide with another FID.
- `fid_beyond_js_safe_int` `'90071992547409931'`: > 2^53, breaks if parsed as a JS number.

**Names** (all must round-trip byte-for-byte, and must not be merged as duplicates)
- `Viking` variants: `viking` (case), `Viking ` (trailing space), `Vikіng` (Cyrillic і),
  `Ｖｉｋｉｎｇ` (full-width). v1.4 `check-duplicate` uses `LOWER()`, which is ASCII-only in SQLite.
  Random rows also create real duplicate-looking names (`Frost🔥12`, `Wolf 7` …).
- `name_nfc` / `name_nfd`: `Zoë` composed vs decomposed: look identical, are different bytes.
- ZWJ emoji family, RTL Arabic with digits and Latin, Korean, Chinese, Turkish dotted/dotless i
  (`İSMAİL ılık`), Polish diacritics, a 50-char name with emoji.
- `name_sql_quote` (`Robert'); DROP TABLE players;--`), `name_html` (`<b>bold</b> & "quoted"`),
  `name_csv_formula` (`=HYPERLINK(...)`, starts with `=` → Excel formula injection in exports).

**Numbers**
- `max_values`: every numeric field 99999 (the v1.4 upper bound). Monday points =
  3,487,965,120, which overflows a 32-bit int. Has prefs for all 24 hours on all days.
- `all_zero`: everything 0. `fractional`: 0.1, 12.25, 3.3333333333, 0.5.
- `real_in_integer_column`: `fire_crystals = 12.5`, `fire_crystal_shards = 7.75`. SQLite keeps
  REAL values in INTEGER-affinity columns (v1.4 submit does `float()` when the input has a dot).
  A migration that casts to int silently changes points.

**Time preferences** (`time_slot` is UTC `HH:00`, `day_type` construction/research/troop)
- No prefs at all (31 players), prefs on some day types only, 24/24 hours, single hour.
- Legacy list shape: identical slots on all three day types (what the pre-day_type v1.4
  migration and `time_slots` list submissions produce): `legacy_prefs_all_days` + ~10% random.
- `deleted_with_prefs` + `deleted_assigned_sticky`: 3 **orphan** prefs whose player row is gone.

**Assignments**
- Scheme `max_slots`: slot ids `23:50`, `00:20`, `00:50` … `23:20`, `23:50+` (49/day).
- **Shared 23:50 boundary**: `shared_slot_winner` holds monday `23:50+` AND tuesday `23:50`
  (one real time), sticky on both rows. `shared_slot_loser` wanted the same boundary and is
  unassigned everywhere. `linked_boundary_pairs` must stay 1 after migration.
  Thursday also has ordinary `23:50`/`23:50+` rows that are NOT linked (tuesday research day).
- Sticky: 20 rows; `no_prefs_assigned_manually` is sticky on monday `12:20` with no prefs (admin
  drag), so "assignment implies a matching pref" is false.
- `deleted_assigned_sticky`: player deleted, sticky monday assignment left behind → **orphan
  assignment** (v1.4 never sets `PRAGMA foreign_keys=ON`, so `ON DELETE CASCADE` never ran).
  Migration must skip/report orphans, not crash on a FK or NOT NULL.
- Stale rows: 5 assignments on the inactive research day (`friday` when research_day is tuesday)
  left from switching research day. They are real rows; decide whether they migrate.
- Unassigned: ~60 players have no assignment at all; many others are assigned on 1-2 days only.
- All rows `position = 0`, `is_assigned = 1` (as v1.4 writes them).
- `player.id` has gaps (6 deleted; 4 of them cleanly with their prefs/assignments, 2 leaving
  orphans). Don't assume `id == rownum`, and keep `sqlite_sequence` in mind if ids are reused.

**Settings** (all TEXT): `time_slot_scheme=max_slots`, `research_day=tuesday|friday`,
`show_fire_crystals=true` (string, not bool), `application_closing_time=2026-10-12T18:00:00.000Z`
(JS `toISOString()` format with `Z` and millis), `state_number=2807`,
`published_days=monday,tuesday` (friday mode: `monday,thursday`; comma string, not JSON).
v1.4 defaults if absent: research_day tuesday, scheme exact_alignment, state 2694.

**Timestamps**: `created_at`/`updated_at` are SQLite `CURRENT_TIMESTAMP` text
(`YYYY-MM-DD HH:MM:SS`, UTC, no `T`, no zone). Pinned, never "now".

## Not covered (known gaps)
- Hypothetical very old shapes: `time_preferences` without `day_type`, or the older
  `UNIQUE(player_id, time_slot)` constraint. v1.4 `init_db` repairs those itself; this fixture
  is a DB that has already been through v1.4 `init_db`.
- `admin_users` rows (unused by v1.4).
- Non-`HH:00` pref values or unknown `day_type` values (no evidence the live DB has any).
- `exact_alignment` installs with no `time_slot_scheme` row at all (only via
  `--scheme exact_alignment`, which still writes the key).
- Duplicate assignment of one player twice on the same day (v1.4's manual editor might allow it).
