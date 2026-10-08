# Parity harness: v1.4 vs phase-1 ministry

Reviewer tooling (milestone 1b). Nothing here changes `backend/` or `frontend/`.

| file | what |
|---|---|
| `run_parity.py` | Main harness. Builds dummy v1.4 DBs (`backend/tests/fixtures/make_legacy_db.py`), runs the live v1.4 code (`git show 5454016:backend/{app,database}.py`) and the phase-1 backend side by side via Flask `test_client`, compares ~110 steps per scenario, classifies every difference. Exit 1 on any regression. |
| `_worker.py` | One app per interpreter (both are `app.py`). Drives the same operation script against either app and dumps normalised JSON. |
| `probe_migration.py` | Evidence probes for the review: migration failure/rollback, re-run, two instances migrating at once, a v1.4 revision restarting on a migrated DB, FID/alliance edge cases, public exposure, Excel formula cells, closing-time parsing. |

```bash
python3 scripts/parity/run_parity.py            # 15 scenarios (~3 min); --quick = 4; -v = every regression diff
python3 scripts/parity/run_parity.py --self-test # injects a shared-23:50 bug into the NEW app at runtime; must be caught
<backend venv>/bin/python scripts/parity/probe_migration.py
```
The apps run under `$PARITY_PYTHON` (default: the backend-core venv) with `PYTHONHASHSEED=0`; a stub
`dotenv` module stops either app reading a stray `.env`. All DBs live in a temp dir (`--keep` keeps it).

## Sides
- `old`: v1.4 exactly as live. Its auto-assign walks a player's hours in **set hash order**, so its
  output changes with `PYTHONHASHSEED` (the `hash-sens` column counts steps where that matters).
- `old_sorted`: v1.4 with one runtime shim (module-global `set` iterates sorted) = the documented
  deviation "auto-assign walks a player's preferences in sorted order". **This is the oracle.**
- `old_int`: `old_sorted` on a copy with REAL crystal values cast to int, to attribute the cascade of the
  one known data change (migration truncates `12.5` fire crystals) to a single root cause.
- `new`: phase-1 backend on a copy migrated by its own startup.

## Script (per scenario)
S0 after migration: points per player/day, heatmap, export-json, assignments per day, public schedule
(4 days), published days, every player's own assignments, Excel. S1 auto-assign Mon/research/Thu (sticky
rows must survive) + snapshot. S2 clear all sticky flags (manual save), auto-assign again (exercises the
shared 23:50 combined-score winner). S3 manual saves: move the boundary loser onto Mon/Thu `23:50+`
(mirror check) and a sticky drag on Thursday, re-run auto-assign. S4 publish/unpublish. S5 switch slot
scheme (remap) + snapshot. S6 auto-assign under the new scheme + snapshot. S7 player lookups/resubmits for
awkward FIDs, a brand-new FID, then closing time in the past (edit allowed, new blocked).

## Classes
`OK` identical; `EXPECTED` explained by a documented deviation (SPEC "Backend phase 1 deviations" /
API.md); `BENIGN` cosmetic and undocumented (doc gap, does not fail the run); `REGRESSION` anything else.
Normalisers are applied only when needed (leave-one-out), so each label is a real explanation.
