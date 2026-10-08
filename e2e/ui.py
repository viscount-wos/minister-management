"""Every route, selector, UI string and API helper the e2e suite relies on, in ONE place.

UI strings are read from the app's own locale files (frontend/src/i18n/locales/<lang>/<ns>.json),
so a wording change in the app does not break the tests. Controls are found by data-testid
(Playwright's get_by_test_id) or by their linked <label> (get_by_label).
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path

from playwright.sync_api import Page, expect

# --- routes ---------------------------------------------------------------
ROUTES = {
    'home': '/',
    'ministry': '/minister',               # event key 'ministry'; players see "Minister" (owner rule)
    'apply': '/minister/apply',            # the wizard: step 1 starts with the FID -> new / edit
    'admin_login': '/admin',
    'admin_dashboard': '/admin/dashboard',
    'player_guide': '/minister/guide',
    'tyrant_guide': '/tyrant/guide',
    'svs_guide': '/svs/guide',
    'admin_guide': '/admin/guide',
    'changelog': '/changelog',
}

# Old URL -> where it must land (bookmarks / shared links keep working).
LEGACY_REDIRECTS = {
    '/submit': '/minister/apply',
    '/apply': '/minister/apply',
    '/update': '/minister/apply',
    '/ministry': '/minister',
    '/ministry/apply': '/minister/apply',
    '/ministry/submit': '/minister/apply',
    '/ministry/update': '/minister/apply',
    '/minister/submit': '/minister/apply',
    '/minister/update': '/minister/apply',
    '/ministry/schedule/monday': '/minister/schedule/monday',
    '/schedule/monday': '/minister/schedule/monday',
    '/ministry/guide': '/minister/guide',
    '/guide': '/minister/guide',
    '/ministry/admin': '/admin?event=ministry',
}

# Pages that need no login, checked for raw i18n keys in every language.
PUBLIC_PAGES = ['home', 'ministry', 'apply', 'admin_login', 'player_guide', 'tyrant_guide', 'svs_guide', 'changelog']

# --- languages ------------------------------------------------------------
# code -> option label in the header's language dropdown (the native name; same in every UI language)
LANGUAGES = {
    'en': 'English', 'es': 'Español', 'fr': 'Français', 'de': 'Deutsch', 'pl': 'Polski',
    'ko': '한국어', 'zh': '中文', 'tr': 'Türkçe', 'ar': 'العربية',
}
RTL_LANGUAGES = {'ar'}

# --- UI strings, read from the app's locale files ----------------------------
LOCALES = Path(__file__).resolve().parent.parent / 'frontend' / 'src' / 'i18n' / 'locales'


@lru_cache(maxsize=None)
def _ns(lang: str, ns: str) -> dict:
    return json.loads((LOCALES / lang / f'{ns}.json').read_text(encoding='utf-8'))


def tr(lang: str, key: str, **vars) -> str:
    """tr('ar', 'ministry:apply.newFor', round='X') -> the app's string with {{vars}} filled."""
    ns, _, path = key.partition(':')
    node = _ns(lang, ns)
    for part in path.split('.'):
        node = node[part]
    return re.sub(r'\{\{\s*(\w+)\s*\}\}', lambda m: str(vars.get(m.group(1), m.group(0))), node)


def en(key: str, **vars) -> str:
    return tr('en', key, **vars)


# --- navigation / common actions -------------------------------------------

def go(page: Page, base_url: str, route: str) -> None:
    page.goto(base_url + ROUTES[route])
    page.wait_for_load_state('networkidle')


LANGUAGE_SELECT = 'language-select'     # header dropdown (native <select>, value = language code)
THEME_SELECT = 'theme-select'
TIMEZONE_SELECT = 'header-timezone'


def switch_language(page: Page, code: str) -> None:
    """Pick a language in the header dropdown (the choice is remembered in localStorage)."""
    page.get_by_test_id(LANGUAGE_SELECT).select_option(code)
    page.wait_for_function(
        "([dir, lang]) => document.documentElement.dir === dir && document.documentElement.lang === lang",
        arg=['rtl' if code in RTL_LANGUAGES else 'ltr', code])


def admin_dashboard_url(event: str) -> str:
    return f"{ROUTES['admin_dashboard']}?event={event}"


def admin_guide_url(event: str) -> str:
    return f"{ROUTES['admin_guide']}?event={event}"


def admin_login(page: Page, base_url: str, password: str, event: str = 'ministry') -> None:
    """Log in through the UI (password found by its <label>) and land on `event`'s dashboard."""
    page.goto(base_url + ROUTES['home'])
    # A still-valid token makes /admin skip straight to the dashboard: start logged out. The password is
    # found by its English label, and a language picked earlier in the test is remembered: forget it.
    page.evaluate("localStorage.removeItem('adminToken'); localStorage.removeItem('adminRole');"
                  " localStorage.removeItem('preferred_language')")
    page.goto(f"{base_url}{ROUTES['admin_login']}?event={event}")
    page.wait_for_load_state('networkidle')
    page.get_by_label(en('admin:password')).fill(password)
    page.get_by_test_id('admin-login').click()
    page.wait_for_url('**' + admin_dashboard_url(event))
    expect(page.get_by_test_id('round-select')).to_be_visible()
    page.wait_for_load_state('networkidle')


def use_admin_token(page: Page, base_url: str, token: str, path: str | None = None) -> None:
    """Reuse an API token instead of logging in through the UI (the login is rate-limited)."""
    page.goto(base_url + ROUTES['home'])
    page.evaluate("t => { localStorage.setItem('adminToken', t); localStorage.setItem('adminRole', 'admin'); }", token)
    if path:
        page.goto(base_url + path)
        page.wait_for_load_state('networkidle')


# --- the application wizard (v1.4 steps) -------------------------------------
# 1 player info (starts with the FID) -> 2 construction -> 3 research -> 4 troop -> 5 review
DAY_STEPS = {'construction': 2, 'research': 3, 'troop': 4}
REVIEW_STEP = 5


def step_no(page: Page) -> int:
    return int(page.get_by_test_id('wizard-steps').get_attribute('data-step'))


def expect_step(page: Page, n: int) -> None:
    expect(page.get_by_test_id('wizard-steps')).to_have_attribute('data-step', str(n))
    expect(page.get_by_test_id(f'wizard-step-{n}')).to_be_visible()


def enter_fid(page: Page, base_url: str, fid: str) -> None:
    """Wizard step 1: type the FID and press Next (which looks it up)."""
    go(page, base_url, 'apply')
    expect_step(page, 1)
    page.get_by_test_id('fid-input').fill(fid)
    page.get_by_test_id('wizard-next').click()


def open_application(page: Page, base_url: str, fid: str) -> str:
    """Apply page -> FID -> wait for the wizard's mode or the closed state. Returns 'new'|'edit'|'closed'."""
    enter_fid(page, base_url, fid)
    landed = page.locator('[data-testid="application-heading"]:not([data-mode="lookup"]), '
                          '[data-testid="applications-closed"]')
    expect(landed.first).to_be_visible()
    page.wait_for_load_state('networkidle')
    if page.get_by_test_id('applications-closed').count():
        return 'closed'
    return page.get_by_test_id('application-heading').get_attribute('data-mode')


ANSWER = {
    'construction': 'answer-construction_speedups_days',
    'research': 'answer-research_speedups_days',
    'troop': 'answer-troop_training_speedups_days',
}


def fill_profile(page: Page, name: str, alliance: str) -> None:
    page.get_by_test_id('profile-game-name').fill(name)
    page.get_by_test_id('profile-alliance').fill(alliance)


def fill_answers(page: Page, construction='', research='', troop='') -> None:
    page.get_by_test_id(ANSWER['construction']).fill(construction)
    page.get_by_test_id(ANSWER['research']).fill(research)
    page.get_by_test_id(ANSWER['troop']).fill(troop)


def next_step(page: Page) -> None:
    before = step_no(page)
    page.get_by_test_id('wizard-next').click()
    expect_step(page, before + 1)


def back_step(page: Page) -> None:
    before = step_no(page)
    page.get_by_test_id('wizard-back').click()
    expect_step(page, before - 1)


def slot(page: Page, day_type: str, hhmm: str):
    """Hour button on a day step's grid (UTC value)."""
    return page.get_by_test_id(f'slot-{day_type}-{hhmm}')


def toggle_slots(page: Page, day_type: str, hours: list[str]) -> None:
    """On the current day step, click each hour and check it is now selected."""
    for h in hours:
        slot(page, day_type, h).click()
        expect(slot(page, day_type, h)).to_have_attribute('aria-pressed', 'true')


def walk_days(page: Page, pick: dict[str, list[str]] | None = None) -> None:
    """From step 1 (filled) through the three day steps to the review step, picking hours on the way.
    Days without hours raise the 'no slots' confirm: the test must accept dialogs."""
    pick = pick or {}
    next_step(page)
    for day_type, n in DAY_STEPS.items():
        expect_step(page, n)
        expect(page.get_by_test_id(f'wizard-step-{n}')).to_have_attribute('data-day', day_type)
        toggle_slots(page, day_type, pick.get(day_type, []))
        next_step(page)
    expect_step(page, REVIEW_STEP)


def go_to_step(page: Page, n: int) -> None:
    """Next/Back until step n (dialogs must be accepted when a day is empty)."""
    while step_no(page) < n:
        next_step(page)
    while step_no(page) > n:
        back_step(page)


def expect_review_slots(page: Page, by_day: dict[str, list[str]]) -> None:
    """Review step: each day lists exactly these UTC hours."""
    for day_type, hours in by_day.items():
        chips = page.get_by_test_id(f'review-slots-{day_type}').locator('[data-slot]')
        expect(chips).to_have_count(len(hours))
        for h in hours:
            expect(page.get_by_test_id(f'review-slots-{day_type}').locator(f'[data-slot="{h}"]')).to_be_visible()


def submit(page: Page) -> None:
    page.get_by_test_id('wizard-submit').click()
    expect(page.get_by_test_id('save-success')).to_be_visible()


# --- raw i18n key detection -------------------------------------------------
# A missing i18next key renders as the key itself, e.g. 'form.next' or 'ministry.apply.title'.
_KEY_RE = re.compile(r'(?<![\w/@.-])([a-z][a-zA-Z0-9_]+(?:\.[a-zA-Z_][a-zA-Z0-9_]+)+)(?![\w/-])')
_NS_KEY_RE = re.compile(r'\b(?:common|profile|ministry|admin|guide|changelog|tyrant|svs|tal):[a-zA-Z_][\w.]*')
_NOT_KEYS_LAST = {'com', 'org', 'net', 'io', 'gg', 'app', 'dev', 'png', 'jpg', 'svg', 'js',
                  'json', 'md', 'py', 'html', 'invalid'}

_COLLECT_JS = r"""
() => {
  const out = [document.title, document.body.innerText];
  for (const el of document.querySelectorAll('[placeholder],[title],[aria-label],img[alt]')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    for (const a of ['placeholder', 'title', 'aria-label', 'alt']) {
      const v = el.getAttribute(a); if (v) out.push(v);
    }
  }
  return out.join('\n');
}
"""


def visible_text(page: Page) -> str:
    return page.evaluate(_COLLECT_JS)


def raw_i18n_keys(text: str) -> list[str]:
    """Strings in `text` that look like untranslated i18n keys or interpolation leftovers."""
    found = []
    for m in _KEY_RE.finditer(text):
        tok = m.group(1)
        if tok.rsplit('.', 1)[-1].lower() in _NOT_KEYS_LAST:
            continue
        found.append(tok)
    found += re.findall(r'\{\{\s*\w+\s*\}\}', text)       # '{{count}}' not interpolated
    found += _NS_KEY_RE.findall(text)                       # 'ministry:apply.x' (namespaced key)
    return sorted(set(found))


def check_all_languages(page: Page, where: str, shot=None) -> dict[str, list[str]]:
    """Switch through every language on the current page; return {lang: raw keys}."""
    bad = {}
    for code in LANGUAGES:
        switch_language(page, code)
        keys = raw_i18n_keys(visible_text(page))
        if keys:
            bad[code] = keys
            if shot:
                shot(f'{where}-{code}-RAWKEYS')
    switch_language(page, 'en')
    return bad


# --- API helper (arranges test state; the UI is what is under test) ----------

class Api:
    """Tiny JSON client for the wos-events API (docs/API.md)."""

    def __init__(self, base_url: str, password: str):
        self.base_url = base_url
        self.password = password
        self._token: str | None = None

    def call(self, method: str, path: str, body=None, admin=False, ok=(200, 201)):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        req.add_header('Accept', 'application/json')
        if data is not None:
            req.add_header('Content-Type', 'application/json')
        if admin:
            req.add_header('Authorization', f'Bearer {self.token()}')
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                status, payload = r.status, json.loads(r.read() or b'{}')
        except urllib.error.HTTPError as e:
            status, payload = e.code, json.loads(e.read() or b'{}')
        if ok and status not in ok:
            raise AssertionError(f'{method} {path} -> {status} {payload}')
        return status, payload

    def token(self) -> str:
        if not self._token:
            _, res = self.call('POST', '/api/admin/login', {'password': self.password})
            self._token = res['token']
        return self._token

    def current_round(self):
        status, res = self.call('GET', '/api/events/ministry/current', ok=None)
        return res if status == 200 else None

    def start_new_round(self, name: str, closing_time=None):
        _, res = self.call('POST', '/api/admin/events/ministry/start-new-round',
                           {'name': name, 'closing_time': closing_time}, admin=True)
        return res['round']

    def ensure_open_round(self, name: str):
        return self.current_round() or self.start_new_round(name)

    def update_round(self, round_id: int, **fields):
        _, res = self.call('PUT', f'/api/admin/rounds/{round_id}', fields, admin=True)
        return res

    def application(self, fid: str):
        status, res = self.call('GET', f'/api/events/ministry/current/application/{fid}', ok=None)
        return res if status == 200 else None

    def put_application(self, fid: str, name: str, alliance: str, answers: dict):
        _, res = self.call('PUT', f'/api/events/ministry/current/application/{fid}',
                           {'profile': {'game_name': name, 'alliance': alliance}, 'answers': answers})
        return res
