"""Round states the player can meet: closing time passed, and no open round at all.

Runs last (file order) and always restores an open round, so other files can rely on one.
"""
from __future__ import annotations

import time

import pytest
from playwright.sync_api import Page, expect

import ui
from ui import en

_STAMP = str(int(time.time()))[-8:]
PAST = '2020-01-01T00:00:00Z'


@pytest.fixture
def round_closed_for_new(api):
    """Current round with its closing time in the past; restored afterwards."""
    rnd = api.current_round()
    existing = f'98{_STAMP}01'
    api.put_application(existing, 'E2E before closing', 'CLS', {'construction_speedups_days': 5})
    api.update_round(rnd['id'], closing_time=PAST)
    yield {'round': rnd, 'existing_fid': existing}
    api.update_round(rnd['id'], closing_time=rnd['closing_time'])


def test_closing_time_blocks_new_but_allows_edit(page: Page, base_url, shot, api, round_closed_for_new):
    rnd = round_closed_for_new['round']

    ui.go(page, base_url, 'ministry')
    expect(page.get_by_text(en('ministry:home.applicationsClosed'))).to_be_visible()
    expect(page.get_by_test_id('ministry-apply-tile')).to_contain_text(en('ministry:home.applyTileClosedDesc'))
    shot('ministry-home-closed')

    # a NEW player is told applications are closed
    assert ui.open_application(page, base_url, f'98{_STAMP}02') == 'closed'
    expect(page.get_by_test_id('applications-closed')).to_contain_text(
        en('ministry:apply.closedBody', round=rnd['name']))
    shot('new-player-closed')
    bad = ui.check_all_languages(page, 'closed', shot)
    assert not bad, f'raw i18n keys on the closed state: {bad}'
    ui.switch_language(page, 'ar')
    expect(page.get_by_test_id('applications-closed')).to_contain_text(
        ui.tr('ar', 'ministry:apply.closedBody', round=rnd['name']))
    shot('new-player-closed-ar')
    ui.switch_language(page, 'en')

    # an EXISTING application stays editable, with the closing message shown
    assert ui.open_application(page, base_url, round_closed_for_new['existing_fid']) == 'edit'
    expect(page.get_by_test_id('closing-note')).to_have_text(en('ministry:apply.closedButEditable'))
    page.get_by_test_id(ui.ANSWER['construction']).fill('6')
    page.on('dialog', lambda d: d.accept())
    ui.save_application(page)
    assert api.application(round_closed_for_new['existing_fid'])['answers']['construction_speedups_days'] == 6
    shot('existing-edit-after-close')


def test_closing_time_passes_while_filling(page: Page, base_url, api):
    """Form opened before the deadline, saved after it: 403 APPLICATIONS_CLOSED -> closed state."""
    rnd = api.current_round()
    assert ui.open_application(page, base_url, f'98{_STAMP}03') == 'new'
    api.update_round(rnd['id'], closing_time=PAST)
    try:
        ui.fill_profile(page, 'E2E too late', 'LTE')
        ui.fill_answers(page, construction='1')
        ui.pick_slots(page, {'construction': ['05:00']})
        page.get_by_test_id('save-application').click()
        expect(page.get_by_test_id('applications-closed')).to_be_visible()
        assert api.application(f'98{_STAMP}03') is None
    finally:
        api.update_round(rnd['id'], closing_time=rnd['closing_time'])


def test_admin_round_settings(page: Page, base_url, admin_password, shot, api):
    """Per-round settings in the admin UI: research day, fire crystals, slot scheme, closing time."""
    rnd = api.current_round()
    api.update_round(rnd['id'], closing_time=None, settings={       # known starting point
        'research_day': 'tuesday', 'show_fire_crystals': False, 'time_slot_scheme': 'exact_alignment'})
    ui.admin_login(page, base_url, admin_password)
    page.get_by_test_id('tab-settings').click()
    expect(page.get_by_test_id('round-settings-title')).to_have_text(en('admin:round.settingsFor', round=rnd['name']))

    toggle = page.get_by_test_id('research-day-toggle')
    toggle.click()
    expect(toggle).to_have_attribute('data-value', 'friday')
    assert api.current_round()['settings']['research_day'] == 'friday'
    page.get_by_test_id('tab-assignments').click()
    expect(page.get_by_test_id('assign-day-friday')).to_be_visible()
    page.get_by_test_id('tab-settings').click()
    page.get_by_test_id('research-day-toggle').click()
    expect(page.get_by_test_id('research-day-toggle')).to_have_attribute('data-value', 'tuesday')

    page.get_by_test_id('show-fire-crystals').click()          # controlled: state follows the API reply
    expect(page.get_by_test_id('show-fire-crystals')).to_be_checked()
    assert api.current_round()['settings']['show_fire_crystals'] is True

    page.get_by_test_id('scheme-max_slots').click()
    remapped_prefix = en('admin:round.remapped', n='#').split('#')[0].strip()
    expect(page.get_by_test_id('settings-saved')).to_contain_text(remapped_prefix)
    assert api.current_round()['settings']['time_slot_scheme'] == 'max_slots'
    page.get_by_test_id('scheme-exact_alignment').click()
    expect(page.get_by_test_id('scheme-exact_alignment')).to_have_attribute('aria-pressed', 'true')

    page.get_by_label(en('admin:closingTime')).fill('2099-12-31T18:00')
    page.get_by_test_id('save-closing-time').click()
    expect(page.get_by_test_id('closing-time-status')).to_contain_text(en('admin:currentClosingTime'))
    assert api.current_round()['closing_time'].startswith('2099-12-31')
    shot('settings')

    # player side follows the round's settings
    assert ui.open_application(page, base_url, f'98{_STAMP}04') == 'new'
    expect(page.get_by_test_id('answer-fire_crystals')).to_be_visible()
    expect(page.get_by_test_id('closing-note')).to_be_visible()

    ui.admin_login(page, base_url, admin_password)
    page.get_by_test_id('tab-settings').click()
    page.get_by_test_id('clear-closing-time').click()
    expect(page.get_by_test_id('closing-time-status')).to_have_text(en('admin:noClosingTime'))
    page.get_by_test_id('show-fire-crystals').click()
    expect(page.get_by_test_id('show-fire-crystals')).not_to_be_checked()
    after = api.current_round()
    assert after['closing_time'] is None and after['settings']['show_fire_crystals'] is False


def test_no_open_round(page: Page, base_url, shot, api):
    rnd = api.current_round()
    api.update_round(rnd['id'], status='closed')
    try:
        ui.go(page, base_url, 'home')
        expect(page.get_by_test_id('event-tile-ministry')).to_contain_text(en('common:home.status.notOpen'))
        ui.go(page, base_url, 'ministry')
        expect(page.get_by_test_id('no-round-banner')).to_have_text(en('ministry:apply.notOpenBody'))
        expect(page.get_by_test_id('ministry-apply-tile')).to_be_disabled()
        shot('ministry-home-no-round')

        ui.go(page, base_url, 'apply')
        expect(page.get_by_test_id('no-round')).to_contain_text(en('ministry:apply.notOpenTitle'))
        shot('apply-no-round')
        bad = ui.check_all_languages(page, 'no-round', shot)
        assert not bad, f'raw i18n keys on the no-round state: {bad}'
        ui.switch_language(page, 'ar')
        assert page.evaluate('document.documentElement.dir') == 'rtl'
        expect(page.get_by_test_id('no-round')).to_contain_text(ui.tr('ar', 'ministry:apply.notOpenTitle'))
        shot('apply-no-round-ar')
    finally:
        # leave the stack with an open round again (the old one stays closed, as after start-new-round)
        api.start_new_round(f'E2E round restored {_STAMP}')
