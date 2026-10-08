"""Ministry happy path through the UI: apply (en + ar), duplicate guard, edit via FID, admin sees it.

Tests run in file order and share STATE; later tests skip if the submission failed.
Each run uses fresh FIDs (time-based), so it is safe to re-run against the same container.
"""
from __future__ import annotations

import time

import pytest
from playwright.sync_api import Page, expect

import ui

_STAMP = str(int(time.time()))[-8:]
STATE = {
    'fid': f'7{_STAMP}1',
    'name': f'E2E Chief ✨ {_STAMP}',
    'fid_ar': f'7{_STAMP}2',
    'name_ar': f'اختبار E2E {_STAMP}',
    'submitted': False,
}
EN = ui.STRINGS['en']


def _next(page: Page, lang='en'):
    page.get_by_role('button', name=ui.STRINGS[lang]['form.next'], exact=True).click()


def test_submit_application_en(page: Page, base_url, shot, accept_dialogs):
    ui.go(page, base_url, 'home')
    page.get_by_role('button', name=EN['home.submitNew']).click()
    expect(page.get_by_placeholder(EN['form.playerIDPlaceholder'])).to_be_visible()

    ui.fill_apply_step1(page, STATE['fid'], STATE['name'], 'e2e',
                        construction='12.5', research='3', troop='100')
    expect(page.locator(ui.FIELD['alliance'])).to_have_value('E2E')   # upper-cased, max 3
    shot('step1')
    _next(page)                                                      # -> construction times
    ui.time_slot_button(page, '12:00').click()
    ui.time_slot_button(page, '13:00').click()
    shot('step2-construction')
    _next(page)                                                      # -> research times
    _next(page)                                                      # none -> confirm() accepted
    ui.time_slot_button(page, '20:00').click()                       # troop
    _next(page)                                                      # -> review
    expect(page.get_by_text(STATE['name'])).to_be_visible()
    expect(page.get_by_text(STATE['fid'], exact=True)).to_be_visible()
    shot('review')
    page.get_by_role('button', name=EN['form.submit'], exact=True).click()
    expect(page.get_by_text(EN['form.success'])).to_be_visible()
    shot('success')
    STATE['submitted'] = True


def test_duplicate_fid_is_refused(page: Page, base_url, shot):
    if not STATE['submitted']:
        pytest.skip('submission failed')
    ui.go(page, base_url, 'apply')
    ui.fill_apply_step1(page, STATE['fid'], 'Someone Else', 'XYZ')
    _next(page)
    expect(page.get_by_text(EN['form.playerAlreadyExists'])).to_be_visible()
    expect(page.locator(ui.FIELD['fid'])).to_be_visible()            # still on step 1
    shot('duplicate-warning')


def test_reopen_by_fid_and_edit(page: Page, base_url, shot, accept_dialogs):
    if not STATE['submitted']:
        pytest.skip('submission failed')
    ui.go(page, base_url, 'home')
    page.get_by_role('button', name=EN['home.updateExisting']).click()
    page.get_by_placeholder(EN['update.fidLabel']).fill(STATE['fid'])
    page.get_by_role('button', name=EN['update.load']).click()

    name = page.locator(ui.FIELD['game_name'])
    expect(name).to_have_value(STATE['name'])
    expect(page.locator(ui.FIELD['construction'])).to_have_value('12.5')
    expect(page.locator(ui.FIELD['alliance'])).to_have_value('E2E')
    shot('loaded')

    page.locator(ui.FIELD['construction']).fill('42.5')
    page.get_by_role('button', name=EN['research_tab']).click()
    ui.time_slot_button(page, '01:00').click()
    shot('edited')
    page.get_by_role('button', name=EN['form.update'], exact=True).click()
    expect(page.get_by_text(EN['form.success'])).to_be_visible()

    # reload from scratch and prove the edit persisted
    ui.go(page, base_url, 'update')
    page.get_by_placeholder(EN['update.fidLabel']).fill(STATE['fid'])
    page.get_by_role('button', name=EN['update.load']).click()
    expect(page.locator(ui.FIELD['construction'])).to_have_value('42.5')
    expect(page.locator(ui.FIELD['research'])).to_have_value('3')
    STATE['edited'] = True
    shot('reloaded')


def test_submit_application_ar_rtl(page: Page, base_url, shot, accept_dialogs):
    """Full submission with the UI in Arabic (labels looked up in Arabic, not English)."""
    ui.go(page, base_url, 'apply')
    ui.switch_language(page, 'ar')
    assert page.evaluate('document.documentElement.dir') == 'rtl'
    expect(page.get_by_placeholder(ui.STRINGS['ar']['form.playerIDPlaceholder'])).to_be_visible()
    ui.fill_apply_step1(page, STATE['fid_ar'], STATE['name_ar'], 'LOV', construction='1')
    shot('ar-step1')
    _next(page, 'ar')
    ui.time_slot_button(page, '00:00').click()
    _next(page, 'ar')
    _next(page, 'ar')
    _next(page, 'ar')
    expect(page.get_by_text(STATE['name_ar'])).to_be_visible()
    shot('ar-review')
    page.get_by_role('button', name=ui.STRINGS['ar']['form.submit'], exact=True).click()
    expect(page.get_by_text(ui.STRINGS['ar']['form.success'])).to_be_visible()
    assert page.evaluate('document.documentElement.dir') == 'rtl'
    shot('ar-success')
    STATE['submitted_ar'] = True


def test_admin_sees_players(page: Page, base_url, admin_password, shot):
    if not STATE['submitted']:
        pytest.skip('submission failed')
    ui.admin_login(page, base_url, admin_password)
    search = page.get_by_placeholder(EN['admin.search'])
    search.fill(STATE['fid'])
    row = page.get_by_role('row').filter(has_text=STATE['fid'])
    expect(row).to_have_count(1)
    expect(row).to_contain_text(STATE['name'])
    expect(row).to_contain_text('E2E')
    shot('admin-row')
    if STATE.get('submitted_ar'):
        search.fill(STATE['fid_ar'])
        expect(page.get_by_role('row').filter(has_text=STATE['fid_ar'])).to_contain_text(
            STATE['name_ar'])
    search.fill('')
    shot('admin-table')


def test_admin_wrong_password_rejected(page: Page, base_url, shot):
    ui.go(page, base_url, 'admin_login')
    page.locator(ui.FIELD['admin_password']).fill('definitely-not-the-password')
    page.get_by_role('button', name=EN['admin.login'], exact=True).click()
    page.wait_for_load_state('networkidle')
    expect(page).not_to_have_url(base_url + ui.ROUTES['admin_dashboard'])
    shot('admin-bad-password')
