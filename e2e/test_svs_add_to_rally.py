"""SVS Players tab -> "Add to rally" (v2.2.1): the Plan column, adding a player to an existing rally leader from the
table and seeing it in the Battle plan tab, named-full goes to extra, "Move here", bulk add with one already placed
(skipped and reported), the In plan / Not in plan filter, the automatic retry after a revision conflict, and the
empty-plan message that links to the Battle plan tab. Every context fails on a CSP violation (conftest).
"""
from __future__ import annotations

import re
import secrets
import time

import pytest
from playwright.sync_api import Page, expect

import ui

RUN = time.strftime('%H%M%S')
BASE = 63_000_000 + secrets.randbelow(900_000)
N = 24
FIDS = [str(BASE + i) for i in range(N)]
NAMES = [f'Ral{i:02d}x{RUN}' for i in range(N)]
NAME = dict(zip(FIDS, NAMES))
ALIAS = 'Rally Caller 01'
MAIN, COUNTER, TUR = 'Main rallies', 'Counter rallies', 'Turrets'


def tr(key: str, lang: str = 'en', **v) -> str:
    return ui.tr(lang, key, **v)


def troops(camp='FC10', tier=11):
    return {k: {'furnace_level': camp, 'tier': tier} for k in ('infantry', 'lancer', 'marksman')}


@pytest.fixture(scope='module', autouse=True)
def rally_round(api):
    _, res = api.call('POST', '/api/admin/events/svs/start-new-round',
                      {'name': f'SVS rally e2e {RUN}', 'settings': {'battle_start': '11:00', 'battle_hours': 5}},
                      admin=True)
    for fid, name in zip(FIDS, NAMES):
        api.call('PUT', f'/api/events/svs/current/application/{fid}',
                 {'profile': {'game_name': name, 'alliance': 'RAL', 'troops': troops()},
                  'answers': {'hours': ['11:00', '12:00'], 'discord_vc': True}})
    return res['round']


def blank_leader(lid, gid, fid, alias=None):
    return {'id': lid, 'group_id': gid, 'order': 0, 'player': {'fid': fid},
            'disguise': {'pfp_hero': None, 'alias': alias}, 'split': False,
            'rally': {'heroes': [None, None, None], 'ratio': None}, 'garrison': None, 'pet_buff': None,
            'named_joiners': [], 'other_joiner_heroes': {'rally': [], 'garrison': []}, 'extra_joiners': []}


def get_plan(api) -> dict:
    return api.call('GET', '/api/admin/svs/rounds/current/plan', admin=True)[1]


def where(api, fid):
    plan = get_plan(api)['plan']
    for ld in plan['leaders']:
        if (ld['player'] or {}).get('fid') == fid:
            return ('leader', ld['id'], None)
        for i, j in enumerate(ld['named_joiners']):
            if (j['player'] or {}).get('fid') == fid:
                return ('named', ld['id'], i)
        for i, e in enumerate(ld['extra_joiners']):
            if e['player'].get('fid') == fid:
                return ('extra', ld['id'], i)
    for g in plan['groups']:
        for p in g.get('players') or []:
            if p.get('fid') == fid:
                return ('group', g['id'], None)
    return None


def open_players(page: Page, base_url: str, api, query: str = '') -> None:
    ui.use_admin_token(page, base_url, api.token(), ui.admin_dashboard_url('svs') + query)
    expect(page.get_by_test_id('svs-table')).to_be_visible()
    page.wait_for_load_state('networkidle')


def open_menu(page: Page, fid: str):
    page.get_by_test_id(f'add-to-rally-{fid}').click()
    menu = page.get_by_test_id('add-to-rally')
    expect(menu).to_be_visible()
    return menu


def plan_cell(page: Page, fid: str):
    return page.get_by_test_id(f'plan-{fid}')


# ---------------------------------------------------------------- 0. no plan yet

def test_no_leaders_links_to_battle_plan(page: Page, base_url, api, shot):
    open_players(page, base_url, api)
    expect(plan_cell(page, FIDS[2])).to_have_text('—' + tr('svs:players.filter.notInPlan'))
    menu = open_menu(page, FIDS[2])
    expect(menu.get_by_test_id('add-no-leaders')).to_contain_text(tr('svs:players.add.noLeaders'))
    shot('no-leaders')
    page.keyboard.press('Escape')
    expect(menu).to_have_count(0)
    expect(page.get_by_test_id(f'add-to-rally-{FIDS[2]}')).to_be_focused()  # focus goes back to the trigger
    open_menu(page, FIDS[2]).get_by_test_id('add-open-plan').click()
    expect(page.get_by_test_id('svs-planner')).to_be_visible()

    # now the plan the rest of the module uses: Rally Caller 01 (main), a counter leader, Turrets
    plan = get_plan(api)
    doc = plan['plan']
    doc['groups'][0]['name'] = MAIN
    doc['groups'][1]['name'] = COUNTER
    doc['groups'].append({'id': 'tur', 'kind': 'extra', 'name': TUR, 'players': []})
    doc['leaders'] = [blank_leader('L1', doc['groups'][0]['id'], FIDS[0], ALIAS),
                      blank_leader('L2', doc['groups'][1]['id'], FIDS[1])]
    api.call('PUT', '/api/admin/svs/rounds/current/plan', {'revision': plan['revision'], 'plan': doc}, admin=True)


# ---------------------------------------------------------------- 1. add from the table, see it in the Battle plan

def test_add_to_leader_then_battle_plan(page: Page, base_url, api, shot):
    open_players(page, base_url, api)
    expect(plan_cell(page, FIDS[0])).to_have_text(tr('svs:players.place.leader', leader=ALIAS, group=MAIN))
    expect(plan_cell(page, FIDS[1])).to_have_text(tr('svs:players.place.leader', leader=NAMES[1], group=COUNTER))
    menu = open_menu(page, FIDS[2])
    expect(menu.get_by_test_id('rally-leader-L1')).to_contain_text(ALIAS)
    expect(menu.get_by_test_id('rally-leader-L1').get_by_test_id('leader-capacity')).to_have_text(
        tr('svs:players.add.capacity', named=0, extra=0, maxNamed=4, maxExtra=14))
    shot('menu-leaders')
    # keyboard: the first leader has the focus; Enter opens the choice, the default (named) is focused
    expect(menu.get_by_test_id('rally-leader-L1')).to_be_focused()
    page.keyboard.press('Enter')
    expect(menu.get_by_test_id('add-as-named')).to_have_attribute('data-default', 'true')
    expect(menu.get_by_test_id('add-as-named')).to_be_focused()
    shot('menu-mode')
    page.keyboard.press('Enter')
    expect(page.get_by_test_id('rally-result')).to_contain_text(NAMES[2])
    expect(menu).to_have_count(0)
    want = tr('svs:players.place.joiner', leader=ALIAS, group=MAIN, n=1)
    expect(plan_cell(page, FIDS[2])).to_have_text(want)
    assert where(api, FIDS[2]) == ('named', 'L1', 0)
    shot('after-add')

    page.get_by_test_id('tab-plan').click()
    card = page.locator(f'[data-testid=leader-card][data-name="{NAMES[0]}"]')
    expect(card.get_by_test_id('joiner-0')).to_have_attribute('data-name', NAMES[2])


# ---------------------------------------------------------------- 2. named places full -> extra

def test_named_full_goes_to_extra(page: Page, base_url, api):
    rev = get_plan(api)['revision']
    _, res = api.call('POST', '/api/admin/svs/rounds/current/plan/place',
                      {'fids': FIDS[3:7], 'as': 'named', 'leader_id': 'L2', 'expected_revision': rev}, admin=True)
    assert len(res['result']['placed']) == 4
    open_players(page, base_url, api)
    menu = open_menu(page, FIDS[7])
    expect(menu.get_by_test_id('rally-leader-L2').get_by_test_id('leader-capacity')).to_have_text(
        tr('svs:players.add.capacity', named=4, extra=0, maxNamed=4, maxExtra=14))
    menu.get_by_test_id('rally-leader-L2').click()
    expect(menu.get_by_test_id('add-as-named')).to_be_disabled()
    expect(menu.get_by_test_id('add-as-extra')).to_have_attribute('data-default', 'true')
    menu.get_by_test_id('add-as-extra').click()
    expect(plan_cell(page, FIDS[7])).to_have_text(tr('svs:players.place.extra', leader=NAMES[1], group=COUNTER))
    assert where(api, FIDS[7]) == ('extra', 'L2', 0)


# ---------------------------------------------------------------- 3. Move here

def test_move_here(page: Page, base_url, api, shot):
    open_players(page, base_url, api)
    menu = open_menu(page, FIDS[2])
    now = tr('svs:players.place.joiner', leader=ALIAS, group=MAIN, n=1)
    expect(menu.get_by_test_id('add-now')).to_have_text(tr('svs:players.add.now', where=now))
    menu.get_by_test_id('rally-leader-L2').click()
    btn = menu.get_by_test_id('add-as-extra')
    expect(btn).to_have_text(tr('svs:players.add.moveExtra', n=1, max=14))
    shot('move-here')
    btn.click()
    expect(page.get_by_test_id('rally-result')).to_contain_text(
        tr('svs:players.done.moved', name=NAMES[2],
           where=tr('svs:players.place.extra', leader=NAMES[1], group=COUNTER)))
    expect(plan_cell(page, FIDS[2])).to_have_text(tr('svs:players.place.extra', leader=NAMES[1], group=COUNTER))
    assert where(api, FIDS[2]) == ('extra', 'L2', 1)
    # moved, not copied: L1's named place is free again
    l1 = next(x for x in get_plan(api)['plan']['leaders'] if x['id'] == 'L1')
    assert all(j['player'] is None for j in l1['named_joiners'])
    # Move to Turrets from the "other places"
    menu = open_menu(page, FIDS[2])
    menu.get_by_test_id('to-group-tur').click()
    expect(plan_cell(page, FIDS[2])).to_have_text(tr('svs:players.place.group', group=TUR))
    assert where(api, FIDS[2]) == ('group', 'tur', None)


# ---------------------------------------------------------------- 4. bulk: 3 selected, one already placed

def test_bulk_add_reports_skipped(page: Page, base_url, api, shot):
    open_players(page, base_url, api)
    for fid in (FIDS[8], FIDS[9], FIDS[2]):  # FIDS[2] is in Turrets
        page.get_by_test_id(f'select-{fid}').click()
        expect(page.get_by_test_id(f'select-{fid}')).to_be_checked()
    bar = page.get_by_test_id('bulk-bar')
    expect(bar).to_be_visible()
    expect(page.get_by_test_id('bulk-add')).to_have_text(tr('svs:players.bulk.add', n=3))
    shot('bulk-bar')
    page.get_by_test_id('bulk-add').click()
    menu = page.get_by_test_id('add-to-rally')
    expect(menu.get_by_role('heading')).to_have_text(tr('svs:players.add.bulkTitle', n=3))
    menu.get_by_test_id('rally-leader-L1').click()
    expect(menu.get_by_test_id('bulk-auto')).to_have_text(tr('svs:players.add.bulkAuto', free=18))
    shot('bulk-menu')
    menu.get_by_test_id('bulk-auto').click()
    result = page.get_by_test_id('rally-result')
    expect(result).to_contain_text(tr('svs:players.done.bulk', n=2, to=ALIAS, named=2, extra=0))
    expect(result).to_contain_text(tr('svs:players.done.skipped', list=NAMES[2]))
    expect(bar).to_have_count(0)  # selection cleared
    assert where(api, FIDS[8])[:2] == ('named', 'L1') and where(api, FIDS[9])[:2] == ('named', 'L1')
    assert where(api, FIDS[2]) == ('group', 'tur', None)


def test_capacity_counts_follow_api_changes(page: Page, base_url, api):
    """Unknown FIDs in a bulk call are reported (not_found); the menu shows the leader's new numbers."""
    rev = get_plan(api)['revision']
    _, res = api.call('POST', '/api/admin/svs/rounds/current/plan/place',
                      {'fids': FIDS[10:16] + [str(BASE + 900 + i) for i in range(7)], 'as': 'extra',
                       'leader_id': 'L2', 'expected_revision': rev}, admin=True)
    assert len(res['result']['placed']) == 6 and len(res['result']['not_found']) == 7
    open_players(page, base_url, api)
    menu = open_menu(page, FIDS[0])
    expect(menu.get_by_test_id('rally-leader-L2').get_by_test_id('leader-capacity')).to_have_text(
        tr('svs:players.add.capacity', named=4, extra=7, maxNamed=4, maxExtra=14))  # FIDS[7] + 6


# ---------------------------------------------------------------- 5. Not in plan / In plan filter

def test_not_in_plan_filter(page: Page, base_url, api, shot):
    open_players(page, base_url, api)
    placed = {f for f in FIDS if where(api, f)}
    free = [f for f in FIDS if f not in placed]
    assert free, 'some players stay unplaced'
    chip = page.get_by_test_id('chip-in-plan-no')
    expect(chip.get_by_test_id('chip-count')).to_have_text(str(len(free)))
    chip.click()
    expect(page).to_have_url(re.compile(r'in_plan=no'))
    expect(page.get_by_test_id('filter-pill-in_plan')).to_have_text(tr('svs:players.filter.notInPlan'))
    expect(page.get_by_test_id('result-count')).to_contain_text(str(len(free)))
    for f in free:
        expect(page.get_by_test_id(f'player-row-{f}')).to_be_visible()
    for f in placed:
        expect(page.get_by_test_id(f'player-row-{f}')).to_have_count(0)
    shot('not-in-plan')
    page.get_by_test_id('chip-in-plan-yes').click()
    expect(page).to_have_url(re.compile(r'in_plan=yes'))
    for f in placed:
        expect(page.get_by_test_id(f'player-row-{f}')).to_be_visible()
    page.get_by_test_id('filter-pill-in_plan').click()
    expect(page).not_to_have_url(re.compile(r'in_plan='))


# ---------------------------------------------------------------- 6. revision conflict: re-read + one retry

def test_conflict_retries_once(page: Page, base_url, api):
    open_players(page, base_url, api, '&in_plan=no')
    fid = next(f for f in FIDS if not where(api, f))
    menu = open_menu(page, fid)
    menu.get_by_test_id('rally-leader-L1').click()
    expect(menu.get_by_test_id('add-as-named')).to_be_visible()
    # someone else saves an unrelated change meanwhile (the menu's revision is now stale)
    plan = get_plan(api)
    doc = plan['plan']
    next(x for x in doc['leaders'] if x['id'] == 'L2')['pet_buff'] = 'last_hour'
    api.call('PUT', '/api/admin/svs/rounds/current/plan', {'revision': plan['revision'], 'plan': doc}, admin=True)
    menu.get_by_test_id('add-as-named').click()
    expect(page.get_by_test_id('rally-result')).to_be_visible()
    assert where(api, fid)[:2] == ('named', 'L1')
    after = get_plan(api)
    assert after['revision'] == plan['revision'] + 2
    assert next(x for x in after['plan']['leaders'] if x['id'] == 'L2')['pet_buff'] == 'last_hour'  # not clobbered


def test_conflict_that_no_longer_applies(page: Page, base_url, api):
    open_players(page, base_url, api, '&in_plan=no')
    fid = next(f for f in FIDS if not where(api, f))
    menu = open_menu(page, fid)
    menu.get_by_test_id('rally-leader-L1').click()
    expect(menu.get_by_test_id('add-as-named')).to_be_visible()
    # meanwhile someone else puts this very player in Turrets: the choice no longer means the same thing
    rev = get_plan(api)['revision']
    api.call('POST', '/api/admin/svs/rounds/current/plan/place',
             {'fid': fid, 'as': 'group', 'group_id': 'tur', 'expected_revision': rev}, admin=True)
    menu.get_by_test_id('add-as-named').click()
    expect(menu.get_by_test_id('add-error')).to_have_text(tr('svs:players.err.conflict'))
    assert where(api, fid) == ('group', 'tur', None)
