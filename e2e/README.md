# E2E smoke suite (Playwright, Python)

UI-level smoke tests for the ministry app. Written and proven against the **v1.4 baseline**
container (`http://127.0.0.1:8091`), so the same flows can be re-run against wos-events after the
restructure. Never point it at production: it creates test players.

## Setup and run

```bash
e2e/run.sh                                   # creates e2e/.venv, installs chromium, runs pytest
# or by hand:
cd e2e && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
.venv/bin/python -m pytest                   # -q, -k admin, --headed, --slowmo 300 ...
```

| env | default | |
|---|---|---|
| `BASE_URL` | `http://127.0.0.1:8091` | app under test; suite exits early (code 2) if `/health` is down |
| `ADMIN_PASSWORD` | `admin123` | local dev default only; never a real password |

Screenshots: `e2e/artifacts/<run timestamp>/<test>-<step>.png` (gitignored). A screenshot named
`*-RAWKEYS.png` is taken whenever a raw i18n key is found. `.venv/`, `artifacts/` and
`test-results/` are gitignored.

## What it covers

`test_i18n.py`
- raw-key detector unit test, and a live check that it sees a key injected into the DOM
- home loads: heading, apply/update tiles, all 9 language buttons
- for each public page (`/`, `/submit`, `/update`, `/admin`, `/guide`, `/changelog`): switch to each
  of en es fr de pl ko zh tr ar and assert no raw i18n keys (`form.next`, `ministry.x.y`, `common.x`)
  or `{{var}}` leftovers in visible text, placeholders, titles, aria-labels or alt text
- the home heading actually changes in every non-English language (catches silent fallback)
- Arabic sets `<html dir="rtl">`; switching back sets `ltr`
- every step of the apply wizard (1-5) in all 9 languages (fills step 1, does not submit)
- admin dashboard Players/Assignments/Settings tabs and admin guide in all 9 languages

`test_ministry_flow.py` (runs in order, shares state, fresh FIDs every run)
- submit an application through the UI in English (FID, name with emoji, alliance lower-case →
  upper-cased, fractional speedups, slots on Monday + Thursday, Tuesday left empty → `confirm()`)
- submitting the same FID again shows the duplicate warning and stays on step 1
- reopen it by FID on the update page, check pre-filled values, edit speedups + a research slot,
  save, reload and prove the edit persisted
- full submission with the UI in Arabic (Arabic button labels, RTL kept through success)
- admin login (`admin123`), search the players table by FID, row shows name and `[E2E]` tag
- wrong admin password does not reach the dashboard

## Selectors: what will need updating after the restructure

All routes, selectors and UI strings live in **`ui.py`**; update that first.

- `ROUTES`: v1.4 paths `/submit`, `/update`, `/guide`, `/admin/dashboard` move under
  `/ministry/...` / `/admin/...`. Add a test that the old paths redirect (SPEC requires it).
- Home: v1.4 has "Submit New Application" / "View Assignment / Update Info" buttons. wos-events
  has one tile per event, so `test_home_loads`, `test_submit_application_en` and
  `test_reopen_by_fid_and_edit` must first click the ministry tile.
- `STRINGS`: copied from v1.4 `frontend/src/i18n.ts`. After the i18n split, load them from
  `frontend/src/i18n/locales/<lang>/<ns>.json` instead of hard-coding (keys will be namespaced).
- `FIELD`: v1.4 inputs have `name=` attributes but labels are NOT associated (`<label>` without
  `for`), so tests use `input[name=...]`. The rewrite should add `id`/`htmlFor` (then use
  `get_by_label`) or `data-testid`s; please keep `name=` too.
- Apply flow changes in wos-events: the update page becomes "New application for <round>" /
  "Edit your application for <round>" via FID; add "Use my last answers" and "Start new round"
  (admin) tests, which v1.4 cannot have.
- Language buttons are found by native name (`English`, `العربية` …); keep those labels or update
  `LANGUAGES`. v1.4 does not persist the language across reloads; tests switch after each `goto`.
- Time-slot buttons are found by exact text (`12:00`) with the UTC timezone (the default).
- Admin players table: found by `role=row` filtered by FID text, and the search placeholder
  `Search players...`. Tabs by their English names.

## Not covered

Publish/unpublish and the public schedule page, auto-assign and drag-and-drop assignment editing,
Excel/JSON export and import, settings changes (closing time, research day, scheme, state number),
themes, timezone selector conversions, mobile viewport, Firefox/WebKit, accessibility. Test players
are not cleaned up (the baseline is throwaway; delete them in the admin UI if needed).
