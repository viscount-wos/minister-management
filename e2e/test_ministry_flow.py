"""Ministry happy path through the UI against the v2 API (profiles / rounds / applications).

home tiles -> ministry -> apply; new application (en + ar); edit via FID; admin sees it;
admin "Start new round" -> the same FID gets "New application" and "Use my last answers"
copies the previous round's answers.

Tests run in file order and share STATE; later tests skip if an earlier step failed.
Each run uses fresh FIDs (time-based), so it is safe to re-run against the same container.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

import ui
from ui import en

_STAMP = str(int(time.time()))[-8:]
STATE: dict = {
    'fid': f'7{_STAMP}1',
    'name': f'E2E Chief ✨ {_STAMP}',
    'fid_ar': f'7{_STAMP}2',
    'name_ar': f'اختبار E2E {_STAMP}',
}


def test_home_tile_to_ministry_to_apply(page: Page, base_url, shot, api):
    rnd = api.current_round()
    ui.go(page, base_url, 'home')
    tile = page.get_by_test_id('event-tile-ministry')
    expect(tile).to_contain_text(en('ministry:event.name'))
    expect(tile).to_contain_text(en('common:home.status.open'))
    tile.click()
    page.wait_for_url('**/ministry')
    expect(page.get_by_test_id('current-round')).to_have_text(en('ministry:home.currentRound', round=rnd['name']))
    shot('ministry-home')
    page.get_by_test_id('ministry-apply-tile').click()
    page.wait_for_url('**/ministry/apply')
    expect(page.get_by_test_id('round-name')).to_have_text(rnd['name'])
    expect(page.get_by_label(en('profile:playerID'))).to_be_visible()      # label linked to input
    shot('apply-lookup')


def test_fid_must_be_digits(page: Page, base_url):
    ui.enter_fid(page, base_url, 'abc123')
    expect(page.get_by_test_id('fid-error')).to_have_text(en('profile:fidDigitsOnly'))
    expect(page.get_by_test_id('profile-fields')).to_have_count(0)


def test_new_application_en(page: Page, base_url, shot, api, accept_dialogs):
    rnd = api.current_round()
    assert ui.open_application(page, base_url, STATE['fid']) == 'new'
    expect(page.get_by_test_id('application-heading')).to_have_text(
        en('ministry:apply.newFor', round=rnd['name']))
    expect(page.get_by_test_id('profile-status')).to_have_text(en('profile:newProfile'))
    expect(page.get_by_test_id('use-last-answers')).to_have_count(0)      # never applied before
    expect(page.get_by_test_id('profile-fid')).to_have_value(STATE['fid'])

    # labels are linked: find the name field by its label text
    page.get_by_label(en('profile:gameName')).fill(STATE['name'])
    page.get_by_test_id('profile-alliance').fill('e2e')
    expect(page.get_by_test_id('profile-alliance')).to_have_value('E2E')  # upper-cased, max 3
    ui.fill_answers(page, construction='12.5', research='3', troop='100')
    ui.pick_slots(page, {'construction': ['12:00', '13:00'], 'troop': ['20:00']})
    shot('filled')
    ui.save_application(page)
    expect(page.get_by_test_id('save-success')).to_contain_text(en('ministry:form.success'))
    expect(page.get_by_test_id('save-success')).to_contain_text(en('ministry:apply.savedNew', round=rnd['name']))
    shot('success')

    app = api.application(STATE['fid'])
    assert app['answers']['construction_speedups_days'] == 12.5
    assert app['answers']['time_slots_by_day'] == {
        'construction': ['12:00', '13:00'], 'research': [], 'troop': ['20:00']}
    assert app['profile_snapshot']['alliance'] == 'E2E'
    STATE['submitted'] = True


def test_edit_via_fid(page: Page, base_url, shot, api, accept_dialogs):
    if not STATE.get('submitted'):
        pytest.skip('submission failed')
    rnd = api.current_round()
    assert ui.open_application(page, base_url, STATE['fid']) == 'edit'
    expect(page.get_by_test_id('application-heading')).to_have_text(
        en('ministry:apply.editFor', round=rnd['name']))
    expect(page.get_by_test_id('profile-status')).to_have_text(en('profile:prefilled'))
    expect(page.get_by_test_id('profile-game-name')).to_have_value(STATE['name'])
    expect(page.get_by_test_id('profile-alliance')).to_have_value('E2E')
    expect(page.get_by_test_id(ui.ANSWER['construction'])).to_have_value('12.5')
    ui.expect_slots(page, {'construction': ['12:00', '13:00'], 'troop': ['20:00']})
    expect(page.get_by_test_id('my-assignments')).to_be_visible()
    shot('loaded')

    page.get_by_test_id(ui.ANSWER['construction']).fill('42.5')
    ui.pick_slots(page, {'research': ['01:00']})
    shot('edited')
    page.get_by_test_id('save-application').click()
    expect(page.get_by_test_id('save-success')).to_contain_text(en('ministry:apply.savedEdit', round=rnd['name']))

    # reload from scratch and prove the edit persisted
    assert ui.open_application(page, base_url, STATE['fid']) == 'edit'
    expect(page.get_by_test_id(ui.ANSWER['construction'])).to_have_value('42.5')
    expect(page.get_by_test_id(ui.ANSWER['research'])).to_have_value('3')
    ui.expect_slots(page, {'research': ['01:00']})
    STATE['edited'] = True
    shot('reloaded')


def test_new_application_ar_rtl(page: Page, base_url, shot, api, accept_dialogs):
    """Full new application with the UI in Arabic (strings checked in Arabic, not English)."""
    rnd = api.current_round()
    ui.go(page, base_url, 'apply')
    ui.switch_language(page, 'ar')
    assert page.evaluate('document.documentElement.dir') == 'rtl'
    expect(page.get_by_test_id('fid-input')).to_have_attribute(
        'placeholder', ui.tr('ar', 'profile:playerIDPlaceholder'))
    page.get_by_test_id('fid-input').fill(STATE['fid_ar'])
    page.get_by_test_id('fid-continue').click()
    expect(page.get_by_test_id('application-heading')).to_have_text(
        ui.tr('ar', 'ministry:apply.newFor', round=rnd['name']))
    ui.fill_profile(page, STATE['name_ar'], 'LOV')
    ui.fill_answers(page, construction='1')
    ui.pick_slots(page, {'construction': ['00:00']})
    shot('ar-form')
    page.get_by_test_id('save-application').click()
    expect(page.get_by_test_id('save-success')).to_contain_text(ui.tr('ar', 'ministry:form.success'))
    assert page.evaluate('document.documentElement.dir') == 'rtl'
    shot('ar-success')
    STATE['submitted_ar'] = True


def test_admin_sees_application(page: Page, base_url, admin_password, shot, api):
    if not STATE.get('submitted'):
        pytest.skip('submission failed')
    rnd = api.current_round()
    ui.admin_login(page, base_url, admin_password)
    expect(page.get_by_test_id('round-select')).to_have_value(str(rnd['id']))   # current round by default
    expect(page.get_by_test_id('round-status')).to_have_attribute('data-status', 'open')
    search = page.get_by_label(en('admin:search'))
    search.fill(STATE['fid'])
    row = page.get_by_test_id(f'player-row-{STATE["fid"]}')
    expect(row).to_contain_text(STATE['name'])
    expect(row).to_contain_text('[E2E]')
    expect(page.get_by_role('row').filter(has_text=STATE['fid'])).to_have_count(1)
    shot('admin-row')
    if STATE.get('submitted_ar'):
        search.fill(STATE['fid_ar'])
        expect(page.get_by_test_id(f'player-row-{STATE["fid_ar"]}')).to_contain_text(STATE['name_ar'])
    search.fill('')
    shot('admin-table')


def test_admin_wrong_password_rejected(page: Page, base_url, shot):
    ui.go(page, base_url, 'admin_login')
    page.get_by_label(en('admin:password')).fill('definitely-not-the-password')
    page.get_by_test_id('admin-login').click()
    expect(page.get_by_test_id('login-error')).to_have_text(en('admin:invalidPassword'))
    expect(page).not_to_have_url(base_url + ui.ROUTES['admin_dashboard'])
    shot('admin-bad-password')


def test_admin_forged_token_goes_back_to_login(page: Page, base_url, shot):
    """The old literal v1.4 token is rejected (401) and the UI returns cleanly to login."""
    ui.go(page, base_url, 'admin_login')
    page.evaluate("localStorage.setItem('adminToken', 'admin-token')")
    page.goto(base_url + ui.ROUTES['admin_dashboard'])
    page.wait_for_url('**/admin?expired=1')
    expect(page.get_by_test_id('session-expired')).to_have_text(en('admin:sessionExpired'))
    assert page.evaluate("localStorage.getItem('adminToken')") is None
    shot('expired')


def test_start_new_round_then_use_last_answers(page: Page, base_url, admin_password, shot, api,
                                                accept_dialogs):
    if not STATE.get('edited'):
        pytest.skip('edit step failed')
    old = api.current_round()
    new_name = f'E2E round 2 {_STAMP}'

    # --- admin: Start new round (confirm dialog), old round becomes read-only
    ui.admin_login(page, base_url, admin_password)
    page.get_by_test_id('start-new-round').click()
    dialog = page.get_by_test_id('new-round-dialog')
    expect(dialog).to_be_visible()
    expect(page.get_by_test_id('new-round-warning')).to_contain_text(old['name'])
    shot('confirm-dialog')
    page.get_by_test_id('cancel-new-round').click()                     # cancel really cancels
    expect(dialog).to_have_count(0)
    assert api.current_round()['id'] == old['id']

    page.get_by_test_id('start-new-round').click()
    page.get_by_label(en('admin:round.name')).fill(new_name)
    page.get_by_test_id('confirm-new-round').click()
    expect(dialog).to_have_count(0)
    new = api.current_round()
    assert new['name'] == new_name and new['id'] != old['id']
    select = page.get_by_test_id('round-select')
    expect(select).to_have_value(str(new['id']))
    expect(page.get_by_test_id('players-total')).to_contain_text(': 0')
    shot('new-round')

    select.select_option(str(old['id']))
    expect(page.get_by_test_id('read-only-banner')).to_be_visible()
    expect(page.get_by_test_id(f'player-row-{STATE["fid"]}')).to_be_visible()    # nothing deleted
    expect(page.get_by_test_id(f'edit-{STATE["fid"]}')).to_have_count(0)        # read-only
    page.get_by_test_id('tab-settings').click()
    expect(page.get_by_test_id('closing-time')).to_be_disabled()
    shot('old-round-read-only')

    # --- player: same FID now gets a NEW application with blank answers
    assert ui.open_application(page, base_url, STATE['fid']) == 'new'
    expect(page.get_by_test_id('application-heading')).to_have_text(en('ministry:apply.newFor', round=new_name))
    expect(page.get_by_test_id('profile-game-name')).to_have_value(STATE['name'])     # profile pre-fills
    expect(page.get_by_test_id('profile-alliance')).to_have_value('E2E')
    expect(page.get_by_test_id(ui.ANSWER['construction'])).to_have_value('')          # answers blank
    expect(ui.day_tab(page, 'construction')).to_be_visible()
    expect(ui.slot(page, 'construction', '12:00')).to_have_attribute('aria-pressed', 'false')
    expect(page.get_by_test_id('last-answers-applied')).to_have_count(0)
    shot('new-round-blank')

    page.get_by_test_id('use-last-answers').click()
    applied = page.get_by_test_id('last-answers-applied')
    expect(applied).to_have_text(en('profile:lastAnswers.applied', round=old['name']))
    expect(page.get_by_test_id(ui.ANSWER['construction'])).to_have_value('42.5')
    expect(page.get_by_test_id(ui.ANSWER['research'])).to_have_value('3')
    expect(page.get_by_test_id(ui.ANSWER['troop'])).to_have_value('100')
    ui.expect_slots(page, {'construction': ['12:00', '13:00'], 'research': ['01:00'], 'troop': ['20:00']})
    shot('last-answers-applied')

    bad = ui.check_all_languages(page, 'last-answers', shot)
    assert not bad, f'raw i18n keys on the use-last-answers form: {bad}'
    ui.switch_language(page, 'ar')
    expect(page.get_by_test_id('last-answers-applied')).to_have_text(
        ui.tr('ar', 'profile:lastAnswers.applied', round=old['name']))
    shot('last-answers-ar')
    ui.switch_language(page, 'en')

    ui.save_application(page)
    app = api.application(STATE['fid'])
    assert app['round_id'] == new['id']
    assert app['answers']['construction_speedups_days'] == 42.5
    assert app['answers']['time_slots_by_day']['research'] == ['01:00']


def test_admin_assign_publish_export_and_player_sees_schedule(page: Page, base_url, admin_password, shot,
                                                             api):
    """Round-scoped admin endpoints: auto-assign, lock (assignment save), publish, xlsx + json export;
    the player then sees the published schedule and their own slot from the current round."""
    if not STATE.get('edited'):
        pytest.skip('edit step failed')
    rnd = api.current_round()
    fid = STATE['fid']
    ui.admin_login(page, base_url, admin_password)
    page.get_by_test_id('tab-assignments').click()
    page.get_by_test_id('assign-day-monday').click()
    page.get_by_test_id('auto-assign').click()
    card = page.get_by_test_id(f'card-{fid}')
    expect(card).to_be_visible()
    card.get_by_role('button', name=en('admin:clickToLock')).click()        # saves the day (PUT)
    expect(card.get_by_role('button', name=en('admin:clickToUnlock'))).to_be_visible()
    page.wait_for_load_state('networkidle')
    _, day = api.call('GET', f'/api/admin/ministry/rounds/{rnd["id"]}/assignments/monday', admin=True)
    placed = {s: c[0] for s, c in day['assignments'].items() if c and c[0]['fid'] == fid}
    assert len(placed) == 1, day
    slot_id, placed_card = next(iter(placed.items()))
    mins = int(slot_id[:2]) * 60 + int(slot_id[3:5])                        # ±20 min of a chosen hour
    assert placed_card['is_sticky'] is True and any(abs(mins - h * 60) <= 20 for h in (12, 13)), slot_id
    page.get_by_test_id('publish').click()
    expect(page.get_by_test_id('unpublish')).to_be_visible()
    assert api.current_round()['settings']['published_days'] == ['monday']
    with page.expect_download() as dl:
        page.get_by_test_id('export-excel').click()
    assert dl.value.suggested_filename.endswith('.xlsx')
    assert Path(dl.value.path()).read_bytes()[:2] == b'PK'                  # a real xlsx (zip)
    page.get_by_test_id('tab-players').click()
    with page.expect_download() as dl:
        page.get_by_test_id('export-json').click()
    data = json.loads(Path(dl.value.path()).read_text())
    assert data['round']['id'] == rnd['id'] and any(p['fid'] == fid for p in data['players'])
    shot('assigned-published')

    # player side: published schedule link + page, and their own assignment
    ui.go(page, base_url, 'ministry')
    page.get_by_test_id('schedule-link-monday').click()
    page.wait_for_url('**/ministry/schedule/monday')
    expect(page.get_by_text(STATE['name'])).to_be_visible()
    shot('public-schedule')
    assert ui.open_application(page, base_url, fid) == 'edit'
    expect(page.get_by_test_id('my-assignments-monday')).to_contain_text(slot_id)
    shot('my-assignment')
    ui.switch_language(page, 'ar')
    shot('my-assignment-ar')


def test_legacy_urls_redirect(page: Page, base_url):
    for old, new in ui.LEGACY_REDIRECTS.items():
        page.goto(base_url + old)
        page.wait_for_url(f'**{new}')
        assert page.url.endswith(new), (old, page.url)
