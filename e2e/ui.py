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
    'ministry': '/ministry',
    'apply': '/ministry/apply',            # FID first, then "New application" / "Edit your application"
    'admin_login': '/admin',
    'admin_dashboard': '/admin/dashboard',
    'player_guide': '/ministry/guide',
    'admin_guide': '/admin/guide',
    'changelog': '/changelog',
}

# Old URL -> where it must land (bookmarks / shared links keep working).
LEGACY_REDIRECTS = {
    '/submit': '/ministry/apply',
    '/apply': '/ministry/apply',
    '/update': '/ministry/apply',
    '/ministry/submit': '/ministry/apply',
    '/ministry/update': '/ministry/apply',
    '/guide': '/ministry/guide',
    '/ministry/admin': '/admin',
}

# Pages that need no login, checked for raw i18n keys in every language.
PUBLIC_PAGES = ['home', 'ministry', 'apply', 'admin_login', 'player_guide', 'changelog']

# --- languages ------------------------------------------------------------
# code -> label on the language-switch button (the native name; same in every UI language)
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


def switch_language(page: Page, code: str) -> None:
    page.get_by_role('button', name=LANGUAGES[code], exact=True).click()
    page.wait_for_function(
        "dir => document.documentElement.dir === dir",
        arg='rtl' if code in RTL_LANGUAGES else 'ltr')


def admin_login(page: Page, base_url: str, password: str) -> None:
    """Log in through the UI (password found by its <label>) and land on the dashboard."""
    go(page, base_url, 'admin_login')
    page.get_by_label(en('admin:password')).fill(password)
    page.get_by_test_id('admin-login').click()
    page.wait_for_url('**' + ROUTES['admin_dashboard'])
    expect(page.get_by_test_id('round-select')).to_be_visible()
    page.wait_for_load_state('networkidle')


def enter_fid(page: Page, base_url: str, fid: str) -> None:
    go(page, base_url, 'apply')
    page.get_by_test_id('fid-input').fill(fid)
    page.get_by_test_id('fid-continue').click()


def open_application(page: Page, base_url: str, fid: str) -> str:
    """Apply page -> enter FID -> wait for the form or the closed state. Returns 'new'|'edit'|'closed'."""
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


def day_tab(page: Page, day_type: str):
    return page.get_by_test_id(f'day-tab-{day_type}')


def slot(page: Page, day_type: str, hhmm: str):
    """Hour button on the time-preference grid for one day type (UTC value)."""
    return page.get_by_test_id(f'slot-{day_type}-{hhmm}')


def pick_slots(page: Page, by_day: dict[str, list[str]]) -> None:
    for day_type, hours in by_day.items():
        day_tab(page, day_type).click()
        for h in hours:
            slot(page, day_type, h).click()
            expect(slot(page, day_type, h)).to_have_attribute('aria-pressed', 'true')


def expect_slots(page: Page, by_day: dict[str, list[str]]) -> None:
    for day_type, hours in by_day.items():
        day_tab(page, day_type).click()
        for h in hours:
            expect(slot(page, day_type, h)).to_have_attribute('aria-pressed', 'true')


def save_application(page: Page) -> None:
    page.get_by_test_id('save-application').click()
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
