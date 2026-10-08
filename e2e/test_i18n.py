"""Home loads; every language renders without raw i18n keys on every page and state; Arabic is RTL."""
from __future__ import annotations

import time

import pytest
from playwright.sync_api import Page, expect

import ui

NON_EN = [c for c in ui.LANGUAGES if c != 'en']
_STAMP = str(int(time.time()))[-8:]


def test_raw_key_detector_itself():
    text = ('Hello form.next and ministry.apply.title here; visit example.com, e.g. ABC, '
            'v1.4.0, 23:50+, 12.5 days, {{count}} slots, https://x.y/a.b, profile:lastAnswers.hint')
    assert ui.raw_i18n_keys(text) == ['form.next', 'lastAnswers.hint', 'ministry.apply.title',
                                      'profile:lastAnswers.hint', '{{count}}']


def test_raw_key_detector_on_live_page(page: Page, base_url):
    """Prove the page-text collector really sees a rendered raw key (and placeholders)."""
    ui.go(page, base_url, 'home')
    assert ui.raw_i18n_keys(ui.visible_text(page)) == []
    page.evaluate("""() => {
        const d = document.createElement('div'); d.textContent = 'ministry.fakeKey';
        const i = document.createElement('input'); i.placeholder = 'common.placeholderKey';
        document.body.append(d, i);
    }""")
    assert ui.raw_i18n_keys(ui.visible_text(page)) == ['common.placeholderKey', 'ministry.fakeKey']


def test_home_loads(page: Page, base_url, shot):
    ui.go(page, base_url, 'home')
    expect(page.locator('h1').first).to_have_text(ui.en('common:home.title'))
    for key in ('ministry', 'tyrant', 'svs', 'tal'):
        expect(page.get_by_test_id(f'event-tile-{key}')).to_be_visible()
    for name in ui.LANGUAGES.values():
        expect(page.get_by_role('button', name=name, exact=True)).to_be_visible()
    assert page.evaluate('document.documentElement.dir') in ('ltr', '')
    shot('home-en')


@pytest.mark.parametrize('route', ui.PUBLIC_PAGES)
def test_no_raw_i18n_keys_public_pages(page: Page, base_url, shot, route):
    ui.go(page, base_url, route)
    bad = ui.check_all_languages(page, route, shot)
    assert not bad, f'raw i18n keys visible on {route}: {bad}'


def test_each_language_changes_home_text(page: Page, base_url, shot):
    """Catch silent fallback to English (a language whose strings are all missing)."""
    ui.go(page, base_url, 'home')
    english = page.locator('h1').first.inner_text()
    same = []
    for code in NON_EN:
        ui.switch_language(page, code)
        shot(f'home-{code}', full_page=False)
        if page.locator('h1').first.inner_text() == english:
            same.append(code)
    assert not same, f'home heading still English in: {same}'


def test_arabic_sets_rtl_and_back(page: Page, base_url, shot):
    ui.go(page, base_url, 'home')
    ui.switch_language(page, 'ar')
    assert page.evaluate('document.documentElement.dir') == 'rtl'
    shot('home-ar-rtl')
    ui.switch_language(page, 'en')
    assert page.evaluate('document.documentElement.dir') == 'ltr'


def test_application_form_all_languages(page: Page, base_url, shot, api):
    """New-application form (unsaved, fresh FID) and an edit form, in all 9 languages."""
    bad = {}
    assert ui.open_application(page, base_url, f'99{_STAMP}01') == 'new'
    found = ui.check_all_languages(page, 'apply-new', shot)
    if found:
        bad['new'] = found

    fid = f'99{_STAMP}02'
    api.put_application(fid, 'E2E i18n edit', 'I18', {
        'construction_speedups_days': 1, 'time_slots_by_day': {'construction': ['10:00']}})
    assert ui.open_application(page, base_url, fid) == 'edit'
    for day_type in ('research', 'troop'):                      # every day-type tab rendered once
        ui.day_tab(page, day_type).click()
    found = ui.check_all_languages(page, 'apply-edit', shot)
    if found:
        bad['edit'] = found
    assert not bad, f'raw i18n keys on the application form: {bad}'


def test_arabic_rtl_new_pages(page: Page, base_url, shot, api, admin_password):
    """Arabic: <html dir=rtl> and Arabic text on each new page/state."""
    rnd = api.current_round()
    ar = lambda key, **kw: ui.tr('ar', key, **kw)  # noqa: E731

    ui.go(page, base_url, 'ministry')
    ui.switch_language(page, 'ar')
    expect(page.get_by_test_id('current-round')).to_have_text(ar('ministry:home.currentRound', round=rnd['name']))
    expect(page.get_by_test_id('ministry-apply-tile')).to_contain_text(ar('ministry:home.applyTile'))
    shot('ar-ministry-home')

    page.get_by_test_id('ministry-apply-tile').click()
    expect(page.get_by_test_id('application-heading')).to_have_text(ar('ministry:apply.title'))
    expect(page.get_by_text(ar('ministry:apply.enterFid'))).to_be_visible()
    assert page.evaluate('document.documentElement.dir') == 'rtl'
    shot('ar-apply-lookup')

    fid = f'99{_STAMP}03'
    api.put_application(fid, 'E2E ar edit', 'ARB', {'troop_training_speedups_days': 2})
    page.get_by_test_id('fid-input').fill(fid)
    page.get_by_test_id('fid-continue').click()
    expect(page.get_by_test_id('application-heading')).to_have_text(ar('ministry:apply.editFor', round=rnd['name']))
    expect(page.get_by_test_id('profile-status')).to_have_text(ar('profile:prefilled'))
    # RTL really reaches the new components (computed direction, not just the <html> attribute)
    assert page.evaluate("getComputedStyle(document.querySelector('[data-testid=profile-fields]')).direction") == 'rtl'
    shot('ar-apply-edit')

    ui.admin_login(page, base_url, admin_password)
    ui.switch_language(page, 'ar')
    expect(page.get_by_test_id('start-new-round')).to_have_text(ar('admin:round.start'))
    page.get_by_test_id('start-new-round').click()
    expect(page.get_by_test_id('new-round-dialog')).to_contain_text(ar('admin:round.startTitle'))
    shot('ar-admin-start-round-dialog')
    page.get_by_test_id('cancel-new-round').click()
    page.get_by_test_id('tab-settings').click()
    expect(page.get_by_test_id('round-settings-title')).to_have_text(ar('admin:round.settingsFor', round=rnd['name']))
    assert page.evaluate('document.documentElement.dir') == 'rtl'
    shot('ar-admin-settings')


def test_admin_pages_all_languages(page: Page, base_url, admin_password, shot):
    ui.admin_login(page, base_url, admin_password)
    bad = {}
    for tab in ('players', 'assignments', 'settings'):
        page.get_by_test_id(f'tab-{tab}').click()
        page.wait_for_load_state('networkidle')
        found = ui.check_all_languages(page, f'admin-{tab}', shot)
        if found:
            bad[tab] = found
    # The modal covers the header language buttons: switch first, then open it, per language.
    for code in ui.LANGUAGES:
        ui.switch_language(page, code)
        page.get_by_test_id('start-new-round').click()
        expect(page.get_by_test_id('new-round-dialog')).to_be_visible()
        keys = ui.raw_i18n_keys(ui.visible_text(page))
        if keys:
            bad.setdefault('start-round-dialog', {})[code] = keys
            shot(f'admin-start-round-dialog-{code}-RAWKEYS')
        page.get_by_test_id('cancel-new-round').click()
    ui.switch_language(page, 'en')
    ui.go(page, base_url, 'admin_guide')
    found = ui.check_all_languages(page, 'admin_guide', shot)
    if found:
        bad['admin_guide'] = found
    assert not bad, f'raw i18n keys in admin pages: {bad}'
