"""Frost Dragon Tyrant e2e: the 6-step wizard (tyrantpoll's flow) on rounds + profiles, admin, i18n/RTL.

Runs in file order with shared state (one FID set per run). UI strings come from the locale files
(ui.tr), controls from data-testid. Admin: one UI login per test that needs it (failures are what the
login throttle counts; these logins all succeed).
"""
from __future__ import annotations

import csv
import io
import re
import secrets
import time

import pytest
from playwright.sync_api import Page, expect

import ui

RUN = time.strftime('%H%M%S')
FID_A = str(70_000_000 + secrets.randbelow(9_999_999))   # English NEW -> EDIT -> new round + last answers
FID_AR = str(80_000_000 + secrets.randbelow(9_999_999))  # Arabic
STEPS = 6


def tr(key: str, lang: str = 'en', **v) -> str:
    return ui.tr(lang, key, **v)


# ------------------------------------------------------------------ helpers

class TApi:
    def __init__(self, api: ui.Api):
        self.api = api

    def current(self):
        status, res = self.api.call('GET', '/api/events/tyrant/current', ok=None)
        return res if status == 200 else None

    def start(self, name: str):
        _, res = self.api.call('POST', '/api/admin/events/tyrant/start-new-round', {'name': name}, admin=True)
        return res['round']

    def application(self, fid: str):
        status, res = self.api.call('GET', f'/api/events/tyrant/current/application/{fid}', ok=None)
        return res if status == 200 else None

    def profile(self, fid: str):
        _, res = self.api.call('GET', f'/api/profile/{fid}')
        return res

    def update_round(self, rid: int, **body):
        _, res = self.api.call('PUT', f'/api/admin/rounds/{rid}', body, admin=True)
        return res


@pytest.fixture(scope='module')
def tapi(api) -> TApi:
    return TApi(api)


@pytest.fixture(scope='module', autouse=True)
def tyrant_round(tapi):
    """A fresh tyrant round with tyrantpoll's default windows for this module."""
    rnd = tapi.start(f'FDT e2e {RUN}')
    if [w['id'] for w in rnd['settings']['windows']] != ['w1', 'w2', 'w3', 'w4', 'w5']:
        rnd = tapi.update_round(rnd['id'], settings={'windows': [
            {'id': 'w1', 'start': '11:01', 'end': '11:15', 'rush': True},
            {'id': 'w2', 'start': '11:15', 'end': '13:00'}, {'id': 'w3', 'start': '13:00', 'end': '15:00'},
            {'id': 'w4', 'start': '15:00', 'end': '16:30'}, {'id': 'w5', 'start': '16:30', 'end': '18:00'}]})
    return rnd


def open_wizard(page: Page, base_url: str, fid: str, lang: str | None = None) -> str:
    page.goto(base_url + '/tyrant/apply')
    page.wait_for_load_state('networkidle')
    if lang:
        ui.switch_language(page, lang)
    expect(page.get_by_test_id('wizard')).to_have_attribute('data-mode', 'lookup')
    page.get_by_test_id('fid-input').fill(fid)
    page.get_by_test_id('wizard-next').click()
    landed = page.locator('[data-testid="wizard"]:not([data-mode="lookup"]), [data-testid="applications-closed"]')
    expect(landed.first).to_be_visible()
    page.wait_for_load_state('networkidle')
    if page.get_by_test_id('applications-closed').count():
        return 'closed'
    return page.get_by_test_id('wizard').get_attribute('data-mode')


def at_step(page: Page, n: int) -> None:
    expect(page.get_by_test_id('wizard-steps')).to_have_attribute('data-step', str(n))
    expect(page.get_by_test_id(f'wizard-step-{n}')).to_be_visible()


def next_step(page: Page, n_after: int) -> None:
    page.get_by_test_id('wizard-next').click()
    at_step(page, n_after)
    page.wait_for_timeout(300)  # let the 0.2 s colour transition finish before screenshots


def check(page: Page, testid: str, on: bool = True) -> None:
    box = page.get_by_test_id(testid)
    if box.is_checked() != on:
        box.click()
    (expect(box).to_be_checked() if on else expect(box).not_to_be_checked())


def fill_all_steps(page: Page, *, name: str, alliance: str, discord: str, windows: list[str], vc: bool,
                   furnace: str, power: str, gems: str, troops: dict, roles: list[str], shot=None, tag='') -> None:
    """From step 1 (profile loaded) to the review step."""
    at_step(page, 1)
    page.get_by_test_id('profile-game-name').fill(name)
    page.get_by_test_id('profile-discord-id').fill(discord)
    page.get_by_test_id('profile-alliance').fill(alliance)
    shot and shot(f'{tag}step1')
    next_step(page, 2)
    for w in ['w1', 'w2', 'w3', 'w4', 'w5']:
        check(page, f'window-{w}', w in windows)
    check(page, 'discord-vc', vc)
    shot and shot(f'{tag}step2')
    next_step(page, 3)
    page.get_by_test_id('furnace-level').select_option(furnace)
    page.get_by_test_id('power-millions').fill(power)
    page.get_by_test_id('gem-spend').fill(gems)
    shot and shot(f'{tag}step3')
    next_step(page, 4)
    for kind, (fl, tier) in troops.items():
        page.get_by_test_id(f'troop-{kind}-furnace').select_option(fl)
        page.get_by_test_id(f'troop-{kind}-tier').select_option(tier)
    shot and shot(f'{tag}step4')
    next_step(page, 5)
    for r in ['rally_leader', 'joiner', 'gathering', 'battle_mgmt', 'event_prep']:
        check(page, f'role-{r}', r in roles)
    shot and shot(f'{tag}step5')
    next_step(page, 6)


# ------------------------------------------------------------------ player flow

def test_home_tile_is_live_and_landing_page(page: Page, base_url, shot, tyrant_round):
    ui.go(page, base_url, 'home')
    tile = page.get_by_test_id('event-tile-tyrant')
    expect(tile).to_contain_text(tr('tyrant:name'))
    expect(tile).to_contain_text(tr('common:home.status.open'))
    tile.click()
    page.wait_for_url('**/tyrant')
    expect(page.get_by_test_id('current-round')).to_contain_text(tyrant_round['name'])
    shot('landing')
    page.get_by_test_id('tyrant-apply-tile').click()
    page.wait_for_url('**/tyrant/apply')
    expect(page.get_by_test_id('application-heading')).to_have_text(tr('tyrant:apply.title'))
    expect(page.get_by_test_id('round-name')).to_have_text(tyrant_round['name'])
    expect(page.get_by_test_id('wizard-step-indicator-1')).to_have_attribute('data-state', 'current')
    assert page.locator('[data-testid^="wizard-step-indicator-"]').count() == STEPS
    # FID must be digits
    page.get_by_test_id('fid-input').fill('12ab')
    page.get_by_test_id('wizard-next').click()
    expect(page.get_by_test_id('form-error')).to_have_text(tr('profile:fidDigitsOnly'))
    shot('fid-lookup')


def test_full_wizard_new_in_english(page: Page, base_url, shot, tapi, tyrant_round):
    assert open_wizard(page, base_url, FID_A) == 'new'
    expect(page.get_by_test_id('application-heading')).to_have_text(tr('tyrant:apply.newFor', round=tyrant_round['name']))
    expect(page.get_by_test_id('profile-status')).to_have_text(tr('profile:newProfile'))
    expect(page.get_by_test_id('use-last-answers')).to_have_count(0)  # first-timer
    # step 1 checks (tyrantpoll: name, FID, alliance required)
    page.get_by_test_id('wizard-next').click()
    expect(page.get_by_test_id('form-error')).to_have_text(tr('ministry:form.required'))
    page.get_by_test_id('profile-game-name').fill('Tyra')
    page.get_by_test_id('wizard-next').click()
    expect(page.get_by_test_id('form-error')).to_have_text(tr('profile:allianceRequired'))
    page.get_by_test_id('profile-alliance').fill('woo')
    expect(page.get_by_test_id('profile-alliance')).to_have_value('WOO')
    # step 2: tyrantpoll's windows, labels and "Select All"
    page.get_by_test_id('profile-discord-id').fill('tyra#0001')
    next_step(page, 2)
    expect(page.get_by_test_id('window-w1').locator('xpath=..')).to_contain_text(tr('tyrant:step2.openingRush'))
    expect(page.get_by_test_id('window-w1').locator('xpath=..')).to_contain_text('11:01–11:15')
    expect(page.get_by_test_id('utc-note')).to_have_text(tr('tyrant:step2.utcNote'))
    check(page, 'select-all-windows')
    for w in ['w1', 'w2', 'w3', 'w4', 'w5']:
        expect(page.get_by_test_id(f'window-{w}')).to_be_checked()
    check(page, 'window-w5', False)
    expect(page.get_by_test_id('select-all-windows')).not_to_be_checked()
    check(page, 'select-all-windows', False)
    page.get_by_test_id('wizard-back').click()
    at_step(page, 1)
    fill_all_steps(page, name='Tyra', alliance='woo', discord='tyra#0001', windows=['w1', 'w3'], vc=True,
                   furnace='FC8', power='410.5', gems='10000',
                   troops={'infantry': ('FC5', '10'), 'lancer': ('30', '9'), 'marksman': ('', '11')},
                   roles=['rally_leader', 'joiner'], shot=shot, tag='en-')
    expect(page.get_by_test_id('review-furnace-level')).to_contain_text('FC8')
    expect(page.get_by_test_id('review-troop-infantry')).to_contain_text('FC5 / T10')
    expect(page.get_by_test_id('review-troop-marksman')).to_contain_text('— / T11')
    expect(page.get_by_test_id('review-alliance')).to_contain_text('WOO')
    shot('en-step6-review')
    # Edit per section (tyrantpoll's review) -> back to that step
    page.get_by_test_id('review-edit-3').click()
    at_step(page, 3)
    # furnace dropdown order: empty, FC10..FC1, then 30..1
    values = page.get_by_test_id('furnace-level').locator('option').evaluate_all('os => os.map(o => o.value)')
    assert values[:3] == ['', 'FC10', 'FC9'] and values[10:12] == ['FC1', '30'] and values[-1] == '1' and len(values) == 41
    page.get_by_test_id('gem-spend').fill('12000')
    for n in (4, 5, 6):
        next_step(page, n)
    expect(page.get_by_test_id('review-gem-spend')).to_contain_text('12000')
    expect(page.get_by_test_id('wizard-submit')).to_have_attribute('data-mode', 'new')
    page.get_by_test_id('wizard-submit').click()
    expect(page.get_by_test_id('save-success')).to_contain_text(tr('tyrant:apply.savedNew', round=tyrant_round['name']))
    shot('en-saved')

    app = tapi.application(FID_A)
    assert app['answers'] == {'availability': ['w1', 'w3'], 'discord_vc': True, 'gem_spend': 12000,
                              'roles': ['rally_leader', 'joiner'], 'language': 'en'}
    prof = tapi.profile(FID_A)
    assert prof['game_name'] == 'Tyra' and prof['alliance'] == 'WOO' and prof['discord_id'] == 'tyra#0001'
    assert prof['furnace_level'] == 'FC8' and prof['power'] == 410_500_000
    assert prof['troops'] == {'infantry': {'furnace_level': 'FC5', 'tier': 10},
                              'lancer': {'furnace_level': '30', 'tier': 9},
                              'marksman': {'furnace_level': None, 'tier': 11}}


def test_edit_via_fid(page: Page, base_url, shot, tapi, tyrant_round):
    assert open_wizard(page, base_url, FID_A) == 'edit'
    expect(page.get_by_test_id('application-heading')).to_have_text(tr('tyrant:apply.editFor', round=tyrant_round['name']))
    expect(page.get_by_test_id('profile-status')).to_have_text(tr('profile:prefilled'))
    expect(page.get_by_test_id('profile-game-name')).to_have_value('Tyra')
    expect(page.get_by_test_id('profile-discord-id')).to_have_value('tyra#0001')
    expect(page.get_by_test_id('use-last-answers')).to_have_count(0)  # edit mode
    shot('edit-step1')
    next_step(page, 2)
    expect(page.get_by_test_id('window-w1')).to_be_checked()
    expect(page.get_by_test_id('window-w2')).not_to_be_checked()
    expect(page.get_by_test_id('window-w3')).to_be_checked()
    expect(page.get_by_test_id('discord-vc')).to_be_checked()
    next_step(page, 3)
    expect(page.get_by_test_id('furnace-level')).to_have_value('FC8')
    expect(page.get_by_test_id('power-millions')).to_have_value('410.5')
    expect(page.get_by_test_id('gem-spend')).to_have_value('12000')
    next_step(page, 4)
    expect(page.get_by_test_id('troop-lancer-furnace')).to_have_value('30')
    expect(page.get_by_test_id('troop-infantry-tier')).to_have_value('10')
    next_step(page, 5)
    expect(page.get_by_test_id('role-rally_leader')).to_be_checked()
    check(page, 'role-event_prep')
    next_step(page, 6)
    expect(page.get_by_test_id('wizard-submit')).to_have_text(tr('ministry:form.update'))
    page.get_by_test_id('wizard-submit').click()
    expect(page.get_by_test_id('save-success')).to_contain_text(tr('tyrant:apply.savedEdit', round=tyrant_round['name']))
    assert tapi.application(FID_A)['answers']['roles'] == ['rally_leader', 'joiner', 'event_prep']
    # "Not you? Use a different FID"
    page.get_by_test_id('reopen-application').click()
    expect(page.get_by_test_id('wizard')).to_have_attribute('data-mode', 'edit')
    page.get_by_test_id('change-fid').click()
    expect(page.get_by_test_id('wizard')).to_have_attribute('data-mode', 'lookup')


def test_arabic_rtl_wizard(page: Page, base_url, shot, tapi, tyrant_round):
    assert open_wizard(page, base_url, FID_AR, lang='ar') == 'new'
    assert page.evaluate('document.documentElement.dir') == 'rtl'
    expect(page.get_by_test_id('application-heading')).to_have_text(
        tr('tyrant:apply.newFor', 'ar', round=tyrant_round['name']))
    # step indicator follows the page direction (as the ministry wizard): step 1 on the right
    one = page.get_by_test_id('wizard-step-indicator-1').bounding_box()
    six = page.get_by_test_id(f'wizard-step-indicator-{STEPS}').bounding_box()
    assert one['x'] > six['x']
    expect(page.get_by_test_id('wizard-step-title')).to_have_text(tr('tyrant:step1.title', 'ar'))
    fill_all_steps(page, name='طاغية', alliance='ARB', discord='', windows=['w2', 'w4'], vc=False,
                   furnace='FC3', power='95', gems='', troops={'infantry': ('FC3', '8')}, roles=['gathering'],
                   shot=shot, tag='ar-')
    expect(page.get_by_test_id('wizard-step-title')).to_have_text(tr('tyrant:step6.title', 'ar'))
    expect(page.get_by_test_id('review-furnace-level')).to_contain_text('FC3')
    # Back/Next arrows mirrored, buttons in Arabic
    expect(page.get_by_test_id('wizard-back')).to_have_text(tr('ministry:form.back', 'ar'))
    shot('ar-step6-review')
    page.get_by_test_id('wizard-submit').click()
    expect(page.get_by_test_id('save-success')).to_contain_text(tr('tyrant:apply.savedTitle', 'ar'))
    assert page.evaluate('document.documentElement.dir') == 'rtl'
    shot('ar-saved')
    app = tapi.application(FID_AR)
    assert app['answers']['availability'] == ['w2', 'w4'] and app['answers']['language'] == 'ar'
    assert tapi.profile(FID_AR)['furnace_level'] == 'FC3'
    ui.switch_language(page, 'en')


def test_no_raw_keys_every_step_9_languages(page: Page, base_url, shot):
    bad = {}
    page.goto(base_url + '/tyrant')
    page.wait_for_load_state('networkidle')
    bad.update({f'landing-{k}': v for k, v in ui.check_all_languages(page, 'tyrant-landing', shot).items()})
    assert open_wizard(page, base_url, FID_A) == 'edit'
    for n in range(1, STEPS + 1):
        at_step(page, n)
        found = ui.check_all_languages(page, f'tyrant-step{n}', shot)
        bad.update({f'step{n}-{k}': v for k, v in found.items()})
        # every language really changes the step title
        titles = set()
        for lang in ('en', 'ar', 'ko', 'pl'):
            ui.switch_language(page, lang)
            titles.add(page.get_by_test_id('wizard-step-title').inner_text())
        ui.switch_language(page, 'en')
        assert len(titles) == 4, titles
        if n < STEPS:
            next_step(page, n + 1)
    assert not bad, bad


def test_shared_profile_furnace_dropdown_in_ministry(page: Page, base_url, shot):
    """The profile is shared: the ministry wizard shows the furnace code saved by Tyrant, in the same dropdown."""
    page.goto(base_url + '/ministry/apply')
    page.wait_for_load_state('networkidle')
    page.get_by_test_id('fid-input').fill(FID_A)
    page.get_by_test_id('wizard-next').click()
    sel = page.get_by_test_id('profile-furnace-level')
    expect(sel).to_have_value('FC8')
    assert sel.evaluate('el => el.tagName') == 'SELECT'
    values = sel.locator('option').evaluate_all('os => os.map(o => o.value)')
    assert values[:2] == ['', 'FC10'] and values[-1] == '1' and len(values) == 41
    ui.switch_language(page, 'ar')
    labels = sel.locator('option').evaluate_all('os => os.map(o => o.textContent)')
    assert labels[0] == tr('common:furnace.select', 'ar') and labels[11] == tr('common:furnace.level', 'ar', n='30')
    groups = sel.locator('optgroup').evaluate_all('gs => gs.map(g => g.label)')
    assert groups == [tr('common:furnace.fireCrystal', 'ar'), tr('common:furnace.preFc', 'ar')]
    sel.select_option('25')
    expect(sel).to_have_value('25')
    shot('ministry-furnace-ar')
    ui.switch_language(page, 'en')


def test_closing_time_states(page: Page, base_url, shot, tapi, tyrant_round):
    tapi.update_round(tyrant_round['id'], closing_time='2000-01-01T00:00:00Z')
    try:
        new_fid = str(60_000_000 + secrets.randbelow(9_999_999))
        assert open_wizard(page, base_url, new_fid) == 'closed'
        expect(page.get_by_test_id('applications-closed')).to_contain_text(tr('tyrant:apply.closedTitle'))
        shot('closed-new')
        assert open_wizard(page, base_url, FID_A) == 'edit'
        expect(page.get_by_test_id('closing-note')).to_have_text(tr('tyrant:apply.closedButEditable'))
    finally:
        tapi.update_round(tyrant_round['id'], closing_time=None)


# ------------------------------------------------------------------ admin

def _admin_tyrant(page: Page, base_url: str, password: str) -> None:
    ui.admin_login(page, base_url, password)
    page.get_by_test_id('admin-event-tyrant').click()
    expect(page.get_by_test_id('tyrant-admin')).to_be_visible()
    page.wait_for_load_state('networkidle')


def test_admin_stats_filter_sort_export_settings(page: Page, base_url, admin_password, shot, tapi, tyrant_round):
    _admin_tyrant(page, base_url, admin_password)
    expect(page.get_by_test_id('admin-event-tyrant')).to_have_attribute('aria-selected', 'true')
    expect(page.get_by_test_id('round-select')).to_have_value(str(tyrant_round['id']))
    expect(page.get_by_test_id('stat-total-value')).to_have_text('2')
    expect(page.get_by_test_id('stat-opening-rush-value')).to_have_text('1')
    expect(page.get_by_test_id('stat-discord-vc-value')).to_have_text('1')
    expect(page.get_by_test_id('stat-alliances-value')).to_have_text('2')
    expect(page.get_by_test_id('by-window-w1')).to_have_attribute('data-count', '1')
    expect(page.get_by_test_id('by-role-gathering')).to_have_attribute('data-count', '1')
    expect(page.get_by_test_id(f'player-row-{FID_A}').get_by_test_id('furnace-badge')).to_have_text('FC8')
    shot('admin-tyrant')
    # search, alliance filter, furnace filter, sort
    page.get_by_test_id('tyrant-search').fill('tyra#')
    expect(page.locator('[data-testid^="player-row-"]')).to_have_count(1)
    page.get_by_test_id('tyrant-search').fill('')
    expect(page.locator('[data-testid^="player-row-"]')).to_have_count(2)
    page.get_by_test_id('alliance-filter').select_option('ARB')
    expect(page.locator('[data-testid^="player-row-"]')).to_have_count(1)
    expect(page.get_by_test_id(f'player-row-{FID_AR}')).to_be_visible()
    expect(page.get_by_test_id('stat-total-value')).to_have_text('1')
    page.get_by_test_id('alliance-filter').select_option('')
    page.get_by_test_id('furnace-filter').select_option('FC5')
    expect(page.locator('[data-testid^="player-row-"]')).to_have_count(1)
    expect(page.get_by_test_id(f'player-row-{FID_A}')).to_be_visible()
    page.get_by_test_id('furnace-filter').select_option('')
    page.get_by_test_id('sort-furnace').click()
    expect(page.locator('[data-testid^="player-row-"]').first).to_have_attribute('data-testid', f'player-row-{FID_A}')
    page.get_by_test_id('sort-furnace').click()
    expect(page.locator('[data-testid^="player-row-"]').first).to_have_attribute('data-testid', f'player-row-{FID_AR}')
    # exports
    with page.expect_download() as dl:
        page.get_by_test_id('export-csv').click()
    text = open(dl.value.path(), encoding='utf-8-sig').read()
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0][:4] == ['FID', 'In-Game Name', 'Alliance', 'Discord ID'] and len(rows) == 3
    assert dl.value.suggested_filename.endswith('.csv')
    with page.expect_download() as dl:
        page.get_by_test_id('export-excel').click()
    assert dl.value.suggested_filename.endswith('.xlsx') and open(dl.value.path(), 'rb').read(2) == b'PK'
    # 9 languages on the admin view
    bad = ui.check_all_languages(page, 'tyrant-admin', shot)
    # settings: windows editor + closing time
    page.get_by_test_id('tab-settings').click()
    expect(page.get_by_test_id('windows-editor')).to_be_visible()
    page.get_by_test_id('window-add').click()
    page.get_by_test_id('window-start-5').fill('18:00')
    page.get_by_test_id('window-end-5').fill('19:30')
    shot('admin-settings')
    bad.update(ui.check_all_languages(page, 'tyrant-admin-settings', shot))
    page.get_by_test_id('save-windows').click()
    expect(page.get_by_test_id('settings-saved')).to_be_visible()
    windows = tapi.current()['settings']['windows']
    assert [w['id'] for w in windows] == ['w1', 'w2', 'w3', 'w4', 'w5', 'w6'] and windows[-1]['end'] == '19:30'
    page.get_by_test_id('closing-time').fill('2099-01-01T12:00')
    page.get_by_test_id('save-closing-time').click()
    expect(page.get_by_test_id('closing-time-status')).not_to_have_text(tr('admin:noClosingTime'))
    assert tapi.current()['closing_time'].startswith('2099-01-01')
    page.get_by_test_id('clear-closing-time').click()
    expect(page.get_by_test_id('closing-time-status')).to_have_text(tr('admin:noClosingTime'))
    assert not bad, bad
    # delete (tyrantpoll had delete) on a throwaway player
    throwaway = str(50_000_000 + secrets.randbelow(9_999_999))
    tapi.api.call('PUT', f'/api/events/tyrant/current/application/{throwaway}',
                  {'profile': {'game_name': 'Gone', 'alliance': 'DEL'}, 'answers': {}})
    page.get_by_test_id('tab-players').click()
    page.reload()
    page.wait_for_load_state('networkidle')
    page.get_by_test_id('admin-event-tyrant').wait_for()
    page.on('dialog', lambda d: d.accept())
    page.get_by_test_id(f'delete-{throwaway}').click()
    expect(page.get_by_test_id(f'player-row-{throwaway}')).to_have_count(0)
    assert tapi.application(throwaway) is None


def test_start_new_round_then_use_last_answers(page: Page, base_url, admin_password, shot, tapi, tyrant_round):
    _admin_tyrant(page, base_url, admin_password)
    page.get_by_test_id('start-new-round').click()
    dialog = page.get_by_test_id('new-round-dialog')
    expect(dialog).to_be_visible()
    expect(page.get_by_test_id('new-round-name')).to_have_value(
        re.compile('^' + re.escape(tr('tyrant:admin.defaultRoundName', date='').strip())))
    name = f'FDT e2e next {RUN}'
    page.get_by_test_id('new-round-name').fill(name)
    page.get_by_test_id('confirm-new-round').click()
    expect(dialog).to_have_count(0)
    expect(page.get_by_test_id('round-status')).to_have_attribute('data-status', 'open')
    expect(page.get_by_test_id('stat-total-value')).to_have_text('0')
    new_round = tapi.current()
    assert new_round['name'] == name and new_round['id'] != tyrant_round['id']
    assert [w['id'] for w in new_round['settings']['windows']][-1] == 'w6'  # windows carried over

    # same FID: NEW mode for the new round, profile pre-filled, answers blank, "Use my last answers"
    assert open_wizard(page, base_url, FID_A) == 'new'
    expect(page.get_by_test_id('application-heading')).to_have_text(tr('tyrant:apply.newFor', round=name))
    expect(page.get_by_test_id('profile-game-name')).to_have_value('Tyra')
    expect(page.get_by_test_id('use-last-answers')).to_be_visible()
    expect(page.get_by_test_id('last-answers')).to_contain_text(tyrant_round['name'])
    shot('last-answers-offer')
    next_step(page, 2)
    expect(page.get_by_test_id('window-w1')).not_to_be_checked()  # blank round answers
    page.get_by_test_id('wizard-back').click()
    at_step(page, 1)
    page.get_by_test_id('use-last-answers').click()
    expect(page.get_by_test_id('last-answers-applied')).to_contain_text(tyrant_round['name'])
    bad = ui.check_all_languages(page, 'tyrant-last-answers', shot)
    assert not bad, bad
    next_step(page, 2)
    expect(page.get_by_test_id('window-w1')).to_be_checked()
    expect(page.get_by_test_id('window-w3')).to_be_checked()
    expect(page.get_by_test_id('discord-vc')).to_be_checked()
    next_step(page, 3)
    expect(page.get_by_test_id('gem-spend')).to_have_value('12000')
    expect(page.get_by_test_id('furnace-level')).to_have_value('FC8')  # profile
    for n in (4, 5, 6):
        next_step(page, n)
    page.get_by_test_id('wizard-submit').click()
    expect(page.get_by_test_id('save-success')).to_contain_text(tr('tyrant:apply.savedNew', round=name))
    app = tapi.application(FID_A)
    assert app['round_id'] == new_round['id'] and app['answers']['roles'] == ['rally_leader', 'joiner', 'event_prep']
    assert app['answers']['availability'] == ['w1', 'w3']
