"""Admin Edit / Remove in the SVS and Frost Dragon Tyrant player lists (v2.2.1).

Edit opens the shared add/edit dialog prefilled (FID read-only), saves with PUT /api/admin/applications/<id> and
patches the row in place (filters in the URL stay). Validation errors land on their field. Remove asks first; for
SVS the confirmation says where the player is in the battle plan, and the server takes them out of the plan in the
same transaction. Closed rounds keep the buttons visible but disabled with a tooltip. Arabic renders RTL; a 390px
phone has no sideways scroll. Every context fails on a CSP violation (conftest).
"""
from __future__ import annotations

import secrets
import time

import pytest
from playwright.sync_api import Page, expect

import ui

RUN = time.strftime('%H%M%S')
BASE = 71_000_000 + secrets.randbelow(900_000)
SVS_FIDS = [str(BASE + i) for i in range(5)]
SVS_NAMES = [f'Edi{i}x{RUN}' for i in range(5)]
TYR_FIDS = [str(BASE + 100 + i) for i in range(3)]
TYR_NAMES = [f'Tyd{i}x{RUN}' for i in range(3)]
ALIAS = 'Rally Caller 01'
MAIN = 'Main rallies'


def tr(key: str, lang: str = 'en', **v) -> str:
    return ui.tr(lang, key, **v)


def troops(camp='FC10', tier=11):
    return {k: {'furnace_level': camp, 'tier': tier} for k in ('infantry', 'lancer', 'marksman')}


@pytest.fixture(scope='module')
def rounds(api):
    _, svs = api.call('POST', '/api/admin/events/svs/start-new-round',
                      {'name': f'SVS edit e2e {RUN}', 'settings': {'battle_start': '11:00', 'battle_hours': 5}},
                      admin=True)
    for fid, name in zip(SVS_FIDS, SVS_NAMES):
        api.call('PUT', f'/api/events/svs/current/application/{fid}',
                 {'profile': {'game_name': name, 'alliance': 'EDA', 'troops': troops()},
                  'answers': {'hours': ['11:00', '12:00'], 'discord_vc': True}})
    # the plan: SVS_FIDS[0] leads "Rally Caller 01" in Main, SVS_FIDS[1] is its Joiner 2
    _, plan = api.call('GET', '/api/admin/svs/rounds/current/plan', admin=True)
    doc = plan['plan']
    doc['groups'][0]['name'] = MAIN
    named = [{'player': None, 'rally': {'lead_hero': None, 'ratio_override': None},
              'garrison': {'lead_hero': None, 'ratio_override': None}} for _ in range(4)]
    named[1]['player'] = {'fid': SVS_FIDS[1]}
    doc['leaders'] = [{'id': 'L1', 'group_id': doc['groups'][0]['id'], 'order': 0, 'player': {'fid': SVS_FIDS[0]},
                       'disguise': {'pfp_hero': None, 'alias': ALIAS}, 'split': False,
                       'rally': {'heroes': [None, None, None], 'ratio': None}, 'garrison': None, 'pet_buff': None,
                       'named_joiners': named, 'other_joiner_heroes': {'rally': [], 'garrison': []},
                       'extra_joiners': []}]
    api.call('PUT', '/api/admin/svs/rounds/current/plan', {'revision': plan['revision'], 'plan': doc}, admin=True)

    _, tyr = api.call('POST', '/api/admin/events/tyrant/start-new-round', {'name': f'FDT edit e2e {RUN}'}, admin=True)
    for fid, name in zip(TYR_FIDS, TYR_NAMES):
        api.call('PUT', f'/api/events/tyrant/current/application/{fid}',
                 {'profile': {'game_name': name, 'alliance': 'TYD', 'troops': troops('FC8', 10),
                              'power': 400_000_000, 'discord_id': None},
                  'answers': {'availability': ['w1', 'w2'], 'discord_vc': False, 'gem_spend': 5000,
                              'roles': ['joiner']}})
    return {'svs': svs['round'], 'tyrant': tyr['round']}


def open_players(page: Page, base_url: str, api, event: str, query: str = '') -> None:
    ui.use_admin_token(page, base_url, api.token(), ui.admin_dashboard_url(event) + query)
    expect(page.get_by_test_id(f'{event}-table')).to_be_visible()
    page.wait_for_load_state('networkidle')


def svs_app(api, fid):
    return api.call('GET', f'/api/events/svs/current/application/{fid}')[1]


def get_plan(api):
    return api.call('GET', '/api/admin/svs/rounds/current/plan', admin=True)[1]


# ---------------------------------------------------------------- SVS: hours, VC, troops -> the row updates in place

def test_svs_edit_hours_vc_troops(page: Page, base_url, api, rounds, shot):
    fid = SVS_FIDS[2]
    open_players(page, base_url, api, 'svs', '&alliance=EDA&sort=name&dir=asc')
    expect(page.get_by_test_id(f'hours-{fid}').locator('[data-on=true]')).to_have_count(2)
    btn = page.get_by_test_id(f'edit-{fid}')
    expect(btn).to_have_attribute('aria-label', tr('admin:playerEdit.editLabel', name=SVS_NAMES[2]))
    btn.focus()
    page.keyboard.press('Enter')                       # keyboard accessible
    dialog = page.get_by_test_id('edit-player-dialog')
    expect(dialog).to_be_visible()
    expect(dialog).to_have_attribute('data-event', 'svs')
    expect(page.get_by_test_id('edit-fid')).to_have_value(fid)
    expect(page.get_by_test_id('edit-fid')).to_have_attribute('readonly', '')
    expect(page.get_by_test_id('edit-name')).to_have_value(SVS_NAMES[2])
    expect(page.get_by_test_id('edit-name')).to_be_focused()
    expect(page.get_by_test_id('edit-alliance')).to_have_value('EDA')
    expect(page.get_by_test_id('edit-shared-note')).to_have_text(tr('admin:playerEdit.shared'))
    expect(page.get_by_test_id('edit-hour-11:00')).to_have_attribute('aria-pressed', 'true')
    expect(page.get_by_test_id('edit-hour-13:00')).to_have_attribute('aria-pressed', 'false')
    expect(page.get_by_test_id('edit-vc')).to_have_value('yes')
    expect(page.get_by_test_id('edit-infantry-tier')).to_have_value('11')
    expect(page.get_by_test_id('edit-lancer-camp')).to_have_value('FC10')
    tiers = page.get_by_test_id('edit-infantry-tier').locator('option').evaluate_all('os => os.map(o => o.value)')
    assert tiers == ['', '11', '10']                   # SVS: T10/T11 only
    shot('svs-edit-dialog-en', full_page=False)

    page.get_by_test_id('edit-hour-11:00').click()
    page.get_by_test_id('edit-hour-13:00').click()
    page.get_by_test_id('edit-vc').select_option('no')
    page.get_by_test_id('edit-infantry-tier').select_option('10')
    page.get_by_test_id('edit-lancer-camp').select_option('FC9')
    page.get_by_test_id('edit-name').fill(SVS_NAMES[2] + 'z')
    page.get_by_test_id('edit-save').click()
    expect(dialog).to_have_count(0)
    expect(page.get_by_test_id('admin-toast')).to_have_text(tr('admin:playerEdit.saved', name=SVS_NAMES[2] + 'z'))
    expect(page.get_by_test_id(f'edit-{fid}')).to_be_focused()   # focus back on the row button
    row = page.get_by_test_id(f'player-row-{fid}')
    expect(row).to_contain_text(SVS_NAMES[2] + 'z')
    on = page.get_by_test_id(f'hours-{fid}').locator('[data-on=true]')
    expect(on).to_have_count(2)
    expect(on.first).to_have_text('12:00')
    expect(page.get_by_test_id(f'troop-summary-{fid}')).to_contain_text('FC9')
    assert 'alliance=EDA' in page.url and 'sort=name' in page.url  # filters kept
    app = svs_app(api, fid)
    assert app['answers']['hours'] == ['12:00', '13:00'] and app['answers']['discord_vc'] is False
    _, prof = api.call('GET', f'/api/profile/{fid}')
    assert prof['game_name'] == SVS_NAMES[2] + 'z'
    assert prof['troops']['infantry'] == {'furnace_level': 'FC10', 'tier': 10}
    assert prof['troops']['lancer'] == {'furnace_level': 'FC9', 'tier': 11}
    shot('svs-after-edit')


# ---------------------------------------------------------------- Tyrant: windows, roles, stats, troops

def test_tyrant_edit_windows_troops(page: Page, base_url, api, rounds, shot):
    fid = TYR_FIDS[0]
    open_players(page, base_url, api, 'tyrant')
    page.get_by_test_id(f'edit-{fid}').click()
    dialog = page.get_by_test_id('edit-player-dialog')
    expect(dialog).to_have_attribute('data-event', 'tyrant')
    expect(page.get_by_test_id('edit-shared-note')).to_have_text(tr('admin:playerEdit.sharedTyrant'))
    expect(page.get_by_test_id('edit-window-w1')).to_have_attribute('aria-pressed', 'true')
    expect(page.get_by_test_id('edit-window-w3')).to_have_attribute('aria-pressed', 'false')
    expect(page.get_by_test_id('edit-power')).to_have_value('400')
    expect(page.get_by_test_id('edit-gems')).to_have_value('5000')
    expect(page.get_by_test_id('edit-vc')).to_have_value('no')
    tiers = page.get_by_test_id('edit-marksman-tier').locator('option').evaluate_all('os => os.map(o => o.value)')
    assert tiers == ['', '11', '10', '9', '8']        # Tyrant: T8-T11
    shot('tyrant-edit-dialog', full_page=False)

    page.get_by_test_id('edit-window-w1').click()
    page.get_by_test_id('edit-window-w3').click()
    page.get_by_test_id('edit-roles').click()
    page.get_by_test_id('edit-roles-option-rally_leader').click()
    page.keyboard.press('Escape')                      # closes the roles menu only, not the dialog
    expect(page.get_by_test_id('edit-roles-menu')).to_have_count(0)
    expect(dialog).to_be_visible()
    page.get_by_test_id('edit-vc').select_option('yes')
    page.get_by_test_id('edit-power').fill('512.5')
    page.get_by_test_id('edit-discord-id').fill('tyd#7')
    page.get_by_test_id('edit-marksman-camp').select_option('FC10')
    page.get_by_test_id('edit-marksman-tier').select_option('8')
    page.get_by_test_id('edit-save').click()
    expect(dialog).to_have_count(0)
    expect(page.get_by_test_id('admin-toast')).to_be_visible()
    row = page.get_by_test_id(f'player-row-{fid}')
    expect(row).to_contain_text('tyd#7')
    expect(row).to_contain_text('512.5M')
    expect(page.get_by_test_id(f'troop-summary-{fid}')).to_contain_text('FC10 T8')
    _, app = api.call('GET', f'/api/events/tyrant/current/application/{fid}')
    assert app['answers']['availability'] == ['w2', 'w3'] and app['answers']['discord_vc'] is True
    assert app['answers']['roles'] == ['rally_leader', 'joiner'] and app['answers']['gem_spend'] == 5000
    _, prof = api.call('GET', f'/api/profile/{fid}')
    assert prof['power'] == 512_500_000 and prof['discord_id'] == 'tyd#7'
    assert prof['troops']['marksman'] == {'furnace_level': 'FC10', 'tier': 8}
    assert prof['troops']['infantry'] == {'furnace_level': 'FC8', 'tier': 10}


# ---------------------------------------------------------------- validation errors land on the field

def test_validation_error_on_field(page: Page, base_url, api, rounds, shot):
    fid = TYR_FIDS[1]
    open_players(page, base_url, api, 'tyrant')
    page.get_by_test_id(f'edit-{fid}').click()
    dialog = page.get_by_test_id('edit-player-dialog')
    # client check (same message as the wizard)
    page.get_by_test_id('edit-gems').fill('lots')
    page.get_by_test_id('edit-save').click()
    expect(dialog.get_by_test_id('field-error')).to_have_text(tr('tyrant:errors.gems'))
    expect(page.get_by_test_id('edit-gems')).to_have_attribute('aria-invalid', 'true')
    expect(page.get_by_test_id('edit-gems')).to_be_focused()
    expect(page.get_by_test_id('edit-error')).to_have_count(0)   # not repeated at the bottom
    # server check (over the API's maximum): the translated "check this field" message, on the gems field
    page.get_by_test_id('edit-gems').fill('9999999999')
    page.get_by_test_id('edit-save').click()
    expect(dialog.get_by_test_id('field-error')).to_have_text(
        tr('common:errors.invalidField', field=tr('tyrant:step3.gemSpend')))
    expect(page.get_by_test_id('edit-gems')).to_have_attribute('aria-invalid', 'true')
    shot('validation-error', full_page=False)
    # the name is required
    page.get_by_test_id('edit-gems').fill('')
    page.get_by_test_id('edit-name').fill('')
    page.get_by_test_id('edit-save').click()
    expect(dialog.get_by_test_id('field-error')).to_have_text(tr('ministry:form.required'))
    expect(page.get_by_test_id('edit-name')).to_have_attribute('aria-invalid', 'true')
    page.keyboard.press('Escape')
    expect(dialog).to_have_count(0)
    _, app = api.call('GET', f'/api/events/tyrant/current/application/{fid}')
    assert app['answers']['gem_spend'] == 5000                  # nothing saved


# ---------------------------------------------------------------- delete with the battle-plan warning

def test_svs_delete_with_plan_warning(page: Page, base_url, api, rounds, shot):
    open_players(page, base_url, api, 'svs')
    rev = get_plan(api)['revision']
    # a player who is NOT in the plan: plain confirmation; Cancel has the focus, Esc closes
    page.get_by_test_id(f'delete-{SVS_FIDS[3]}').click()
    dialog = page.get_by_test_id('delete-dialog')
    expect(dialog).to_be_visible()
    expect(page.get_by_test_id('delete-plan-warning')).to_have_count(0)
    expect(page.get_by_test_id('cancel-delete')).to_be_focused()
    page.keyboard.press('Escape')
    expect(dialog).to_have_count(0)
    expect(page.get_by_test_id(f'delete-{SVS_FIDS[3]}')).to_be_focused()

    # Joiner 2 of Rally Caller 01: the confirmation names the player and the place
    page.get_by_test_id(f'delete-{SVS_FIDS[1]}').click()
    expect(dialog).to_be_visible()
    expect(dialog.locator('#delete-player-title')).to_have_text(tr('admin:playerEdit.deleteTitle', name=SVS_NAMES[1]))
    expect(page.get_by_test_id('delete-who')).to_contain_text(SVS_FIDS[1])
    expect(page.get_by_test_id('delete-plan-warning')).to_have_text(
        tr('svs:players.deletePlan.joiner', leader=ALIAS, group=MAIN, n=2))
    shot('delete-confirm-plan', full_page=False)
    page.get_by_test_id('confirm-delete').click()
    expect(dialog).to_have_count(0)
    expect(page.get_by_test_id(f'player-row-{SVS_FIDS[1]}')).to_have_count(0)
    expect(page.get_by_test_id('admin-toast')).to_have_text(tr('admin:playerEdit.removedPlan', name=SVS_NAMES[1]))
    plan = get_plan(api)
    assert plan['revision'] == rev + 1
    ld = plan['plan']['leaders'][0]
    assert ld['named_joiners'][1]['player'] is None and ld['player'] == {'fid': SVS_FIDS[0]}
    status, _ = api.call('GET', f'/api/events/svs/current/application/{SVS_FIDS[1]}', ok=None)
    assert status == 404
    # the leader: their own sentence
    page.get_by_test_id(f'delete-{SVS_FIDS[0]}').click()
    expect(page.get_by_test_id('delete-plan-warning')).to_have_text(
        tr('svs:players.deletePlan.leader', leader=ALIAS, group=MAIN))
    page.get_by_test_id('cancel-delete').click()


def test_tyrant_delete(page: Page, base_url, api, rounds):
    fid = TYR_FIDS[2]
    open_players(page, base_url, api, 'tyrant')
    page.get_by_test_id(f'delete-{fid}').click()
    expect(page.get_by_test_id('delete-dialog')).to_contain_text(TYR_NAMES[2])
    page.get_by_test_id('confirm-delete').click()
    expect(page.get_by_test_id(f'player-row-{fid}')).to_have_count(0)
    status, _ = api.call('GET', f'/api/events/tyrant/current/application/{fid}', ok=None)
    assert status == 404


# ---------------------------------------------------------------- Arabic + a 390px phone

def test_arabic_and_phone_edit_dialog(page: Page, base_url, api, rounds, shot):
    fid = SVS_FIDS[4]
    open_players(page, base_url, api, 'svs')
    ui.switch_language(page, 'ar')
    page.get_by_test_id(f'edit-{fid}').click()
    dialog = page.get_by_test_id('edit-player-dialog')
    expect(dialog).to_be_visible()
    assert page.evaluate('document.documentElement.dir') == 'rtl'
    expect(dialog.locator('#add-player-title')).to_have_text(tr('admin:editPlayer', 'ar'))
    expect(page.get_by_test_id('edit-shared-note')).to_have_text(tr('admin:playerEdit.shared', 'ar'))
    expect(page.get_by_test_id('edit-troops-hint')).to_have_text(tr('admin:playerEdit.troopsHint', 'ar'))
    text = dialog.inner_text()
    assert not ui.raw_i18n_keys(text), ui.raw_i18n_keys(text)
    # RTL: the close button sits on the left of the title
    close = page.get_by_test_id('edit-player-close').bounding_box()
    title = dialog.locator('#add-player-title').bounding_box()
    assert close['x'] < title['x']
    shot('svs-edit-dialog-ar', full_page=False)
    page.get_by_test_id('edit-cancel').click()
    page.get_by_test_id(f'delete-{fid}').click()
    expect(page.get_by_test_id('delete-dialog')).to_contain_text(tr('admin:playerEdit.deleteConfirm', 'ar'))
    shot('delete-confirm-ar', full_page=False)
    page.get_by_test_id('cancel-delete').click()
    ui.switch_language(page, 'en')

    page.set_viewport_size({'width': 390, 'height': 844})
    page.reload()
    page.wait_for_load_state('networkidle')
    page.get_by_test_id(f'edit-{fid}').scroll_into_view_if_needed()
    page.get_by_test_id(f'edit-{fid}').click()
    expect(dialog).to_be_visible()
    box = dialog.bounding_box()
    assert box['x'] >= 0 and box['x'] + box['width'] <= 390
    assert page.evaluate('document.documentElement.scrollWidth') <= 390
    for tid in ('edit-save', 'edit-cancel', 'edit-player-close', 'edit-hour-11:00'):
        assert page.get_by_test_id(tid).bounding_box()['height'] >= 44, tid
    shot('svs-edit-dialog-phone', full_page=False)
    page.get_by_test_id('edit-save').scroll_into_view_if_needed()
    shot('svs-edit-dialog-phone-bottom', full_page=False)
    page.get_by_test_id('edit-cancel').click()


# ---------------------------------------------------------------- closed rounds: read-only

@pytest.mark.parametrize('event', ['svs', 'tyrant'])
def test_closed_round_disables_actions(page: Page, base_url, api, rounds, event, shot):
    old = rounds[event]
    if api.call('GET', f'/api/events/{event}/current', ok=None)[1].get('id') == old['id']:
        api.call('POST', f'/api/admin/events/{event}/start-new-round', {'name': f'{event} after edit {RUN}'},
                 admin=True)
    open_players(page, base_url, api, event)
    page.get_by_test_id('round-select').select_option(str(old['id']))
    expect(page.get_by_test_id('read-only-banner')).to_be_visible()
    fid = SVS_FIDS[0] if event == 'svs' else TYR_FIDS[0]
    for kind in ('edit', 'delete'):
        b = page.get_by_test_id(f'{kind}-{fid}')
        expect(b).to_be_visible()
        expect(b).to_have_attribute('aria-disabled', 'true')
        expect(b).to_have_attribute('title', tr('admin:playerEdit.closed'))
        b.click(force=True)                            # aria-disabled: a click does nothing
    expect(page.get_by_test_id('edit-player-dialog')).to_have_count(0)
    expect(page.get_by_test_id('delete-dialog')).to_have_count(0)
    expect(page.locator('#row-actions-closed')).to_have_text(tr('admin:playerEdit.closed'))
    if event == 'svs':
        expect(page.get_by_test_id(f'add-to-rally-{fid}')).to_have_count(0)
    shot(f'closed-{event}', full_page=False)
