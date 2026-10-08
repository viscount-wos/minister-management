"""Event Management: the one admin shell for every event (docs/SPEC.md "Event Management admin").

Branding (title + contextual subtitle, en and ar), event-page admin links landing on that event,
the event switch keeping the login, token expiry returning to the same event, the contextual
guide button, document.title per page and raw-key checks in 9 languages.

The admin login is throttled on failures only, but to stay light most tests reuse ONE API token
(session `api` fixture) through localStorage instead of logging in through the UI.
"""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

import ui

ADMIN_EVENTS = {          # event key -> (name key, subtitle key, public page)
    'ministry': ('ministry:event.name', 'ministry:event.adminSubtitle', '/minister'),
    'tyrant': ('tyrant:name', 'tyrant:admin.adminSubtitle', '/tyrant'),
}


def tr(key: str, lang: str = 'en', **v) -> str:
    return ui.tr(lang, key, **v)


def title_of(lang: str, *parts: str) -> str:
    """document.title as usePageTitle builds it: parts, then the app name, joined with ' · '."""
    return ' · '.join([*parts, tr('common:appTitle', lang)])


@pytest.fixture(scope='module')
def token(api) -> str:
    return api.token()


@pytest.fixture(scope='module', autouse=True)
def tyrant_open(api):
    """The Tyrant dashboard needs a round for its tabs; open one if none is open."""
    status, _ = api.call('GET', '/api/events/tyrant/current', ok=None)
    if status != 200:
        api.call('POST', '/api/admin/events/tyrant/start-new-round', {'name': 'E2E shell tyrant'}, admin=True)


def logged_out(page: Page, base_url: str) -> None:
    page.goto(base_url + '/')
    page.evaluate("localStorage.clear()")


# ------------------------------------------------------------------ branding

@pytest.mark.parametrize('lang', ['en', 'ar'])
def test_login_title(page: Page, base_url, shot, lang):
    logged_out(page, base_url)
    page.goto(base_url + '/admin?event=tyrant')
    if lang != 'en':
        ui.switch_language(page, lang)
    expect(page.get_by_test_id('admin-title')).to_have_text(tr('admin:title', lang))
    expect(page.get_by_test_id('admin-login-event')).to_have_text(tr('tyrant:name', lang))
    expect(page.get_by_test_id('admin-login-back')).to_have_text(
        tr('admin:shell.backTo', lang, event=tr('tyrant:name', lang)))
    assert 'Minister Administration' not in ui.visible_text(page)
    expect(page).to_have_title(title_of(lang, tr('admin:title', lang)))
    if lang == 'ar':
        assert page.evaluate('document.documentElement.dir') == 'rtl'
    shot(f'login-{lang}')


@pytest.mark.parametrize('lang', ['en', 'ar'])
def test_dashboard_title_and_contextual_subtitle(page: Page, base_url, token, shot, lang):
    ui.use_admin_token(page, base_url, token, ui.admin_dashboard_url('ministry'))
    if lang != 'en':
        ui.switch_language(page, lang)
    for event, (name, subtitle, _) in ADMIN_EVENTS.items():
        if event != 'ministry':
            page.get_by_test_id(f'admin-event-{event}').click()
        expect(page.get_by_test_id('admin-shell')).to_have_attribute('data-event', event)
        expect(page.get_by_test_id('admin-title')).to_have_text(tr('admin:title', lang))
        expect(page.get_by_test_id('admin-subtitle')).to_have_text(tr(subtitle, lang))
        expect(page.get_by_test_id(f'admin-event-{event}')).to_have_attribute('aria-selected', 'true')
        expect(page).to_have_title(title_of(lang, tr(name, lang), tr('admin:title', lang)))
        page.wait_for_load_state('networkidle')
        text = ui.visible_text(page)
        assert 'Minister Administration' not in text and 'ministry assignments' not in text
        shot(f'dashboard-{event}-{lang}')


# ------------------------------------------------------------------ landing

def test_event_page_admin_link_lands_on_that_event(page: Page, base_url, admin_password, shot):
    logged_out(page, base_url)
    page.goto(base_url + '/tyrant')
    page.get_by_test_id('tyrant-admin-tile').click()
    page.wait_for_url('**/admin?event=tyrant')
    expect(page.get_by_test_id('admin-title')).to_have_text(tr('admin:title'))
    page.get_by_label(tr('admin:password')).fill(admin_password)
    page.get_by_test_id('admin-login').click()                      # the one UI login of this file
    page.wait_for_url('**' + ui.admin_dashboard_url('tyrant'))
    expect(page.get_by_test_id('tyrant-admin')).to_be_visible()
    shot('landed-tyrant')

    # already logged in: the ministry page's admin tile goes straight to the ministry dashboard
    page.goto(base_url + '/minister')
    page.get_by_test_id('ministry-admin-tile').click()
    page.wait_for_url('**' + ui.admin_dashboard_url('ministry'))
    expect(page.get_by_test_id('ministry-admin')).to_be_visible()

    # Home's link lands on the LAST event administered (localStorage)
    page.goto(base_url + '/tyrant')
    page.get_by_test_id('tyrant-admin-tile').click()
    page.wait_for_url('**' + ui.admin_dashboard_url('tyrant'))
    page.goto(base_url + '/')
    page.get_by_test_id('home-admin-link').click()
    page.wait_for_url('**' + ui.admin_dashboard_url('tyrant'))
    expect(page.get_by_test_id('admin-shell')).to_have_attribute('data-event', 'tyrant')
    # old URL without ?event= still works and resolves the same way
    page.goto(base_url + ui.ROUTES['admin_dashboard'])
    page.wait_for_url('**' + ui.admin_dashboard_url('tyrant'))


def test_home_link_defaults_to_ministry(page: Page, base_url, token):
    ui.use_admin_token(page, base_url, token)
    page.evaluate("localStorage.removeItem('adminLastEvent')")
    page.goto(base_url + '/')
    page.get_by_test_id('home-admin-link').click()
    page.wait_for_url('**' + ui.admin_dashboard_url('ministry'))


def test_event_switch_keeps_login(page: Page, base_url, token, shot):
    ui.use_admin_token(page, base_url, token, ui.admin_dashboard_url('ministry'))
    expect(page.get_by_test_id('ministry-admin')).to_be_visible()
    page.get_by_test_id('admin-event-tyrant').click()
    page.wait_for_url('**' + ui.admin_dashboard_url('tyrant'))
    expect(page.get_by_test_id('tyrant-admin')).to_be_visible()
    expect(page.get_by_test_id('stat-total-value')).to_be_visible()  # tyrant data loaded with the same token
    page.reload()
    expect(page.get_by_test_id('tyrant-admin')).to_be_visible()
    page.get_by_test_id('admin-event-ministry').click()
    page.wait_for_url('**' + ui.admin_dashboard_url('ministry'))
    expect(page.get_by_test_id('tab-assignments')).to_be_visible()
    assert page.evaluate("localStorage.getItem('adminToken')") == token
    assert '/admin?' not in page.url


def test_expired_token_returns_to_same_event(page: Page, base_url, admin_password, shot):
    ui.use_admin_token(page, base_url, 'admin-token', ui.admin_dashboard_url('tyrant'))  # forged/expired
    page.wait_for_url('**/admin?event=tyrant&expired=1')
    expect(page.get_by_test_id('session-expired')).to_have_text(tr('admin:sessionExpired'))
    expect(page.get_by_test_id('admin-login-event')).to_have_attribute('data-event', 'tyrant')
    shot('expired-tyrant')
    page.get_by_label(tr('admin:password')).fill(admin_password)
    page.get_by_test_id('admin-login').click()
    page.wait_for_url('**' + ui.admin_dashboard_url('tyrant'))
    expect(page.get_by_test_id('tyrant-admin')).to_be_visible()


# ------------------------------------------------------------------ guides

def test_guide_button_is_contextual(page: Page, base_url, token, shot):
    ui.use_admin_token(page, base_url, token, ui.admin_dashboard_url('tyrant'))
    page.get_by_test_id('admin-guide-link').click()
    page.wait_for_url('**' + ui.admin_guide_url('tyrant'))
    expect(page.get_by_test_id('admin-guide-tyrant')).to_be_visible()
    expect(page.get_by_test_id('admin-guide-ministry')).to_have_count(0)
    expect(page.get_by_role('heading', name=tr('guide:tyrantAdmin.windowsTitle'))).to_be_visible()
    expect(page).to_have_title(title_of('en', tr('guide:admin.title'), tr('tyrant:name')))
    shot('guide-tyrant-en')
    ui.switch_language(page, 'ar')
    expect(page.get_by_role('heading', name=tr('guide:tyrantAdmin.windowsTitle', 'ar'))).to_be_visible()
    shot('guide-tyrant-ar')
    ui.switch_language(page, 'en')
    # the guide's own event switch
    page.get_by_test_id('admin-event-ministry').click()
    page.wait_for_url('**' + ui.admin_guide_url('ministry'))
    expect(page.get_by_test_id('admin-guide-ministry')).to_be_visible()
    # back goes to that event's dashboard; its guide button opens the ministry guide
    page.get_by_test_id('guide-back').click()
    page.wait_for_url('**' + ui.admin_dashboard_url('ministry'))
    page.get_by_test_id('admin-guide-link').click()
    page.wait_for_url('**' + ui.admin_guide_url('ministry'))
    expect(page.get_by_test_id('admin-guide-ministry')).to_be_visible()


# ------------------------------------------------------------------ document.title

PAGE_TITLES = [   # path, title parts (i18n keys, most specific first)
    ('/', []),
    ('/minister', ['ministry:event.name']),
    ('/minister/apply', ['ministry:apply.title']),
    ('/minister/guide', ['guide:player.title', 'ministry:event.name']),
    ('/minister/schedule/monday', ['ministry:schedule.title']),
    ('/tyrant', ['tyrant:name']),
    ('/tyrant/apply', ['tyrant:apply.title']),
    ('/svs', ['svs:name']),
    ('/tal', ['tal:name']),
    ('/changelog', ['changelog:title']),
    ('/admin', ['admin:title']),
    ('/admin/guide?event=tyrant', ['guide:admin.title', 'tyrant:name']),
    ('/admin/dashboard?event=tyrant', ['tyrant:name', 'admin:title']),
    ('/admin/dashboard?event=ministry', ['ministry:event.name', 'admin:title']),
]


def test_document_title_per_page(page: Page, base_url, token):
    ui.use_admin_token(page, base_url, token)
    bad = []
    for lang in ('en', 'ar'):
        for path, parts in PAGE_TITLES:
            if path == '/admin':        # logged in, /admin would jump to the dashboard
                page.evaluate("localStorage.removeItem('adminToken')")
            page.goto(base_url + path)
            page.wait_for_load_state('networkidle')
            if lang != 'en':
                ui.switch_language(page, lang)
            want = title_of(lang, *[tr(k, lang) for k in parts])
            try:
                expect(page).to_have_title(want, timeout=3000)
            except AssertionError:
                bad.append((lang, path, page.title(), want))
            if path == '/admin':
                page.evaluate("t => localStorage.setItem('adminToken', t)", token)
    assert not bad, bad
    assert 'Ministry Management' not in page.title()


# ------------------------------------------------------------------ 9 languages

def test_no_raw_keys_admin_shell_and_tyrant_guide(page: Page, base_url, token, shot):
    bad = {}
    logged_out(page, base_url)
    page.goto(base_url + '/admin?event=tyrant')
    page.wait_for_load_state('networkidle')
    if found := ui.check_all_languages(page, 'login-tyrant', shot):
        bad['login'] = found
    ui.use_admin_token(page, base_url, token)
    for event in ADMIN_EVENTS:
        page.goto(base_url + ui.admin_dashboard_url(event))
        page.wait_for_load_state('networkidle')
        expect(page.get_by_test_id('admin-subtitle')).to_be_visible()
        if found := ui.check_all_languages(page, f'shell-{event}', shot):
            bad[f'shell-{event}'] = found
        for code in ui.LANGUAGES:   # the title/subtitle really change per language
            ui.switch_language(page, code)
            expect(page.get_by_test_id('admin-title')).to_have_text(tr('admin:title', code))
            expect(page.get_by_test_id('admin-subtitle')).to_have_text(tr(ADMIN_EVENTS[event][1], code))
        ui.switch_language(page, 'en')
    page.goto(base_url + ui.admin_guide_url('tyrant'))
    page.wait_for_load_state('networkidle')
    if found := ui.check_all_languages(page, 'guide-tyrant', shot):
        bad['guide-tyrant'] = found
    for code in ui.LANGUAGES:
        ui.switch_language(page, code)
        expect(page.get_by_test_id('admin-guide-tyrant')).to_contain_text(tr('guide:tyrantAdmin.workflow6', code))
    assert not bad, f'raw i18n keys: {bad}'


# ------------------------------------------------------------------ welcome line

def test_welcome_hidden_until_state_number_set(page: Page, base_url, api):
    _, s = api.call('GET', '/api/settings/public')
    if s['state_number'] is None:
        for path in ('/', '/minister', '/tyrant'):
            page.goto(base_url + path)
            page.wait_for_load_state('networkidle')
            expect(page.get_by_test_id('welcome')).to_have_count(0)
            assert '2694' not in ui.visible_text(page)
        api.call('PUT', '/api/admin/settings', {'state_number': '2807'}, admin=True)
    _, s = api.call('GET', '/api/settings/public')
    page.goto(base_url + '/')
    expect(page.get_by_test_id('welcome')).to_have_text(tr('common:home.welcome', state=s['state_number']))
    assert re.search(r'\b2694\b', ui.visible_text(page)) is None or s['state_number'] == '2694'


# ------------------------------------------------------------------ "Minister", never "Ministry"

_MINISTRY = re.compile(r'ministr(y|ies)', re.I)


def test_no_ministry_wording_in_english(page: Page, base_url, token, shot):
    """Owner rule: players and admins see "Minister" (the in-game term), never "Ministry".
    The event key 'ministry' stays in URLs of the API, test ids and code only."""
    ui.use_admin_token(page, base_url, token)
    bad = {}

    def check(where: str) -> None:
        page.wait_for_load_state('networkidle')
        found = sorted({m.group(0) for m in _MINISTRY.finditer(ui.visible_text(page))})
        if found:
            bad[where] = found
            shot(f'{where}-MINISTRY')

    for path in ('/', '/minister', '/minister/apply', '/minister/guide', '/minister/schedule/monday',
                 '/changelog', '/tyrant', ui.admin_guide_url('ministry')):
        page.goto(base_url + path)
        check(path)
    page.goto(base_url + ui.admin_dashboard_url('ministry'))
    for tab in ('players', 'assignments', 'settings'):
        page.get_by_test_id(f'tab-{tab}').click()
        check(f'admin-{tab}')
    page.get_by_test_id('start-new-round').click()
    check('admin-start-round-dialog')
    page.get_by_test_id('cancel-new-round').click()
    page.evaluate("localStorage.removeItem('adminToken')")
    page.goto(base_url + '/admin?event=ministry')
    check('admin-login')
    assert not bad, f'"Ministry" still visible: {bad}'
    # the old /ministry URLs redirect to /minister keeping the query string
    page.goto(base_url + '/ministry/apply?fid=123&x=1')
    page.wait_for_url('**/minister/apply?fid=123&x=1')
