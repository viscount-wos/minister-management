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
        # CSSOM, not an injected <style>: the site's CSP (style-src 'self') rightly blocks inline <style> tags
        page.evaluate("document.querySelectorAll('[data-testid=wizard-nav]')"
                      ".forEach(e => e.style.setProperty('position', 'static', 'important'))")
        page.screenshot(path=str(SHOTS / f'{slug(self.device)}-{self.lang}-{name}.png'), full_page=True)
        page.evaluate("document.querySelectorAll('[data-testid=wizard-nav]').forEach(e => e.style.removeProperty('position'))")

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
    # Minister still asks the furnace (only Tyrant dropped it, p2e): FC10..FC1 then 30..1
    opts = page.get_by_test_id('profile-furnace-level').locator('option').evaluate_all('os => os.map(o => o.value)')
    assert opts == [''] + [f'FC{n}' for n in range(10, 0, -1)] + [str(n) for n in range(30, 0, -1)], opts
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
        if picks[day]:
            # 'Times shown in <zone>': the zone is an LTR isolate (no bracket/number scramble in Arabic)
            note = page.get_by_test_id('times-shown-in')
            expect(note).to_contain_text(ui.tr(lang, 'ministry:form.timesShownIn'))
            assert note.locator('bdi[dir=ltr]').count() == 1
        p.check(f'minister-{n}-{day}', tappable=['wizard-back', 'wizard-next', 'wizard-timezone'])
        ui.next_step(page)
    ui.expect_step(page, ui.REVIEW_STEP)
    ui.expect_review_slots(page, picks)
    # review heading names the zone the times are shown in (was a fixed '(UTC)')
    heading = page.get_by_test_id('review-times-heading')
    expect(heading).to_contain_text(ui.tr(lang, 'ministry:form.step2Title'))
    assert 'UTC' not in heading.inner_text()
    # chips: '<local> (<utc> UTC)', each time an LTR isolate; local time first in reading order
    chip = page.get_by_test_id('review-slots-construction').locator('[data-slot="10:00"]')
    expect(chip.get_by_test_id('time-utc')).to_have_text('(10:00 UTC)')
    assert chip.get_by_test_id('time-utc').get_attribute('dir') == 'ltr'
    expect(chip.get_by_test_id('time-local')).to_have_text('19:00')        # Asia/Seoul = UTC+9
    local_x = chip.get_by_test_id('time-local').bounding_box()['x']
    utc_x = chip.get_by_test_id('time-utc').bounding_box()['x']
    assert (local_x > utc_x) if lang == 'ar' else (local_x < utc_x), (lang, local_x, utc_x)
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
    expect(page.get_by_test_id('furnace-level')).to_have_count(0)  # Tyrant does not ask the main furnace (p2e)
    page.get_by_test_id('power-millions').fill('123.4')
    page.get_by_test_id('gem-spend').fill('5000')
    p.check('tyrant-3-stats', tappable=['wizard-back', 'wizard-next', 'power-millions', 'gem-spend'])
    ui.next_step(page)
    # 4 troops: CAMP levels (FC10..FC1 only) + tier, all required
    expect(page.get_by_test_id('camp-hint')).to_have_text(ui.tr(lang, 'tyrant:step4.campHint'))
    for kind in ('infantry', 'lancer', 'marksman'):
        expect(page.locator(f'label[for=troop-{kind}-furnace]')).to_have_text(ui.tr(lang, f'tyrant:step4.camp.{kind}'))
        opts = page.get_by_test_id(f'troop-{kind}-furnace').locator('option').evaluate_all('os => os.map(o => o.value)')
        assert opts == ['', 'FC10', 'FC9', 'FC8', 'FC7', 'FC6', 'FC5', 'FC4', 'FC3', 'FC2', 'FC1']
    page.get_by_test_id('wizard-next').click()
    expect(page.get_by_test_id('form-error')).to_have_text(ui.tr(lang, 'tyrant:errors.campRequired'))
    for kind in ('infantry', 'lancer', 'marksman'):
        page.get_by_test_id(f'troop-{kind}-furnace').select_option('FC5')
        page.get_by_test_id(f'troop-{kind}-tier').select_option('10')
    p.check('tyrant-4-troops', tappable=['wizard-back', 'wizard-next'] + [f'troop-{k}-{f}' for k in ('infantry', 'lancer', 'marksman') for f in ('furnace', 'tier')])
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


# ------------------------------------------------------------------ SVS wizard NEW (v2.2.0)

def ensure_svs_round(api: ui.Api):
    status, res = api.call('GET', '/api/events/svs/current', ok=None)
    if status == 200 and res['settings']['hours'] == ['11:00', '12:00', '13:00', '14:00', '15:00']:
        return res
    _, res = api.call('POST', '/api/admin/events/svs/start-new-round',
                      {'name': f'SVS mobile {RUN}', 'settings': {'battle_start': '11:00', 'battle_hours': 5}}, admin=True)
    return res['round']


@pytest.mark.parametrize('device', ['iPhone 13', 'narrow-360'])
@pytest.mark.parametrize('lang,locale', [('en', 'en-US'), ('ar', 'ar-SA')])
def test_svs_wizard_new_on_phone(phone, api, device, lang, locale):
    ensure_svs_round(api)
    page = phone(device, locale=locale, timezone_id='Asia/Seoul')     # local time = UTC+9
    p = Phone(page, device, lang)
    fid = fresh_fid()
    p.goto('/svs')
    p.check('svs-home', tappable=['svs-apply-tile', 'nav-home'])
    p.goto('/svs/apply')
    ui.expect_step(page, 1)
    p.expect_steps_fit()
    assert page.get_by_test_id('fid-input').get_attribute('inputmode') == 'numeric'
    expect(page.get_by_test_id('fid-help')).to_be_visible()
    p.check('svs-1-fid', tappable=['wizard-back', 'wizard-next'])
    page.get_by_test_id('fid-input').fill(fid)
    page.get_by_test_id('wizard-next').click()
    expect(page.get_by_test_id('application-heading')).to_have_attribute('data-mode', 'new')
    page.get_by_test_id('profile-game-name').fill(f'SVS {lang} {RUN}')
    page.get_by_test_id('profile-alliance').fill('svm')
    p.expect_nav_in_view()
    p.check('svs-1-player', tappable=['wizard-back', 'wizard-next', 'change-fid'])
    ui.next_step(page)
    # 2 hours: game time (UTC) big, local time (Seoul) small, 5 chips 11:00-15:00
    expect(page.get_by_test_id('utc-note')).to_have_text(ui.tr(lang, 'svs:step2.utcNote'))
    chip = page.get_by_test_id('hour-11:00')
    expect(chip.get_by_test_id('hour-utc')).to_have_text('11:00 UTC')
    expect(chip.get_by_test_id('hour-local')).to_have_text('20:00')
    assert chip.get_by_test_id('hour-utc').get_attribute('dir') == 'ltr'
    for h in ('11:00', '12:00', '13:00', '14:00', '15:00'):
        b = page.get_by_test_id(f'hour-{h}').bounding_box()
        assert b['height'] >= TAP and b['width'] >= TAP and b['x'] + b['width'] <= p.width
    page.get_by_test_id('hour-12:00').click()
    page.get_by_test_id('hour-13:00').click()
    expect(page.get_by_test_id('hour-13:00')).to_have_attribute('aria-pressed', 'true')
    p.expect_nav_in_view()
    p.check('svs-2-hours', tappable=['wizard-back', 'wizard-next', 'select-all-hours'])
    ui.next_step(page)
    # 3 troops: FC camps, T11 / T10 buttons only
    for kind in ('infantry', 'lancer', 'marksman'):
        assert page.get_by_test_id(f'troop-{kind}-tier').locator('[role=radio]').all_inner_texts() == ['T11', 'T10']
        page.get_by_test_id(f'troop-{kind}-furnace').select_option('FC9')
        page.get_by_test_id(f'tier-{kind}-11').click()
    p.check('svs-3-troops', tappable=['wizard-back', 'wizard-next'] + [f'troop-{k}-furnace' for k in ('infantry', 'lancer', 'marksman')]
            + [f'tier-{k}-{n}' for k in ('infantry', 'lancer', 'marksman') for n in (10, 11)])
    ui.next_step(page)
    # 4 Discord voice chat (no role question: the planner assigns leaders): big radio cards
    page.get_by_test_id('vc-yes').click()
    expect(page.get_by_test_id('vc-yes')).to_have_attribute('aria-checked', 'true')
    p.check('svs-4-vc', tappable=['wizard-back', 'wizard-next', 'vc-yes', 'vc-no'])
    ui.next_step(page)
    p.expect_nav_in_view()
    p.check('svs-5-review', tappable=['wizard-back', 'wizard-submit', 'review-edit-1', 'review-edit-2'])
    ui.submit(page)
    p.check('svs-success', tappable=['reopen-application'])
    _, app = api.call('GET', f'/api/events/svs/current/application/{fid}')
    assert app['answers'] == {'hours': ['12:00', '13:00'], 'discord_vc': True, 'language': lang}


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
    expect(page.get_by_test_id('windows-editor')).to_be_visible()
    # 16px / 44px time inputs (no iOS zoom), rush checkboxes are whole-row tap targets
    for tid in ('window-start-0', 'window-end-0'):
        assert page.get_by_test_id(tid).bounding_box()['height'] >= TAP
    assert page.get_by_test_id('window-rush-0').locator('xpath=..').bounding_box()['height'] >= TAP
    assert page.get_by_test_id('window-rush-0').bounding_box()['width'] >= 20
    p.check('admin-tyrant-settings')


def seed_tyrant_filter_players(api: ui.Api) -> tuple[str, str]:
    best, other = fresh_fid(), fresh_fid()
    full = lambda camp, tier: {k: {'furnace_level': camp, 'tier': tier} for k in ('infantry', 'lancer', 'marksman')}  # noqa: E731
    for fid, troops in ((best, full('FC10', 11)), (other, full('FC8', 10))):
        api.call('PUT', f'/api/events/tyrant/current/application/{fid}', {
            'profile': {'game_name': f'Mob {fid}', 'alliance': 'MOB', 'furnace_level': 'FC10', 'troops': troops},
            'answers': {'availability': ['w1'], 'gem_spend': 100}})
    return best, other


@pytest.mark.parametrize('lang,locale', [('en', 'en-US'), ('ar', 'ar-SA')])
def test_admin_tyrant_filters_on_phone(phone, api, base_url, lang, locale):
    """Chips, bar filters, pills and Clear filters on a phone: 44px targets, no sideways scroll, RTL."""
    ensure_tyrant_round(api)
    best, other = seed_tyrant_filter_players(api)
    device = 'iPhone 13'
    page = phone(device, locale=locale)
    p = Phone(page, device, lang)
    ui.use_admin_token(page, base_url, api.token(), ui.admin_dashboard_url('tyrant'))
    expect(page.get_by_test_id('tyrant-table')).to_be_visible()
    page.wait_for_load_state('networkidle')
    expect(page.get_by_test_id('stat-gems')).to_have_count(0)
    # no main furnace in the Tyrant admin (p2e): no column / badge / sort / 'Furnace at least' filter
    for gone in ('furnace-badge', 'sort-furnace', 'furnace-filter'):
        expect(page.get_by_test_id(gone)).to_have_count(0)
    total = int(page.get_by_test_id('stat-total-value').inner_text())
    chips = ['chip-infantry-camp-FC10', 'chip-infantry-tier-T11', 'filter-troop', 'filter-min-camp', 'filter-min-tier',
             'alliance-filter', 'windows-filter', 'filter-more', 'sort-strength', 'sort-name']
    p.check('admin-tyrant-filters', tappable=chips)
    # tap a chip: table + summary narrow, chip highlighted, pill
    page.get_by_test_id('chip-infantry-camp-FC8').click()
    expect(page.get_by_test_id(f'player-row-{other}')).to_be_visible()
    expect(page.get_by_test_id(f'player-row-{best}')).to_have_count(0)
    expect(page.get_by_test_id('chip-infantry-camp-FC8')).to_have_attribute('aria-pressed', 'true')
    expect(page.get_by_test_id('filter-pill-infantry_camp')).to_be_visible()
    assert int(page.get_by_test_id('stat-total-value').inner_text()) < total
    p.check('admin-tyrant-chip', tappable=['filter-pill-infantry_camp', 'clear-filters'])
    page.get_by_test_id('filter-pill-infantry_camp').click()
    expect(page.get_by_test_id('stat-total-value')).to_have_text(str(total))
    # the bar: All three, at least FC10, T11 only (URL survives a reload)
    page.get_by_test_id('filter-min-camp').select_option('FC10')
    page.get_by_test_id('filter-min-tier').select_option('11')
    expect(page.get_by_test_id(f'player-row-{best}')).to_be_visible()
    expect(page.get_by_test_id(f'player-row-{other}')).to_have_count(0)
    page.reload()
    page.wait_for_load_state('networkidle')
    expect(page.get_by_test_id('filter-pill-min_camp')).to_be_visible()
    expect(page.get_by_test_id(f'player-row-{other}')).to_have_count(0)
    p.check('admin-tyrant-fc10-t11', tappable=['filter-pill-min_camp', 'filter-pill-min_tier', 'clear-filters'])
    page.get_by_test_id('clear-filters').click()
    expect(page.get_by_test_id('stat-total-value')).to_have_text(str(total))
    # More filters fit on a phone too
    page.get_by_test_id('filter-more').click()
    p.check('admin-tyrant-more-filters', tappable=['filter-vc', 'filter-days', 'roles-filter', 'filter-min-power'])


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


def test_assignment_wants_in_display_timezone(phone, api, base_url):
    """The 'Wants:' line under an unassigned player follows the admin's display timezone, like the slots."""
    fid = fresh_fid()
    api.put_application(fid, f'Wants {RUN}', 'WNT', {
        'construction_speedups_days': 1, 'research_speedups_days': 0, 'troop_training_speedups_days': 0,
        'time_slots_by_day': {'construction': ['05:00'], 'research': [], 'troop': []}})
    page = phone('iPhone 13', timezone_id='Asia/Seoul')
    ui.use_admin_token(page, base_url, api.token(), ui.admin_dashboard_url('ministry'))
    page.get_by_test_id('tab-assignments').click()
    page.get_by_test_id('assign-day-monday').click()
    wants = page.get_by_test_id(f'wants-{fid}')
    expect(wants).to_contain_text('14:00')                 # 05:00 UTC in Seoul (UTC+9)
    expect(wants).not_to_contain_text('05:00')
    assert wants.locator('[data-utc="05:00"]').count() == 1
