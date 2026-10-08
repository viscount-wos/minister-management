"""SVS e2e (v2.2.0): the 5-step phone-first sign-up wizard on desktop (en + ar), hours from the round setting,
T11/T10 only, prefill both ways with Frost Dragon Tyrant (shared profile), closed-round behaviour, the SVS admin
(stats, clickable bars and chips, URL filters, exports, settings), the Heroes view + state hero generation, and admin
"Add player" in all three events. Phones: test_mobile.py::test_svs_wizard_new_on_phone.

Own SVS round per module (default settings 11:00 UTC x 5 hours). Players seeded through the public API.
"""
from __future__ import annotations

import csv
import io
import secrets
import time

import pytest
from playwright.sync_api import Page, expect

import ui

RUN = time.strftime('%H%M%S')
BASE = 52_000_000 + secrets.randbelow(900_000)
FID_EN, FID_AR, FID_PREFILL, FID_LATE = (str(BASE + i) for i in range(4))
F_CALL, F_JOIN, F_WEAK = (str(BASE + 10 + i) for i in range(3))
DEFAULT_HOURS = ['11:00', '12:00', '13:00', '14:00', '15:00']
KINDS = ('infantry', 'lancer', 'marksman')
ROWS = '[data-testid^="player-row-"]'


def tr(key: str, lang: str = 'en', **v) -> str:
    return ui.tr(lang, key, **v)


def full(camp, tier):
    return {k: {'furnace_level': camp, 'tier': tier} for k in KINDS}


def put_svs(api: ui.Api, fid, name, alliance, troops, **answers):
    a = {'hours': ['12:00'], 'discord_vc': True}
    a.update(answers)
    return api.call('PUT', f'/api/events/svs/current/application/{fid}',
                    {'profile': {'game_name': name, 'alliance': alliance, 'troops': troops}, 'answers': a})[1]


@pytest.fixture(scope='module', autouse=True)
def svs_round(api):
    _, res = api.call('POST', '/api/admin/events/svs/start-new-round', {'name': f'SVS e2e {RUN}',
                                                                        'settings': {'battle_start': '11:00',
                                                                                     'battle_hours': 5}},
                      admin=True)
    rnd = res['round']
    put_svs(api, F_CALL, 'Caller', 'AAA', full('FC10', 11), hours=['11:00', '12:00'])
    put_svs(api, F_JOIN, 'Joiner', 'AAA', full('FC9', 10), hours=['12:00'], discord_vc=False)
    put_svs(api, F_WEAK, 'Weak', 'BBB', full('FC5', 10), hours=['15:00'])
    return rnd


def open_wizard(page: Page, base_url: str, fid: str, lang: str | None = None) -> str:
    page.goto(base_url + '/svs/apply')
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
    page.wait_for_timeout(300)


def hour_chips(page: Page) -> list[str]:
    return page.get_by_test_id('hour-grid').locator('[data-testid^="hour-"]').evaluate_all(
        "els => els.map(e => e.dataset.testid.slice(5)).filter(h => /^\\d\\d:\\d\\d$/.test(h))")


def fill_wizard(page: Page, lang: str, *, name: str, alliance: str | None, hours: list[str], camp: str, tier: int,
                vc: bool, shot=None, tag='') -> None:
    at_step(page, 1)
    page.get_by_test_id('profile-game-name').fill(name)
    if alliance is not None:
        page.get_by_test_id('profile-alliance').fill(alliance)
    shot and shot(f'{tag}1')
    next_step(page, 2)
    expect(page.get_by_test_id('utc-note')).to_have_text(tr('svs:step2.utcNote', lang))
    assert hour_chips(page) == DEFAULT_HOURS
    # at least one hour required
    page.get_by_test_id('wizard-next').click()
    expect(page.get_by_test_id('form-error')).to_have_text(tr('svs:errors.hoursRequired', lang))
    for h in hours:
        page.get_by_test_id(f'hour-{h}').click()
        expect(page.get_by_test_id(f'hour-{h}')).to_have_attribute('aria-pressed', 'true')
    shot and shot(f'{tag}2')
    next_step(page, 3)
    for k in KINDS:
        # tier options are EXACTLY T11 and T10 (never T8/T9 in SVS)
        group = page.get_by_test_id(f'troop-{k}-tier')
        assert group.locator('[role=radio]').all_inner_texts() == ['T11', 'T10']
        opts = page.get_by_test_id(f'troop-{k}-furnace').locator('option').evaluate_all('os => os.map(o => o.value)')
        assert opts == ['', 'FC10', 'FC9', 'FC8', 'FC7', 'FC6', 'FC5', 'FC4', 'FC3', 'FC2', 'FC1']
    page.get_by_test_id('wizard-next').click()
    expect(page.get_by_test_id('form-error')).to_have_text(tr('svs:errors.troopsRequired', lang))
    for k in KINDS:
        page.get_by_test_id(f'troop-{k}-furnace').select_option(camp)
        page.get_by_test_id(f'tier-{k}-{tier}').click()
        expect(page.get_by_test_id(f'tier-{k}-{tier}')).to_have_attribute('aria-checked', 'true')
    shot and shot(f'{tag}3')
    next_step(page, 4)
    # no role question any more (owner): step 4 is only Discord voice chat
    expect(page.get_by_test_id('wizard-step-4').locator('[data-testid^=role-]')).to_have_count(0)
    page.get_by_test_id('wizard-next').click()
    expect(page.get_by_test_id('form-error')).to_have_text(tr('svs:errors.vcRequired', lang))
    page.get_by_test_id('vc-yes' if vc else 'vc-no').click()
    shot and shot(f'{tag}4')
    next_step(page, 5)


# ------------------------------------------------------------------ player side

def test_home_tile_open_and_landing(page: Page, base_url, shot):
    page.goto(base_url + '/')
    page.wait_for_load_state('networkidle')
    tile = page.get_by_test_id('event-tile-svs')
    expect(tile).to_contain_text(tr('common:home.status.open'))
    expect(tile).not_to_contain_text(tr('common:home.status.nextRelease'))
    tile.click()
    page.wait_for_url('**/svs')
    expect(page.get_by_test_id('current-round')).to_contain_text(f'SVS e2e {RUN}')
    page.get_by_test_id('svs-apply-tile').click()
    page.wait_for_url('**/svs/apply')
    expect(page.get_by_test_id('wizard')).to_have_attribute('data-mode', 'lookup')
    expect(page.get_by_test_id('fid-help')).to_be_visible()
    shot('landing')


def test_full_wizard_english(page: Page, base_url, api, shot):
    assert open_wizard(page, base_url, FID_EN) == 'new'
    # new player: alliance required
    page.get_by_test_id('profile-game-name').fill(f'Svs EN {RUN}')
    page.get_by_test_id('wizard-next').click()
    expect(page.get_by_test_id('form-error')).to_have_text(tr('profile:allianceRequired'))
    fill_wizard(page, 'en', name=f'Svs EN {RUN}', alliance='sve', hours=['12:00', '13:00'], camp='FC8', tier=11,
                vc=True, shot=shot, tag='en-step')
    expect(page.get_by_test_id('review-hours').locator('[data-hour]')).to_have_count(2)
    expect(page.get_by_test_id('review-role')).to_have_count(0)
    expect(page.get_by_test_id('review-troop-lancer')).to_contain_text('FC8 / T11')
    shot('en-step5')
    page.get_by_test_id('wizard-submit').click()
    expect(page.get_by_test_id('save-success')).to_be_visible()
    _, app = api.call('GET', f'/api/events/svs/current/application/{FID_EN}')
    assert app['answers'] == {'hours': ['12:00', '13:00'], 'discord_vc': True, 'language': 'en'}
    _, prof = api.call('GET', f'/api/profile/{FID_EN}')
    assert prof['alliance'] == 'SVE' and prof['troops']['marksman'] == {'furnace_level': 'FC8', 'tier': 11}
    # edit by FID: everything pre-filled, Update
    page.get_by_test_id('reopen-application').click()
    expect(page.get_by_test_id('wizard')).to_have_attribute('data-mode', 'edit')
    expect(page.get_by_test_id('profile-alliance')).to_have_value('SVE')
    page.get_by_test_id('wizard-next').click()
    at_step(page, 2)
    expect(page.get_by_test_id('hour-12:00')).to_have_attribute('aria-pressed', 'true')
    expect(page.get_by_test_id('hour-11:00')).to_have_attribute('aria-pressed', 'false')
    page.get_by_test_id('hour-15:00').click()
    for n in (3, 4, 5):
        next_step(page, n)
    expect(page.get_by_test_id('wizard-submit')).to_have_attribute('data-mode', 'edit')
    page.get_by_test_id('wizard-submit').click()
    expect(page.get_by_test_id('save-success')).to_be_visible()
    _, app = api.call('GET', f'/api/events/svs/current/application/{FID_EN}')
    assert app['answers']['hours'] == ['12:00', '13:00', '15:00']


def test_arabic_rtl_wizard(page: Page, base_url, api, shot):
    assert open_wizard(page, base_url, FID_AR, lang='ar') == 'new'
    assert page.evaluate('document.documentElement.dir') == 'rtl'
    expect(page.get_by_test_id('wizard-step-title')).to_have_text(tr('svs:step1.title', 'ar'))
    fill_wizard(page, 'ar', name=f'عربي {RUN}', alliance='ARB', hours=['11:00'], camp='FC10', tier=10,
                vc=False, shot=shot, tag='ar-step')
    # step circles follow the page direction: step 1 on the right
    one = page.get_by_test_id('wizard-step-indicator-1').bounding_box()
    five = page.get_by_test_id('wizard-step-indicator-5').bounding_box()
    assert one['x'] > five['x']
    # times stay left-to-right inside Arabic text
    assert page.get_by_test_id('review-hours').locator('bdi').first.get_attribute('dir') == 'ltr'
    assert not ui.raw_i18n_keys(ui.visible_text(page))
    shot('ar-step5')
    page.get_by_test_id('wizard-submit').click()
    expect(page.get_by_test_id('save-success')).to_be_visible()
    _, app = api.call('GET', f'/api/events/svs/current/application/{FID_AR}')
    assert app['answers'] == {'hours': ['11:00'], 'discord_vc': False, 'language': 'ar'}


def test_hours_follow_the_round_setting(page: Page, base_url, api, svs_round):
    rid = svs_round['id']
    api.update_round(rid, settings={'battle_start': '22:00', 'battle_hours': 3})
    try:
        page.goto(base_url + '/svs/apply')
        page.wait_for_load_state('networkidle')
        page.get_by_test_id('fid-input').fill(str(BASE + 99))
        page.get_by_test_id('wizard-next').click()
        expect(page.get_by_test_id('wizard')).to_have_attribute('data-mode', 'new')
        page.get_by_test_id('profile-game-name').fill('Night owl')
        page.get_by_test_id('profile-alliance').fill('NIG')
        next_step(page, 2)
        assert hour_chips(page) == ['22:00', '23:00', '00:00']
        expect(page.get_by_test_id('hour-22:00').get_by_test_id('hour-utc')).to_have_text('22:00 UTC')
    finally:
        api.update_round(rid, settings={'battle_start': '11:00', 'battle_hours': 5})


def test_prefill_from_tyrant_and_back(page: Page, base_url, api):
    status, _ = api.call('GET', '/api/events/tyrant/current', ok=None)
    if status != 200:
        api.call('POST', '/api/admin/events/tyrant/start-new-round', {'name': f'FDT for SVS {RUN}'}, admin=True)
    troops = {'infantry': {'furnace_level': 'FC7', 'tier': 9}, 'lancer': {'furnace_level': 'FC9', 'tier': 11},
              'marksman': {'furnace_level': 'FC8', 'tier': 10}}
    api.call('PUT', f'/api/events/tyrant/current/application/{FID_PREFILL}',
             {'profile': {'game_name': 'From Tyrant', 'alliance': 'TYR', 'troops': troops}, 'answers': {}})
    assert open_wizard(page, base_url, FID_PREFILL) == 'new'
    expect(page.get_by_test_id('profile-game-name')).to_have_value('From Tyrant')
    expect(page.get_by_test_id('profile-alliance')).to_have_value('TYR')
    # a known alliance is optional (owner: ask new players only)
    assert page.get_by_test_id('profile-alliance').get_attribute('required') is None
    next_step(page, 2)
    page.get_by_test_id('hour-14:00').click()
    next_step(page, 3)
    expect(page.get_by_test_id('troop-infantry-furnace')).to_have_value('FC7')
    expect(page.get_by_test_id('troop-lancer-furnace')).to_have_value('FC9')
    # Tyrant's T9 is not an SVS tier: shown unselected, must be picked; T11 / T10 carry over
    expect(page.get_by_test_id('troop-infantry-tier')).to_have_attribute('data-value', '')
    expect(page.get_by_test_id('tier-lancer-11')).to_have_attribute('aria-checked', 'true')
    expect(page.get_by_test_id('tier-marksman-10')).to_have_attribute('aria-checked', 'true')
    page.get_by_test_id('wizard-next').click()
    expect(page.get_by_test_id('form-error')).to_be_visible()
    page.get_by_test_id('tier-infantry-10').click()
    page.get_by_test_id('troop-marksman-furnace').select_option('FC9')
    next_step(page, 4)
    page.get_by_test_id('vc-yes').click()
    next_step(page, 5)
    page.get_by_test_id('wizard-submit').click()
    expect(page.get_by_test_id('save-success')).to_be_visible()
    # ... and the Tyrant wizard now pre-fills from SVS (same shared profile)
    page.goto(base_url + '/tyrant/apply')
    page.wait_for_load_state('networkidle')
    page.get_by_test_id('fid-input').fill(FID_PREFILL)
    page.get_by_test_id('wizard-next').click()
    expect(page.get_by_test_id('wizard')).to_have_attribute('data-mode', 'edit')
    for n in (2, 3, 4):
        next_step(page, n)
    expect(page.get_by_test_id('troop-infantry-tier')).to_have_value('10')
    expect(page.get_by_test_id('troop-marksman-furnace')).to_have_value('FC9')
    expect(page.get_by_test_id('troop-lancer-tier')).to_have_value('11')


def test_closed_round_behaviour(page: Page, base_url, api, svs_round):
    rid = svs_round['id']
    api.update_round(rid, closing_time='2020-01-01T00:00:00Z')
    try:
        assert open_wizard(page, base_url, FID_LATE) == 'closed'
        expect(page.get_by_test_id('applications-closed')).to_contain_text(tr('tyrant:apply.closedTitle'))
        # an existing sign-up stays editable
        assert open_wizard(page, base_url, FID_EN) == 'edit'
        expect(page.get_by_test_id('closing-note')).to_have_text(tr('tyrant:apply.closedButEditable'))
    finally:
        api.update_round(rid, closing_time=None)


def test_no_raw_keys_9_languages(page: Page, base_url, shot):
    page.goto(base_url + '/svs')
    page.wait_for_load_state('networkidle')
    assert ui.check_all_languages(page, 'svs-home', shot) == {}
    page.goto(base_url + '/svs/apply')
    page.wait_for_load_state('networkidle')
    assert ui.check_all_languages(page, 'svs-apply', shot) == {}


# ------------------------------------------------------------------ admin

def open_admin(page: Page, base_url: str, api: ui.Api, event: str = 'svs', query: str = '') -> None:
    ui.use_admin_token(page, base_url, api.token(), ui.admin_dashboard_url(event) + query)
    expect(page.get_by_test_id('round-select')).to_be_visible()
    page.wait_for_load_state('networkidle')


def test_admin_stats_bars_chips_filters_export(page: Page, base_url, api, shot):
    open_admin(page, base_url, api)
    expect(page.get_by_test_id('svs-table')).to_be_visible()
    _, s = api.call('GET', '/api/admin/svs/rounds/current/summary', admin=True)
    expect(page.get_by_test_id('stat-total-value')).to_have_text(str(s['total']))
    expect(page.get_by_test_id('stat-avg-hours-value')).to_have_text(str(s['avg_hours']))
    expect(page.get_by_test_id('stat-all-t11-value')).to_have_text(str(s['all_t11']))
    # no role anywhere (owner: SVS sign-up does not ask it)
    for gone in ('stat-callers', 'stat-joiners', 'by-role', 'filter-role'):
        expect(page.get_by_test_id(gone)).to_have_count(0)
    expect(page.get_by_test_id('stat-discord-vc-value')).to_have_text(str(s['discord_vc']))
    # dashboard order (owner): stats -> bars -> troop chips -> filter bar -> table
    tops = [page.get_by_test_id(t).bounding_box()['y'] for t in ('stat-total', 'by-hour', 'by-troop', 'svs-filters',
                                                                  'svs-table')]
    assert tops == sorted(tops), tops
    # players per hour: one bar per battle hour, clickable as a filter
    expect(page.get_by_test_id('by-hour').locator('button')).to_have_count(5)
    page.get_by_test_id('by-hour-15:00').click()
    expect(page.get_by_test_id('by-hour-15:00')).to_have_attribute('aria-pressed', 'true')
    assert 'hours=15' in page.url
    expect(page.get_by_test_id(f'player-row-{F_WEAK}')).to_be_visible()
    expect(page.get_by_test_id(f'player-row-{F_CALL}')).to_have_count(0)
    page.get_by_test_id('clear-filters').click()
    # tier chips are T11 / T10 (+ none); a camp chip filters exactly
    labels = page.get_by_test_id('tier-chips-infantry').locator('button').all_inner_texts()
    assert all(lbl.split(':')[0].strip() in ('T11', 'T10', tr('tyrant:admin.none')) for lbl in labels), labels
    page.get_by_test_id('chip-infantry-camp-FC9').click()
    expect(page.locator(ROWS)).to_have_count(1)
    expect(page.get_by_test_id(f'player-row-{F_JOIN}')).to_be_visible()
    expect(page.get_by_test_id(f'troop-summary-{F_JOIN}')).to_contain_text('FC9 T10')
    expect(page.get_by_test_id('stat-total-value')).to_have_text('1')
    page.get_by_test_id('clear-filters').click()
    # filter bar: alliance + T11 only + FC10 camps -> the caller; export follows the filters
    page.get_by_test_id('filter-min-camp').select_option('FC10')
    page.get_by_test_id('filter-min-tier').select_option('11')
    expect(page.get_by_test_id(f'player-row-{F_CALL}')).to_be_visible()
    expect(page.get_by_test_id(f'player-row-{F_JOIN}')).to_have_count(0)
    shot('admin-filtered')
    with page.expect_download() as dl:
        page.get_by_test_id('export-csv').click()
    rows = list(csv.reader(io.StringIO(open(dl.value.path(), encoding='utf-8-sig').read())))
    fids = [r[0] for r in rows[1:]]
    assert F_CALL in fids and F_JOIN not in fids and F_WEAK not in fids
    head = rows[0]
    assert head[:4] == ['FID', 'In-Game Name', 'Alliance', '11:00 UTC'] and 'Role' not in head
    assert dict(zip(head, rows[fids.index(F_CALL) + 1]))['Joiner Strength'] == '63'
    with page.expect_download() as dl:
        page.get_by_test_id('export-excel').click()
    assert dl.value.suggested_filename.endswith('_filtered.xlsx')
    # strength sort
    page.get_by_test_id('clear-filters').click()
    page.get_by_test_id('sort-strength').click()
    expect(page.get_by_test_id('sort-strength')).to_have_attribute('data-active', 'desc')
    expect(page.locator(ROWS).first).to_have_attribute('data-testid', f'player-row-{F_CALL}')   # 63 = FC10 + T11 x3
    shot('admin-players')


def test_admin_settings_battle_hours(page: Page, base_url, api, svs_round, shot):
    open_admin(page, base_url, api)
    page.get_by_test_id('tab-settings').click()
    expect(page.get_by_test_id('battle-start')).to_have_value('11:00')
    expect(page.get_by_test_id('battle-hours')).to_have_value('5')
    expect(page.get_by_test_id('battle-preview').locator('[data-hour]')).to_have_count(5)
    page.get_by_test_id('battle-start').fill('12:00')
    page.get_by_test_id('battle-hours').fill('4')
    expect(page.get_by_test_id('battle-preview').locator('[data-hour]')).to_have_count(4)
    page.get_by_test_id('save-battle').click()
    expect(page.get_by_test_id('settings-saved')).to_be_visible()
    try:
        _, cur = api.call('GET', '/api/events/svs/current')
        assert cur['settings']['hours'] == ['12:00', '13:00', '14:00', '15:00']
        shot('admin-settings')
    finally:
        api.update_round(svs_round['id'], settings={'battle_start': '11:00', 'battle_hours': 5})


def test_heroes_view_respects_generation(page: Page, base_url, api, shot):
    open_admin(page, base_url, api)
    page.get_by_test_id('tab-heroes').click()
    expect(page.get_by_test_id('hero-grid')).to_be_visible()
    expect(page.get_by_test_id('hero-credit')).to_have_text(tr('common:heroes.credit'))
    try:
        page.get_by_test_id('state-generation').select_option('5')
        page.get_by_test_id('save-state-generation').click()
        expect(page.get_by_test_id('state-generation-saved')).to_be_visible()
        _, lib5 = api.call('GET', '/api/heroes?max_gen=5')
        expect(page.get_by_test_id('heroes-count')).to_have_text(tr('admin:heroes.count', n=lib5['total'], gen=5))
        expect(page.get_by_test_id('hero-grid').locator('[data-generation]')).to_have_count(lib5['total'])
        gens = page.get_by_test_id('hero-grid').locator('[data-generation]').evaluate_all(
            'els => els.map(e => e.dataset.generation)')
        assert gens and max(int(g) for g in gens if g) == 5
        assert '' in gens                                          # rare/epic heroes (no generation) stay
        expect(page.get_by_test_id('hero-jeronimo').get_by_test_id('hero-gen')).to_have_text(tr('common:heroes.gen', n=1))
        expect(page.get_by_test_id('hero-aiden')).to_have_count(0)  # Gen 17
        img = page.get_by_test_id('hero-jeronimo').locator('img')
        assert img.evaluate('i => i.complete && i.naturalWidth > 0')
        # troop filter
        page.get_by_test_id('hero-troop-marksman').click()
        expect(page.get_by_test_id('hero-troop-marksman')).to_have_attribute('aria-pressed', 'true')
        expect(page.get_by_test_id('hero-grid').locator('[data-troop=lancer]')).to_have_count(0)
        expect(page.get_by_test_id('hero-grid').locator('[data-troop=infantry]')).to_have_count(0)
        troops = page.get_by_test_id('hero-grid').locator('[data-troop]').evaluate_all('els => els.map(e => e.dataset.troop)')
        assert set(troops) == {'marksman'}
        shot('heroes-gen5')
        # the same setting is in the Minister settings tab (state-wide)
        open_admin(page, base_url, api, event='ministry')
        page.get_by_test_id('tab-settings').click()
        expect(page.get_by_test_id('state-generation')).to_have_value('5')
        ui.switch_language(page, 'ar')
        open_admin(page, base_url, api)
        page.get_by_test_id('tab-heroes').click()
        expect(page.get_by_test_id('hero-jeronimo').get_by_test_id('hero-gen')).to_have_text(tr('common:heroes.gen', 'ar', n=1))
        assert not ui.raw_i18n_keys(ui.visible_text(page))
        shot('heroes-ar')
    finally:
        api.call('PUT', '/api/admin/settings', {'state_generation': 17}, admin=True)
        page.evaluate("localStorage.removeItem('preferred_language')")


@pytest.mark.parametrize('event', ['ministry', 'tyrant', 'svs'])
def test_add_player_every_event(page: Page, base_url, api, event, shot):
    status, cur = api.call('GET', f'/api/events/{event}/current', ok=None)
    if status != 200:
        api.call('POST', f'/api/admin/events/{event}/start-new-round', {'name': f'{event} add {RUN}'}, admin=True)
    fid = str(BASE + 500 + secrets.randbelow(400_000))
    open_admin(page, base_url, api, event=event)
    page.get_by_test_id('add-player').click()
    dialog = page.get_by_test_id('add-player-dialog')
    expect(dialog).to_have_attribute('data-event', event)
    page.get_by_test_id('add-save').click()                       # FID required
    expect(page.get_by_test_id('add-error')).to_have_text(tr('profile:fidRequired'))
    page.get_by_test_id('add-fid').fill(fid)
    page.get_by_test_id('add-lookup').click()
    expect(page.get_by_test_id('add-status')).to_have_attribute('data-known', 'false')
    page.get_by_test_id('add-name').fill(f'Added {event}')
    page.get_by_test_id('add-alliance').fill('add')
    if event == 'svs':
        page.get_by_test_id('add-hour-13:00').click()
        tiers = page.get_by_test_id('add-infantry-tier').locator('option').evaluate_all('os => os.map(o => o.value)')
        assert tiers == ['', '11', '10']
        page.get_by_test_id('add-infantry-tier').select_option('11')
    elif event == 'tyrant':
        page.get_by_test_id('add-window-w2').click()
    else:
        page.get_by_test_id('add-construction_speedups_days').fill('7')
    shot(f'add-{event}')
    page.get_by_test_id('add-save').click()
    expect(dialog).to_have_count(0)
    expect(page.get_by_test_id(f'player-row-{fid}')).to_be_visible()
    _, app = api.call('GET', f'/api/events/{event}/current/application/{fid}')
    if event == 'svs':
        assert app['answers'] == {'hours': ['13:00'], 'discord_vc': None, 'language': None}
        _, prof = api.call('GET', f'/api/profile/{fid}')
        assert prof['troops']['infantry']['tier'] == 11 and prof['alliance'] == 'ADD'
    elif event == 'tyrant':
        assert app['answers']['availability'] == ['w2']
    else:
        assert app['answers']['construction_speedups_days'] == 7
    # the same FID again: clear message, nothing created
    page.get_by_test_id('add-player').click()
    page.get_by_test_id('add-fid').fill(fid)
    page.get_by_test_id('add-lookup').click()
    expect(page.get_by_test_id('add-status')).to_have_attribute('data-known', 'true')
    expect(page.get_by_test_id('add-name')).to_have_value(f'Added {event}')
    page.get_by_test_id('add-save').click()
    expect(page.get_by_test_id('add-error')).to_have_text(tr('admin:addPlayer.exists'))
    page.get_by_test_id('add-player-close').click()


def test_svs_admin_guide_and_switch(page: Page, base_url, api, shot):
    open_admin(page, base_url, api)
    expect(page.get_by_test_id('admin-subtitle')).to_contain_text(tr('svs:admin.adminSubtitle'))
    expect(page.get_by_test_id('admin-event-svs')).to_be_visible()      # SVS is in the event switch
    page.goto(base_url + ui.admin_guide_url('svs'))
    page.wait_for_load_state('networkidle')
    expect(page.get_by_test_id('admin-guide-svs')).to_be_visible()
    assert ui.check_all_languages(page, 'svs-admin-guide', shot) == {}
