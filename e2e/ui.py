"""Every route, selector and UI string the smoke suite relies on, in ONE place.

When the app is restructured (ministry pages move under /ministry/...), update this file
first; the tests themselves should not need to change much. Entries marked `# v1.4` are
the ones known to move or change shape in wos-events (see README "After the restructure").
"""
from __future__ import annotations

import re

from playwright.sync_api import Page

# --- routes ---------------------------------------------------------------
ROUTES = {
    'home': '/',
    'apply': '/submit',              # v1.4 -> /ministry/apply (old path should redirect)
    'update': '/update',             # v1.4 -> /ministry/... (old path should redirect)
    'admin_login': '/admin',
    'admin_dashboard': '/admin/dashboard',   # v1.4 -> /admin/... per event
    'player_guide': '/guide',        # v1.4 -> /ministry/guide?
    'admin_guide': '/admin/guide',
    'changelog': '/changelog',
}

# Pages that need no login, checked for raw i18n keys in every language.
PUBLIC_PAGES = ['home', 'apply', 'update', 'admin_login', 'player_guide', 'changelog']

# --- languages ------------------------------------------------------------
# code -> label on the language-switch button (the native name; same in every UI language)
LANGUAGES = {
    'en': 'English', 'es': 'Español', 'fr': 'Français', 'de': 'Deutsch', 'pl': 'Polski',
    'ko': '한국어', 'zh': '中文', 'tr': 'Türkçe', 'ar': 'العربية',
}
RTL_LANGUAGES = {'ar'}

# --- UI strings (copied from frontend/src/i18n.ts v1.4; later: locales/<lang>/*.json) ----
STRINGS = {
    'en': {
        'home.submitNew': 'Submit New Application',          # v1.4 home tile; v2: ministry tile
        'home.updateExisting': 'View Assignment / Update Info',
        'form.next': 'Next',
        'form.submit': 'Submit',
        'form.success': 'Success!',
        'form.update': 'Update',
        'form.playerIDPlaceholder': 'Enter your unique Player ID',
        'form.playerAlreadyExists': 'already exists',
        'update.fidLabel': 'Player ID (FID)',
        'update.load': 'Load My Data',
        'admin.login': 'Login',
        'admin.search': 'Search players...',
        'admin.players': 'Players',
        'admin.assignments': 'Assignments',
        'admin.settings': 'Settings',
        'research_tab': 'Research Day',                       # prefix of form.researchTimes
    },
    'ar': {
        'form.next': 'التالي',
        'form.submit': 'إرسال',
        'form.success': 'نجح!',
        'form.playerIDPlaceholder': 'أدخل معرف اللاعب الفريد الخاص بك',
    },
}

# --- form fields (v1.4 uses name= attributes; labels are not associated with inputs) -----
FIELD = {
    'fid': 'input[name="fid"]',
    'game_name': 'input[name="game_name"]',
    'alliance': 'input[name="alliance"]',
    'construction': 'input[name="construction_speedups_days"]',
    'research': 'input[name="research_speedups_days"]',
    'troop': 'input[name="troop_training_speedups_days"]',
    'admin_password': 'input[type="password"]',
}


def go(page: Page, base_url: str, route: str) -> None:
    page.goto(base_url + ROUTES[route])
    page.wait_for_load_state('networkidle')


def switch_language(page: Page, code: str) -> None:
    page.get_by_role('button', name=LANGUAGES[code], exact=True).click()
    page.wait_for_function(
        "dir => document.documentElement.dir === dir",
        arg='rtl' if code in RTL_LANGUAGES else 'ltr')


def admin_login(page: Page, base_url: str, password: str) -> None:
    """Log in through the UI and land on the dashboard (English)."""
    go(page, base_url, 'admin_login')
    page.locator(FIELD['admin_password']).fill(password)
    page.get_by_role('button', name=STRINGS['en']['admin.login'], exact=True).click()
    page.wait_for_url('**' + ROUTES['admin_dashboard'])
    page.wait_for_load_state('networkidle')


def fill_apply_step1(page: Page, fid: str, name: str, alliance: str,
                     construction='0', research='0', troop='0') -> None:
    page.locator(FIELD['fid']).fill(fid)
    page.locator(FIELD['game_name']).fill(name)
    page.locator(FIELD['alliance']).fill(alliance)
    page.locator(FIELD['construction']).fill(construction)
    page.locator(FIELD['research']).fill(research)
    page.locator(FIELD['troop']).fill(troop)


def time_slot_button(page: Page, hhmm: str):
    """Hour button on the time-preference grid (UTC display: exact text '12:00')."""
    return page.get_by_role('button', name=hhmm, exact=True)


# --- raw i18n key detection -------------------------------------------------
# A missing i18next key renders as the key itself, e.g. 'form.next' or 'ministry.apply.title'.
_KEY_RE = re.compile(r'(?<![\w/@.-])([a-z][a-zA-Z0-9_]+(?:\.[a-zA-Z_][a-zA-Z0-9_]+)+)(?![\w/-])')
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
    return sorted(set(found))
