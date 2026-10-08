"""Home page loads; every language renders without raw i18n keys; Arabic is RTL."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

import ui

NON_EN = [c for c in ui.LANGUAGES if c != 'en']


def _check_all_languages(page: Page, where: str, shot=None) -> dict[str, list[str]]:
    """Switch through every language on the current page; return {lang: raw keys}."""
    bad = {}
    for code in ui.LANGUAGES:
        ui.switch_language(page, code)
        keys = ui.raw_i18n_keys(ui.visible_text(page))
        if keys:
            bad[code] = keys
            if shot:
                shot(f'{where}-{code}-RAWKEYS')
    ui.switch_language(page, 'en')
    return bad


def test_raw_key_detector_itself():
    text = ('Hello form.next and ministry.apply.title here; visit example.com, e.g. ABC, '
            'v1.4.0, 23:50+, 12.5 days, {{count}} slots, https://x.y/a.b')
    assert ui.raw_i18n_keys(text) == ['form.next', 'ministry.apply.title', '{{count}}']


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
    expect(page.locator('h1').first).to_be_visible()
    expect(page.get_by_role('button', name=ui.STRINGS['en']['home.submitNew'])).to_be_visible()
    expect(page.get_by_role('button', name=ui.STRINGS['en']['home.updateExisting'])).to_be_visible()
    for name in ui.LANGUAGES.values():
        expect(page.get_by_role('button', name=name, exact=True)).to_be_visible()
    assert page.evaluate('document.documentElement.dir') in ('ltr', '')
    shot('home-en')


@pytest.mark.parametrize('route', ui.PUBLIC_PAGES)
def test_no_raw_i18n_keys_public_pages(page: Page, base_url, shot, route):
    ui.go(page, base_url, route)
    bad = _check_all_languages(page, route, shot)
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


def test_apply_wizard_steps_all_languages(page: Page, base_url, shot, accept_dialogs):
    """Walk every step of the apply wizard (without submitting) in all 9 languages.

    Uses a FID that does not exist so the duplicate check passes; nothing is written.
    """
    ui.go(page, base_url, 'apply')
    ui.fill_apply_step1(page, fid='999000000001', name='E2E i18n walker (not submitted)',
                        alliance='E2E')
    bad = {}
    for step in range(1, 6):
        found = _check_all_languages(page, f'apply-step{step}', shot)
        if found:
            bad[step] = found
        if step == 3:
            ui.switch_language(page, 'ar')
            shot('apply-step3-ar')
            ui.switch_language(page, 'en')
        if step < 5:
            page.get_by_role('button', name=ui.STRINGS['en']['form.next'], exact=True).click()
    shot('apply-review-en')
    assert not bad, f'raw i18n keys in apply wizard: {bad}'


def test_admin_pages_all_languages(page: Page, base_url, admin_password, shot):
    ui.admin_login(page, base_url, admin_password)
    bad = {}
    for tab in ('admin.players', 'admin.assignments', 'admin.settings'):
        page.get_by_role('button', name=ui.STRINGS['en'][tab], exact=True).click()
        page.wait_for_load_state('networkidle')
        found = _check_all_languages(page, tab, shot)
        if found:
            bad[tab] = found
    ui.go(page, base_url, 'admin_guide')
    found = _check_all_languages(page, 'admin_guide', shot)
    if found:
        bad['admin_guide'] = found
    assert not bad, f'raw i18n keys in admin pages: {bad}'
