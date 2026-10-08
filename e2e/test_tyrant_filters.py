"""Frost Dragon Tyrant admin filters (owner rules p2d): clickable camp/tier count chips, the troop filter bar
('All three, at least FC10, T11 only'), removable pills + Clear filters, filters in the URL (survive reload),
summary recomputed for the filtered set, filtered exports, no aggregate gem total, legacy pre-FC values shown
as stored. Desktop here; the phone version is in test_mobile.py.

Own round with players seeded through the public API (legacy pre-FC camps through the generic profile route).
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
BASE = 63_000_000 + secrets.randbelow(900_000)
F_BEST, F_LAN9, F_T10, F_OLD = (str(BASE + i) for i in range(4))
ROWS = '[data-testid^="player-row-"]'


def tr(key: str, lang: str = 'en', **v) -> str:
    return ui.tr(lang, key, **v)


def full(camp, tier):
    return {k: {'furnace_level': camp, 'tier': tier} for k in ('infantry', 'lancer', 'marksman')}


def seed_players(api: ui.Api) -> None:
    def put(fid, name, alliance, troops, answers):
        prof = {'game_name': name, 'alliance': alliance}
        if troops is not None:
            prof.update({'furnace_level': 'FC10', 'troops': troops, 'power': 500_000_000})
        api.call('PUT', f'/api/events/tyrant/current/application/{fid}', {'profile': prof, 'answers': answers})

    lan9 = full('FC10', 11)
    lan9['lancer'] = {'furnace_level': 'FC9', 'tier': 11}
    put(F_BEST, 'Best', 'AAA', full('FC10', 11), {'availability': ['w1'], 'discord_vc': True, 'gem_spend': 1000,
                                                     'roles': ['joiner']})
    put(F_LAN9, 'Lan9', 'BBB', lan9, {'availability': ['w2'], 'discord_vc': False, 'roles': ['rally_leader']})
    put(F_T10, 'Ten', 'AAA', full('FC10', 10), {'availability': ['w3'], 'discord_vc': True, 'gem_spend': 5000})
    # legacy: pre-FC camp levels stored before the rule (generic profile route), never re-sent
    api.call('PUT', f'/api/profile/{F_OLD}', {'game_name': 'Oldie', 'alliance': 'OLD', 'furnace_level': '27',
                                             'troops': full('25', 10)})
    put(F_OLD, 'Oldie', 'OLD', None, {'availability': ['w3']})


@pytest.fixture(scope='module', autouse=True)
def filter_round(api):
    _, res = api.call('POST', '/api/admin/events/tyrant/start-new-round', {'name': f'FDT filters {RUN}'}, admin=True)
    seed_players(api)
    return res['round']


def open_players(page: Page, base_url: str, api: ui.Api, query: str = '') -> None:
    ui.use_admin_token(page, base_url, api.token(), ui.admin_dashboard_url('tyrant') + query)
    expect(page.get_by_test_id('tyrant-table')).to_be_visible()
    page.wait_for_load_state('networkidle')


def count(page: Page, testid: str) -> str:
    return page.get_by_test_id(testid).get_by_test_id('chip-count').inner_text()


def test_summary_chips_filter_table_and_counts(page: Page, base_url, api, shot):
    open_players(page, base_url, api)
    expect(page.locator(ROWS)).to_have_count(4)
    expect(page.get_by_test_id('stat-total-value')).to_have_text('4')
    expect(page.get_by_test_id('stat-gems')).to_have_count(0)  # no aggregate gem total anywhere
    # camp level AND tier counts per troop type; legacy pre-FC shown as stored
    assert count(page, 'chip-infantry-camp-FC10') == '3' and count(page, 'chip-infantry-camp-25') == '1'
    assert count(page, 'chip-lancer-camp-FC9') == '1' and count(page, 'chip-marksman-tier-T11') == '2'
    assert page.get_by_test_id('chip-lancer-camp-FC10').bounding_box()['height'] >= 43.5
    expect(page.get_by_test_id(f'troop-summary-{F_OLD}')).to_contain_text('25 T10')
    shot('filters-none')

    # one chip: Lancer camp = FC9 -> table AND summary narrow, chip highlighted, pill appears
    page.get_by_test_id('chip-lancer-camp-FC9').click()
    expect(page.locator(ROWS)).to_have_count(1)
    expect(page.get_by_test_id(f'player-row-{F_LAN9}')).to_be_visible()
    expect(page.get_by_test_id('stat-total-value')).to_have_text('1')
    expect(page.get_by_test_id('chip-lancer-camp-FC9')).to_have_attribute('aria-pressed', 'true')
    assert count(page, 'chip-infantry-camp-FC10') == '1'
    expect(page.get_by_test_id('chip-infantry-camp-25')).to_have_count(0)
    expect(page.get_by_test_id('filter-pill-lancer_camp')).to_have_text(
        tr('tyrant:admin.pill.camp', troop=tr('tyrant:admin.troopName.lancer'), v='FC9'))
    assert 'lancer_camp=FC9' in page.url
    expect(page.get_by_test_id('result-count')).to_have_text(tr('tyrant:admin.showingOf', n=1, total=4))
    # a second chip combines with AND
    page.get_by_test_id('chip-marksman-tier-T11').click()
    expect(page.get_by_test_id('filter-pill-marksman_tier')).to_be_visible()
    expect(page.locator(ROWS)).to_have_count(1)
    shot('filters-two-chips')
    # remove the first pill -> only marksman T11 left (Best + Lan9)
    page.get_by_test_id('filter-pill-lancer_camp').click()
    expect(page.locator(ROWS)).to_have_count(2)
    expect(page.get_by_test_id('stat-total-value')).to_have_text('2')
    # tapping the active chip again removes its filter -> back to all
    page.get_by_test_id('chip-marksman-tier-T11').click()
    expect(page.get_by_test_id('filter-pills')).to_have_count(0)
    expect(page.locator(ROWS)).to_have_count(4)
    expect(page.get_by_test_id('stat-total-value')).to_have_text('4')


def test_bar_all_three_fc10_t11_url_reload_export(page: Page, base_url, api, shot):
    open_players(page, base_url, api)
    page.get_by_test_id('filter-troop').select_option('')          # All three
    page.get_by_test_id('filter-min-camp').select_option('FC10')
    values = page.get_by_test_id('filter-min-camp').locator('option').evaluate_all('os => os.map(o => o.value)')
    assert values == [''] + [f'FC{n}' for n in range(10, 0, -1)]
    page.get_by_test_id('filter-min-tier').select_option('11')     # T11 only
    expect(page.locator(ROWS)).to_have_count(1)
    expect(page.get_by_test_id(f'player-row-{F_BEST}')).to_be_visible()
    expect(page.get_by_test_id('filter-pill-min_camp')).to_have_text(
        tr('tyrant:admin.pill.minCamp', troop=tr('tyrant:admin.troopName.all'), v='FC10'))
    expect(page.get_by_test_id('filter-pill-min_tier')).to_be_visible()
    assert 'min_camp=FC10' in page.url and 'min_tier=11' in page.url
    # the filtered view survives a reload (and could be shared)
    page.reload()
    page.wait_for_load_state('networkidle')
    expect(page.locator(ROWS)).to_have_count(1)
    expect(page.get_by_test_id('filter-min-camp')).to_have_value('FC10')
    expect(page.get_by_test_id('filter-min-tier')).to_have_value('11')
    expect(page.get_by_test_id('stat-total-value')).to_have_text('1')
    expect(page.get_by_test_id('export-filtered-note')).to_be_visible()
    shot('filters-fc10-t11')
    with page.expect_download() as dl:
        page.get_by_test_id('export-csv').click()
    rows = list(csv.reader(io.StringIO(open(dl.value.path(), encoding='utf-8-sig').read())))
    assert [r[0] for r in rows[1:]] == [F_BEST]
    head = rows[0]
    assert 'Infantry Camp Level' in head and 'Marksman Tier' in head and 'Joiner Strength' in head
    assert dict(zip(head, rows[1]))['Joiner Strength'] == '63'
    # Marksman only: FC10 marksman camps with T11 marksmen (Best and Lan9, whose FC9 camp is a lancer camp)
    page.get_by_test_id('filter-troop').select_option('marksman')
    expect(page.locator(ROWS)).to_have_count(2)
    page.get_by_test_id('clear-filters').click()
    expect(page.locator(ROWS)).to_have_count(4)
    assert 'min_camp' not in page.url and 'event=tyrant' in page.url


def test_more_filters_windows_and_strength_sort(page: Page, base_url, api):
    open_players(page, base_url, api, '&rush=1')
    expect(page.locator(ROWS)).to_have_count(1)                     # only Best picked the opening rush
    expect(page.get_by_test_id('filter-pill-rush')).to_be_visible()
    page.get_by_test_id('clear-filters').click()
    page.get_by_test_id('filter-more').click()
    expect(page.get_by_test_id('more-filters')).to_be_visible()
    page.get_by_test_id('filter-vc').select_option('yes')
    expect(page.locator(ROWS)).to_have_count(2)
    page.get_by_test_id('filter-min-gems').fill('2000')
    expect(page.locator(ROWS)).to_have_count(1)
    expect(page.get_by_test_id(f'player-row-{F_T10}')).to_be_visible()
    page.get_by_test_id('clear-filters').click()
    page.get_by_test_id('roles-filter').click()
    page.get_by_test_id('roles-filter-option-rally_leader').click()
    page.keyboard.press('Escape')
    expect(page.locator(ROWS)).to_have_count(1)
    page.get_by_test_id('clear-filters').click()
    # joiner strength sort: Best (63) first, legacy pre-FC camps (0 + tiers) last
    page.get_by_test_id('sort-strength').click()
    expect(page.locator(ROWS).first).to_have_attribute('data-testid', f'player-row-{F_BEST}')
    expect(page.locator(ROWS).last).to_have_attribute('data-testid', f'player-row-{F_OLD}')
    expect(page.get_by_test_id(f'player-row-{F_BEST}').get_by_test_id('strength')).to_have_text('63')


def test_filters_in_arabic_no_raw_keys(page: Page, base_url, api, shot):
    open_players(page, base_url, api, '&infantry_camp=FC10&min_tier=10')
    ui.switch_language(page, 'ar')
    assert page.evaluate('document.documentElement.dir') == 'rtl'
    expect(page.locator(ROWS)).to_have_count(3)
    page.get_by_test_id('filter-more').click()
    bad = ui.check_all_languages(page, 'tyrant-admin-filters', shot)
    ui.switch_language(page, 'en')
    assert not bad, bad
