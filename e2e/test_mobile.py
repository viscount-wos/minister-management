"""Phone e2e: Playwright device emulation (iPhone 13 = 390px, Pixel 7 = 412px; 360px is covered by the
audit in the mobile wizard tests via a Galaxy S8-sized context).

Covers: the compact header (one row, dropdowns), language + timezone auto-detect and remembered choices,
<html dir/lang> before the first paint, home / Minister wizard NEW / Tyrant wizard NEW / status pages / guides,
no sideways scroll on any page, >=44px tap targets for key controls, mobile keyboards (inputmode) and no iOS
zoom (inputs >= 16px), the sticky Back/Next bar, and the admin on a phone (tabs, tap-to-move).

Screenshots: artifacts/<run>/mobile/<device>-<lang>-<page>.png (full page; the sticky bar is unstuck for the
capture so it does not cover content).
"""
from __future__ import annotations

import re
import secrets
import time
from pathlib import Path

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, expect

import ui
from conftest import ARTIFACTS, RUN_ID

DEVICES = ['iPhone 13', 'Pixel 7']
NARROW = {'viewport': {'width': 360, 'height': 740}, 'screen': {'width': 360, 'height': 740},
          'device_scale_factor': 3, 'is_mobile': True, 'has_touch': True,
          'user_agent': 'Mozilla/5.0 (Linux; Android 8.0.0; SM-G950F) AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/120.0 Mobile Safari/537.36'}
SHOTS = ARTIFACTS / RUN_ID / 'mobile'
TAP = 43.5          # px; 44 with sub-pixel rounding
RUN = time.strftime('%H%M%S')


def slug(s: str) -> str:
    return re.sub(r'[^\w.-]+', '-', s).strip('-').lower()


def device_args(playwright: Playwright, device: str) -> dict:
    if device == 'narrow-360':
        return dict(NARROW)
    args = dict(playwright.devices[device])
    args.pop('default_browser_type', None)      # we run every device on chromium
    return args


@pytest.fixture
def phone(browser: Browser, playwright: Playwright, base_url):
    """phone(device, locale=..., timezone_id=...) -> Page in a fresh mobile context."""
    contexts: list[BrowserContext] = []

    def make(device: str, locale: str = 'en-US', timezone_id: str = 'UTC', **extra) -> Page:
        ctx = browser.new_context(**device_args(playwright, device), base_url=base_url, locale=locale,
                                  timezone_id=timezone_id, **extra)
        contexts.append(ctx)
        page = ctx.new_page()
        page.on('dialog', lambda d: d.accept())       # "no time slots selected" confirm
        return page

    yield make
    for c in contexts:
        c.close()


class Phone:
    """Checks shared by every phone page."""

    def __init__(self, page: Page, device: str, lang: str):
        self.page, self.device, self.lang = page, device, lang
        self.width = page.viewport_size['width']

    def goto(self, path: str):
        self.page.goto(path)
        self.page.wait_for_load_state('networkidle')

    def shot(self, name: str):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page = self.page
        time.sleep(0.45)        # global 0.2 s colour transition
        page.add_style_tag(content='[data-testid=wizard-nav]{position:static!important}')
        page.screenshot(path=str(SHOTS / f'{slug(self.device)}-{self.lang}-{name}.png'), full_page=True)
        page.evaluate("document.querySelectorAll('style').forEach(s => { if (s.textContent.includes('wizard-nav]{position:static')) s.remove(); })")

    def check(self, name: str, tappable: list[str] = ()):
        """No sideways scroll, header in one row, key controls >= 44px, inputs >= 16px; then a screenshot."""
        page = self.page
        sw = page.evaluate('document.documentElement.scrollWidth')
        iw = page.evaluate('window.innerWidth')
        assert sw <= self.width and iw == self.width, f'{name}: sideways scroll (scrollWidth {sw}, viewport {self.width})'
        # header: the three dropdowns sit in ONE row, each a 44px target
        boxes = [page.get_by_test_id(f'{t}-chip').bounding_box() for t in (ui.TIMEZONE_SELECT, ui.LANGUAGE_SELECT, ui.THEME_SELECT)]
        tops = {round(b['y']) for b in boxes}
        assert max(tops) - min(tops) <= 2, f'{name}: header controls not in one row: {boxes}'
        for b in boxes:
            assert b['height'] >= TAP and b['width'] >= TAP, f'{name}: header control too small {b}'
            assert b['x'] >= 0 and b['x'] + b['width'] <= self.width + 0.5, f'{name}: header control off screen {b}'
        header = page.get_by_test_id('site-header').bounding_box()
        assert header['height'] <= 72, f'{name}: header takes {header["height"]}px'
        for tid in tappable:
            loc = page.get_by_test_id(tid)
            for i in range(loc.count()):
                b = loc.nth(i).bounding_box()
                if b:
                    assert b['height'] >= TAP, f'{name}: {tid} is {b["height"]}px tall'
        small_inputs = page.evaluate("""() => [...document.querySelectorAll('input:not([type=checkbox]):not([type=radio]), select, textarea')]
            .filter(e => e.getBoundingClientRect().width > 0 && parseFloat(getComputedStyle(e).fontSize) < 16)
            .map(e => e.getAttribute('data-testid') || e.id)""")
        assert not small_inputs, f'{name}: inputs under 16px (iOS zooms on focus): {small_inputs}'
        self.shot(name)

    def expect_nav_in_view(self):
        """Back/Next always reachable: the bar sticks to the bottom of the screen on phones."""
        page = self.page
        nav = page.get_by_test_id('wizard-nav')
        assert nav.evaluate('e => getComputedStyle(e).position') == 'sticky'
        b = nav.bounding_box()
        vh = page.viewport_size['height']
        assert b['y'] + b['height'] <= vh + 1 and b['y'] >= 0, f'wizard nav not on screen: {b} (viewport {vh})'
        for tid in ('wizard-back', 'wizard-next', 'wizard-submit'):
            loc = page.get_by_test_id(tid)
            if loc.count():
                assert loc.bounding_box()['height'] >= TAP

    def expect_steps_fit(self):
        """Every step circle inside the wizard card (not touching its edge)."""
        card = self.page.get_by_test_id('wizard').bounding_box()
        for i in range(self.page.get_by_test_id('wizard-steps').locator('li').count()):
            b = self.page.get_by_test_id(f'wizard-step-indicator-{i + 1}').locator('div').first.bounding_box()
            assert b['x'] >= card['x'] + 8 and b['x'] + b['width'] <= card['x'] + card['width'] - 8, \
                f'step circle {i + 1} touches/leaves the card: {b} vs {card}'


def fresh_fid() -> str:
    return str(60_000_000 + secrets.randbelow(9_999_999))


def ensure_tyrant_round(api: ui.Api):
    status, res = api.call('GET', '/api/events/tyrant/current', ok=None)
    if status == 200:
        return res
    _, res = api.call('POST', '/api/admin/events/tyrant/start-new-round', {'name': f'Mobile e2e {RUN}'}, admin=True)
    return res['round']


# ------------------------------------------------------------------ header / home / static pages

@pytest.mark.parametrize('device', DEVICES + ['narrow-360'])
@pytest.mark.parametrize('lang,locale', [('en', 'en-GB'), ('ar', 'ar-SA')])
def test_home_and_static_pages(phone, device, lang, locale):
    page = phone(device, locale=locale)
    p = Phone(page, device, lang)
    for name, path in [('home', '/'), ('minister-home', '/minister'), ('minister-guide', '/minister/guide'),
                       ('minister-schedule-unpublished', '/minister/schedule/monday'), ('tyrant-home', '/tyrant'),
                       ('svs', '/svs'), ('changelog', '/changelog')]:
        p.goto(path)
        assert page.evaluate('document.documentElement.lang') == lang
        assert page.evaluate('document.documentElement.dir') == ('rtl' if lang == 'ar' else 'ltr')
        p.check(name, tappable=['event-tile-ministry', 'event-tile-tyrant', 'home-admin-link', 'nav-home',
                                'ministry-apply-tile', 'tyrant-apply-tile'])
    p.goto('/')
    expect(page.locator('h1').first).to_have_text(ui.tr(lang, 'common:home.title'))


@pytest.mark.parametrize('device', DEVICES)
def test_language_dropdown_switches_to_arabic_and_is_remembered(phone, device):
    page = phone(device)
    p = Phone(page, device, 'en')
    p.goto('/')
    select = page.get_by_test_id(ui.LANGUAGE_SELECT)
    expect(select).to_have_accessible_name(ui.en('common:header.language'))
    # globe + current language in its own script; all 9 by native name
    expect(page.get_by_test_id(f'{ui.LANGUAGE_SELECT}-chip')).to_contain_text('English')
    assert select.locator('option').all_inner_texts() == list(ui.LANGUAGES.values())
    ui.switch_language(page, 'ar')
    assert page.evaluate('document.documentElement.dir') == 'rtl'
    expect(page.get_by_test_id(f'{ui.LANGUAGE_SELECT}-chip')).to_contain_text('العربية')
    expect(page.locator('h1').first).to_have_text(ui.tr('ar', 'common:home.title'))
    p.lang = 'ar'
    p.check('home-after-switch')
    page.reload()
    page.wait_for_load_state('networkidle')
    assert page.evaluate('document.documentElement.dir') == 'rtl', 'language choice not remembered'
    # theme dropdown: palette icon, theme names; the choice is remembered too
    page.get_by_test_id(ui.THEME_SELECT).select_option('reading')
    page.reload()
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") == 'reading'


# ------------------------------------------------------------------ auto-detect

@pytest.mark.parametrize('locale,lang', [('tr-TR', 'tr'), ('ar-SA', 'ar'), ('es-MX', 'es'), ('zh-TW', 'zh'),
                                         ('xx', 'en'), ('pt-BR', 'en')])
def test_language_auto_detected_from_browser(phone, locale, lang):
    page = phone('Pixel 7', locale=locale)
    page.goto('/')
    page.wait_for_load_state('networkidle')
    assert page.evaluate('document.documentElement.lang') == lang
    assert page.evaluate('document.documentElement.dir') == ('rtl' if lang == 'ar' else 'ltr')
    expect(page.locator('h1').first).to_have_text(ui.tr(lang, 'common:home.title'))
    expect(page.get_by_test_id(ui.LANGUAGE_SELECT)).to_have_value(lang)


def test_saved_language_beats_browser_language(phone):
    page = phone('iPhone 13', locale='tr-TR')
    page.goto('/')
    assert page.evaluate('document.documentElement.lang') == 'tr'
    ui.switch_language(page, 'de')
    page.goto('/minister')
    page.wait_for_load_state('networkidle')
    assert page.evaluate('document.documentElement.lang') == 'de'
    expect(page.locator('h1').first).to_have_text(ui.tr('de', 'ministry:home.title'))


def test_rtl_set_before_first_paint(phone):
    """Arabic phone, app JavaScript blocked: <html dir/lang> must already be right (no LTR flash)."""
    page = phone('iPhone 13', locale='ar-SA')
    page.route(re.compile(r'.*/assets/.*\.js$'), lambda route: route.abort())
    page.goto('/')
    assert page.evaluate('document.documentElement.dir') == 'rtl'
    assert page.evaluate('document.documentElement.lang') == 'ar'


@pytest.mark.parametrize('tz,label', [('Asia/Seoul', 'KST'), ('America/New_York', 'ET'), ('Europe/Berlin', 'Berlin'),
                                      ('UTC', 'UTC')])
def test_timezone_auto_detected(phone, tz, label):
    page = phone('Pixel 7', timezone_id=tz)
    page.goto('/')
    page.wait_for_load_state('networkidle')
    expect(page.get_by_test_id(ui.TIMEZONE_SELECT)).to_have_value(tz)
    expect(page.get_by_test_id(f'{ui.TIMEZONE_SELECT}-chip')).to_contain_text(label)


def test_saved_timezone_beats_detected(phone):
    page = phone('iPhone 13', timezone_id='Asia/Seoul')
    page.goto('/')
    page.get_by_test_id(ui.TIMEZONE_SELECT).select_option('America/Chicago')
    page.reload()
    page.wait_for_load_state('networkidle')
    expect(page.get_by_test_id(ui.TIMEZONE_SELECT)).to_have_value('America/Chicago')


# ------------------------------------------------------------------ Minister wizard NEW

@pytest.mark.parametrize('device', DEVICES + ['narrow-360'])
@pytest.mark.parametrize('lang,locale', [('en', 'en-US'), ('ar', 'ar-SA')])
def test_minister_wizard_new_on_phone(phone, api, device, lang, locale):
    page = phone(device, locale=locale, timezone_id='Asia/Seoul')    # non-UTC: slots show local + UTC
    p = Phone(page, device, lang)
    fid = fresh_fid()
    p.goto('/minister/apply')
    ui.expect_step(page, 1)
    p.expect_steps_fit()
    fid_input = page.get_by_test_id('fid-input')
    assert fid_input.get_attribute('inputmode') == 'numeric'
    p.expect_nav_in_view()
    p.check('minister-1-fid', tappable=['wizard-back', 'wizard-next'])
    fid_input.fill(fid)
    page.get_by_test_id('wizard-next').click()
    expect(page.get_by_test_id('application-heading')).to_have_attribute('data-mode', 'new')
    ui.fill_profile(page, f'Phone {lang} {RUN}', 'MOB')
    for field, mode in [('construction_speedups_days', 'decimal'), ('research_speedups_days', 'decimal'),
                        ('troop_training_speedups_days', 'decimal')]:
        assert page.get_by_test_id(f'answer-{field}').get_attribute('inputmode') == mode
    ui.fill_answers(page, '12', '3.5', '0')
    p.expect_nav_in_view()
    p.check('minister-1-profile', tappable=['wizard-back', 'wizard-next', 'change-fid'])
    picks = {'construction': ['10:00', '11:00'], 'research': ['12:00'], 'troop': []}
    ui.next_step(page)
    for day, n in ui.DAY_STEPS.items():
        ui.expect_step(page, n)
        p.expect_steps_fit()
        ui.toggle_slots(page, day, picks[day])
        # 24 hour buttons, each a real tap target, local time + UTC inside the button
        grid = page.get_by_test_id(f'slot-grid-{day}')
        for b in grid.locator('button').all():
            bb = b.bounding_box()
            assert bb['height'] >= TAP and bb['width'] >= TAP
        overflow = grid.evaluate("g => [...g.querySelectorAll('button')].filter(b => b.scrollWidth > b.clientWidth + 1).length")
        assert overflow == 0, f'{day}: text clipped in {overflow} hour buttons'
        p.expect_nav_in_view()
        p.check(f'minister-{n}-{day}', tappable=['wizard-back', 'wizard-next', 'wizard-timezone'])
        ui.next_step(page)
    ui.expect_step(page, ui.REVIEW_STEP)
    ui.expect_review_slots(page, picks)
    p.expect_nav_in_view()
    p.check('minister-5-review', tappable=['wizard-back', 'wizard-submit'])
    ui.submit(page)
    p.check('minister-success', tappable=['reopen-application'])
    app = api.application(fid)
    assert app and app['answers']['construction_speedups_days'] == 12
    assert app['answers']['time_slots_by_day']['construction'] == ['10:00', '11:00']


# ------------------------------------------------------------------ Tyrant wizard NEW

@pytest.mark.parametrize('device', DEVICES + ['narrow-360'])
@pytest.mark.parametrize('lang,locale', [('en', 'en-US'), ('ar', 'ar-SA')])
def test_tyrant_wizard_new_on_phone(phone, api, device, lang, locale):
    rnd = ensure_tyrant_round(api)
    page = phone(device, locale=locale)
    p = Phone(page, device, lang)
    fid = fresh_fid()
    p.goto('/tyrant/apply')
    ui.expect_step(page, 1)
    p.expect_steps_fit()
    assert page.get_by_test_id('fid-input').get_attribute('inputmode') == 'numeric'
    p.check('tyrant-1-fid', tappable=['wizard-back', 'wizard-next'])
    page.get_by_test_id('fid-input').fill(fid)
    page.get_by_test_id('wizard-next').click()
    expect(page.get_by_test_id('application-heading')).to_have_attribute('data-mode', 'new')
    page.get_by_test_id('profile-game-name').fill(f'Tyrant {lang} {RUN}')
    page.get_by_test_id('profile-alliance').fill('mob')
    p.expect_nav_in_view()
    p.check('tyrant-1-identity', tappable=['wizard-back', 'wizard-next', 'change-fid'])
    ui.next_step(page)
    # 2 availability: whole rows are the tap targets
    page.locator('label[for=select-all-windows]').click()
    expect(page.get_by_test_id('select-all-windows')).to_be_checked()
    for w in rnd['settings']['windows']:
        assert page.locator(f'label[for=window-{w["id"]}]').bounding_box()['height'] >= TAP
    p.expect_nav_in_view()
    p.check('tyrant-2-windows', tappable=['wizard-back', 'wizard-next'])
    ui.next_step(page)
    # 3 stats: decimal keyboard for power, numeric for gems
    assert page.get_by_test_id('power-millions').get_attribute('inputmode') == 'decimal'
    assert page.get_by_test_id('gem-spend').get_attribute('inputmode') == 'numeric'
    page.get_by_test_id('furnace-level').select_option('FC5')
    page.get_by_test_id('power-millions').fill('123.4')
    page.get_by_test_id('gem-spend').fill('5000')
    p.check('tyrant-3-stats', tappable=['wizard-back', 'wizard-next', 'furnace-level', 'power-millions', 'gem-spend'])
    ui.next_step(page)
    # 4 troops
    for kind in ('infantry', 'lancer', 'marksman'):
        page.get_by_test_id(f'troop-{kind}-furnace').select_option('FC5')
        page.get_by_test_id(f'troop-{kind}-tier').select_option('10')
    p.check('tyrant-4-troops', tappable=['wizard-back', 'wizard-next'])
    ui.next_step(page)
    # 5 roles
    page.locator('label[for=role-joiner]').click()
    expect(page.get_by_test_id('role-joiner')).to_be_checked()
    p.check('tyrant-5-roles', tappable=['wizard-back', 'wizard-next'])
    ui.next_step(page)
    # 6 review: Edit buttons are tap targets
    p.expect_nav_in_view()
    p.check('tyrant-6-review', tappable=['wizard-back', 'wizard-submit', 'review-edit-1', 'review-edit-2'])
    ui.submit(page)
    p.check('tyrant-success', tappable=['reopen-application'])
    _, app = api.call('GET', f'/api/events/tyrant/current/application/{fid}')
    assert app['answers']['roles'] == ['joiner'] and app['answers']['gem_spend'] == 5000
    assert app['answers']['language'] == lang


# ------------------------------------------------------------------ closed / no round (Tyrant; restored after)

@pytest.mark.parametrize('lang,locale', [('en', 'en-US'), ('ar', 'ar-SA')])
def test_closed_and_no_round_states_on_phone(phone, api, lang, locale):
    rnd = ensure_tyrant_round(api)
    device = 'iPhone 13'
    page = phone(device, locale=locale)
    p = Phone(page, device, lang)
    api.call('PUT', f'/api/admin/rounds/{rnd["id"]}', {'closing_time': '2020-01-01T00:00:00Z'}, admin=True)
    try:
        page.goto('/tyrant/apply')
        page.get_by_test_id('fid-input').fill(fresh_fid())
        page.get_by_test_id('wizard-next').click()
        expect(page.get_by_test_id('applications-closed')).to_be_visible()
        p.check('tyrant-closed')
    finally:
        api.call('PUT', f'/api/admin/rounds/{rnd["id"]}', {'closing_time': None}, admin=True)
    api.call('PUT', f'/api/admin/rounds/{rnd["id"]}', {'status': 'closed'}, admin=True)
    try:
        p.goto('/tyrant/apply')
        expect(page.get_by_test_id('no-round')).to_be_visible()
        p.check('tyrant-no-round')
        p.goto('/tyrant')
        expect(page.get_by_test_id('no-round-banner')).to_be_visible()
        p.check('tyrant-home-no-round')
    finally:
        api.call('POST', '/api/admin/events/tyrant/start-new-round', {'name': f'Mobile e2e {RUN} {lang}'}, admin=True)


# ------------------------------------------------------------------ admin on a phone

@pytest.mark.parametrize('lang,locale', [('en', 'en-US'), ('ar', 'ar-SA')])
def test_admin_usable_on_phone(phone, api, base_url, lang, locale):
    ensure_tyrant_round(api)
    device = 'iPhone 13'
    page = phone(device, locale=locale)
    p = Phone(page, device, lang)
    ui.use_admin_token(page, base_url, api.token(), ui.admin_dashboard_url('ministry'))
    expect(page.get_by_test_id('round-select')).to_be_visible()
    p.check('admin-ministry-players', tappable=['round-select', 'tab-players', 'tab-assignments', 'tab-settings',
                                                'admin-event-ministry', 'admin-event-tyrant', 'start-new-round'])
    page.get_by_test_id('tab-settings').click()
    p.check('admin-ministry-settings')
    page.get_by_test_id('admin-event-tyrant').click()
    expect(page.get_by_test_id('admin-shell')).to_have_attribute('data-event', 'tyrant')
    page.wait_for_load_state('networkidle')
    p.check('admin-tyrant-players')
    page.get_by_test_id('tab-settings').click()
    p.check('admin-tyrant-settings')


def test_admin_tap_to_move_on_phone(phone, api, base_url):
    """The drag-and-drop board on a phone: tap the move icon, then "Move here" on an empty slot; it saves."""
    fid = fresh_fid()
    api.put_application(fid, f'Tap {RUN}', 'TAP', {
        'construction_speedups_days': 9, 'research_speedups_days': 0, 'troop_training_speedups_days': 0,
        'time_slots_by_day': {'construction': ['05:00'], 'research': [], 'troop': []}})
    device = 'iPhone 13'
    page = phone(device)
    p = Phone(page, device, 'en')
    ui.use_admin_token(page, base_url, api.token(), ui.admin_dashboard_url('ministry'))
    page.get_by_test_id('tab-assignments').click()
    page.get_by_test_id('assign-day-monday').click()
    card = page.get_by_test_id(f'card-{fid}')
    expect(card).to_be_visible()
    p.check('admin-assignments', tappable=['assign-day-monday', f'move-{fid}'])
    page.get_by_test_id(f'move-{fid}').click()
    expect(page.get_by_test_id('move-banner')).to_be_visible()
    empty = page.evaluate("""() => [...document.querySelectorAll('[data-testid^="slot-box-"]')]
        .find(b => !b.querySelector('[data-testid^="card-"]')).getAttribute('data-testid').slice('slot-box-'.length)""")
    target = page.get_by_test_id(f'move-here-{empty}')
    assert target.bounding_box()['height'] >= TAP
    p.shot('admin-assignments-picked')
    target.click()
    expect(page.get_by_test_id(f'slot-box-{empty}').get_by_test_id(f'card-{fid}')).to_be_visible()
    expect(page.get_by_test_id('move-banner')).to_have_count(0)
    page.wait_for_load_state('networkidle')
    # persisted (and sticky, as a manual move)
    page.reload()
    page.get_by_test_id('tab-assignments').click()
    page.get_by_test_id('assign-day-monday').click()
    moved = page.get_by_test_id(f'slot-box-{empty}').get_by_test_id(f'card-{fid}')
    expect(moved).to_be_visible()
    expect(moved.get_by_role('button', name=ui.en('admin:clickToUnlock'))).to_be_visible()
    # and back to Unassigned
    page.get_by_test_id(f'move-{fid}').click()
    page.get_by_test_id('move-here-unassigned').click()
    expect(page.get_by_test_id(f'slot-box-{empty}').get_by_test_id(f'card-{fid}')).to_have_count(0)
