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

- **`ui.py`**: routes, legacy redirects, language buttons, selectors, flow helpers
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

## What it covers

`test_i18n.py`
- raw-key detector unit test (dotted keys, `ns:key`, `{{var}}`), and a live DOM check
- home: heading, one tile per event, all 9 language buttons
- every public page (`/`, `/ministry`, `/ministry/apply`, `/admin`, `/ministry/guide`, `/changelog`)
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
- old URLs (`/submit`, `/update`, `/apply`, `/guide`, `/ministry/submit|update`, `/ministry/admin`)
  redirect

`test_round_states.py` (always leaves an open round behind)
- closing time passed: new FID gets "applications closed" (9 languages + Arabic), an existing
  application stays editable with the "closed for new players" note
- closing time passing while the form is open: save returns 403 -> closed state, nothing written
- admin round settings: research day (assignment tab follows), fire crystals (player form follows),
  slot scheme (remap message), closing time save/clear
- no open round: home tile "Not open yet", ministry banner + disabled tile, apply page "not open"
  (9 languages + Arabic)

## Not covered

Drag-and-drop between slots (the assignment save path is exercised through the lock toggle), JSON
import, profile admin endpoints (no UI yet), themes, timezone conversions, mobile viewport,
Firefox/WebKit. Test data is not cleaned up; use a throwaway data dir.
