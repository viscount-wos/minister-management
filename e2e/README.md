# E2E suite (Playwright, Python)

UI-level tests for wos-events: the ministry player flow (profiles / rounds / applications), admin
round management, i18n in all 9 languages and Arabic RTL. Never point it at production: it creates
test players and starts/closes rounds.

## Setup and run

Run against an isolated stack, not the 8091 baseline:

```bash
mkdir -p /tmp/wos-e2e-data                    # fresh empty data dir (or copy a v1.4 DB in first to migrate it)
E2E_DATA=/tmp/wos-e2e-data docker compose -p wos-wiring \
  -f docker-compose.yml -f e2e/docker-compose.e2e.yml up -d --build      # -> 127.0.0.1:8093
BASE_URL=http://127.0.0.1:8093 e2e/run.sh     # creates e2e/.venv, installs chromium, runs pytest
docker compose -p wos-wiring -f docker-compose.yml -f e2e/docker-compose.e2e.yml down
```

By hand: `cd e2e && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt &&
.venv/bin/playwright install chromium && BASE_URL=... .venv/bin/python -m pytest` (`-k admin`,
`--headed`, `--slowmo 300` ...).

| env | default | |
|---|---|---|
| `BASE_URL` | `http://127.0.0.1:8091` | app under test; suite exits early (code 2) if `/health` is down |
| `ADMIN_PASSWORD` | `admin123` | local dev default only; never a real password |

A fresh install has no rounds: the session fixture `ministry_round` opens one through the API if
none is open. Screenshots: `e2e/artifacts/<run timestamp>/<test>-<step>.png` (gitignored); a
`*-RAWKEYS.png` is taken whenever a raw i18n key is found.

## Where things live

- **`ui.py`**: routes, legacy redirects, the header dropdowns (`switch_language` picks an option in
  `language-select`; also `theme-select`, `header-timezone`), selectors, flow helpers
  (`open_application`, `pick_slots`, ...), the raw-key detector and a small `Api` client used only
  to arrange state (start a round, set a closing time, seed an application).
- UI strings are read from the app's own locale files: `ui.tr('ar', 'ministry:apply.newFor',
  round=name)`. Nothing is hard-coded, so a wording change does not break tests.
- Controls are found by `data-testid` (`get_by_test_id`) or by their linked `<label>`
  (`get_by_label`); inputs keep `name=` too. Key test ids: `fid-input`, `fid-continue`,
  `application-heading` (`data-mode` = `lookup|new|edit`), `profile-game-name`, `profile-alliance`,
  `answer-<field>`, `day-tab-<type>`, `slot-<type>-<HH:MM>` (`aria-pressed`), `use-last-answers`,
  `last-answers-applied`, `save-application`, `save-success`, `applications-closed`, `no-round`;
  admin: `round-select`, `round-status`, `start-new-round`, `new-round-dialog`, `confirm-new-round`,
  `read-only-banner`, `tab-<players|assignments|settings>`, `player-row-<fid>`, `card-<fid>`.

- **CSP watch** (`conftest.py`): `Browser.new_context` is wrapped so EVERY context (the `page` fixture, phone
  contexts, ad-hoc ones) reports Content-Security-Policy violations (console + `securitypolicyviolation`); the
  autouse `no_csp_violations` fixture fails the test that caused one. Don't inject `<style>`/`<script>` tags in
  tests (CSP blocks them): set styles through the CSSOM (`el.style.setProperty`). `test_polish.py` self-tests it.
- **Rate limits are off** in `docker-compose.e2e.yml` (`RATE_LIMIT_*_PER_MIN=0`): one IP drives the whole suite.
  The limits are covered in `backend/tests/test_security.py`; the UI's 429 message uses a stubbed response.

## What it covers

`test_i18n.py`
- raw-key detector unit test (dotted keys, `ns:key`, `{{var}}`), and a live DOM check
- home: heading, one tile per event, ONE language dropdown listing the 9 native names (no pills)
- every public page (`/`, `/minister`, `/minister/apply`, `/admin`, `/minister/guide`, `/changelog`)
  in all 9 languages without raw keys; the home heading changes in every language
- the application form in new and edit mode, all 9 languages
- Arabic: `dir=rtl` and Arabic text on ministry home, FID lookup, edit form, admin dashboard,
  start-round dialog and round settings
- admin Players/Assignments/Settings tabs, the start-round dialog and the admin guide, 9 languages

`test_ministry_flow.py` (in order, shared state, fresh FIDs every run)
- home tile -> ministry -> apply (round name shown); FID must be digits
- new application in English: "New application for <round>", no "Use my last answers" for a
  first-timer, alliance upper-cased, decimals, slots on two days; verified through the API
- edit via FID: "Edit your application for <round>", profile + answers + slots pre-filled, own
  assignments shown, edit persists after reload
- new application with the UI in Arabic (RTL kept through success)
- admin: current round selected by default, applicant row found by search; wrong password refused;
  the old literal `admin-token` is rejected and the UI returns to login with "session expired"
- **Start new round**: confirm dialog (cancel really cancels), new round becomes current, old one is
  read-only with its data intact; the same FID then gets "New application for <new round>" with the
  profile pre-filled and answers blank; **Use my last answers** fills the previous answers and slots
  and says where they came from (also checked in 9 languages and Arabic); saved into the new round
- auto-assign, lock (assignment save), publish, Excel + JSON export downloads; the player sees the
  published schedule and their own slot
- old URLs (`/submit`, `/update`, `/apply`, `/guide`, `/schedule/:day`, `/ministry/...`, `/ministry/admin`)
  redirect to `/minister/...` (`/admin?event=ministry`)

`test_round_states.py` (always leaves an open round behind)
- closing time passed: new FID gets "applications closed" (9 languages + Arabic), an existing
  application stays editable with the "closed for new players" note
- closing time passing while the form is open: save returns 403 -> closed state, nothing written
- admin round settings: research day (assignment tab follows), fire crystals (player form follows),
  slot scheme (remap message), closing time save/clear
- no open round: home tile "Not open yet", ministry banner + disabled tile, apply page "not open"
  (9 languages + Arabic)

`test_admin_shell.py` (Event Management, one API token reused; 2 UI logins)
- "Event Management" title on login and dashboard + contextual subtitle per event, en and ar
- event page admin link -> login -> that event's dashboard; logged in -> straight there; Home -> last event (else
  ministry); old `/admin/dashboard` without `?event=`
- event switch keeps the login; forged/expired token -> `/admin?event=tyrant&expired=1` -> back to Tyrant
- guide button opens the current event's guide; guide page event switch; back to that dashboard
- `document.title` per page (en + ar); raw keys in 9 languages on login, both dashboards and the Tyrant guide
- welcome line hidden while the state number is unset; no "Ministry" text in English on the main pages; `/ministry/...`
  redirects to `/minister/...` keeping the query

`test_tyrant.py` (Frost Dragon Tyrant, in order, opens its own tyrant round)
- home tile live ("Open") -> landing -> wizard; FID digits check; 6-step indicator
- NEW in English through all 6 steps (step-1 checks, Select All, NO main-furnace field (owner p2e), per-troop
  camp level FC10..FC1 + tier, roles, review with Edit per section); verified through the API (profile vs answers)
- EDIT via FID (everything pre-filled, Update), "Not you? Use a different FID"
- Arabic RTL wizard (step 1 on the right, Arabic strings, saved with language 'ar')
- raw-key check in 9 languages on the landing page and every wizard step (titles change per language)
- Minister still asks the furnace: the shared dropdown is exactly FC10..FC1 then 30..1 (also on the phone)
- closing time: new FID -> closed card, existing FID -> edit with the note
- admin: event switch, stats cards/breakdowns, search, alliance filter, no furnace column/filter/sort, strength
  sort, CSV (no furnace column) + Excel download,
  windows editor + closing time, delete, 9 languages; Start new round -> NEW + Use my last answers -> saved

`test_mobile.py` (phones: Playwright device emulation on chromium: iPhone 13 390px, Pixel 7 412px, and a
360px Android context)
- every player page in en and ar (auto-detected from the context locale): home, Minister home/guide/schedule,
  Tyrant home, SVS placeholder, changelog: no sideways scroll (`scrollWidth <= viewport`), header controls in ONE
  row and >= 44px, key buttons >= 44px, no input under 16px (iOS zoom); a screenshot of each
- the full Minister wizard NEW (KST timezone, so hours show local + UTC) and the full Tyrant wizard NEW, every step:
  step circles inside the card, sticky Back/Next on screen, hour buttons >= 44px with no clipped text, mobile
  keyboards (`inputmode`: FID numeric, days/power decimal, gems numeric), saved and checked through the API
- the language dropdown switching to Arabic (`dir=rtl`), remembered after reload; theme remembered
- auto-detect: locale `tr-TR` -> Turkish, `ar-SA` -> Arabic RTL, `es-MX`, `zh-TW`, `xx`/`pt-BR` -> English; a saved
  choice beats the browser language; `dir/lang` already right with the JS bundle blocked (first paint)
- timezone auto-detect via `timezone_id` (KST, ET, a zone outside the list: Berlin, UTC); a saved choice wins
- Tyrant closed and no-round states (restored afterwards), admin dashboards on a phone, tap-to-move on the
  assignment board (move icon -> Move here; persists, sticky; back to Unassigned)
- screenshots: `artifacts/<run>/mobile/<device>-<lang>-<page>.png`

Desktop tests pin `locale=en-US`, `timezone_id=UTC` (conftest) because the app now auto-detects both.

## Not covered

Drag-and-drop between slots with a real mouse or a long-press touch drag (the save path is exercised
through the lock toggle and tap-to-move), JSON import, profile admin endpoints (no UI yet), timezone
conversions beyond display, real iOS Safari/WebKit (phones are emulated on chromium). Test data is not cleaned up; use a throwaway data dir.
