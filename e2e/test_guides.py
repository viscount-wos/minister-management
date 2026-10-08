"""Guides (docs/GUIDES.md): every player and admin guide renders in all 9 languages with no raw i18n keys and no
"Ministry" wording (nor the department word in other languages), each event page and wizard links to its guide, the
Admin Guide button opens the CURRENT event's guide with "Event Management basics" one tap away, and the shared plan
view links to the SVS guide's plan section.

When you add a guide or a guide section, add its route/test id here (and to docs/GUIDES.md)."""
from __future__ import annotations

import re
import time

import pytest
from playwright.sync_api import Page, expect

import ui

RUN = str(int(time.time()))[-6:]


def tr(key: str, lang: str = 'en', **v) -> str:
    return ui.tr(lang, key, **v)


# route -> test id of the guide body
PLAYER_GUIDES = {
    '/minister/guide': 'player-guide-ministry',
    '/tyrant/guide': 'player-guide-tyrant',
    '/svs/guide': 'player-guide-svs',
}
ADMIN_GUIDES = {
    **{ui.admin_guide_url(e): f'admin-guide-{e}' for e in ('ministry', 'tyrant', 'svs')},
    **{ui.admin_guide_url(e) + '&topic=basics': 'admin-guide-basics' for e in ('ministry', 'tyrant', 'svs')},
}
ALL_GUIDES = {**PLAYER_GUIDES, **ADMIN_GUIDES}

# The DEPARTMENT word ("Ministry") must never show; players and admins see the person/position ("Minister").
DEPARTMENT = {
    'en': r'ministr(y|ies)', 'es': r'ministerio', 'fr': r'minist[eè]re', 'de': r'ministerium', 'pl': r'ministerstw',
    'tr': r'bakanlık', 'ko': r'부처', 'zh': r'部长|部门', 'ar': r'وزارة',
}


def wait_guide(page: Page, test_id: str) -> None:
    expect(page.get_by_test_id(test_id)).to_be_visible()
    expect(page.get_by_test_id('guide-loading')).to_have_count(0)


@pytest.mark.parametrize('route', list(ALL_GUIDES))
def test_guide_renders_in_every_language(page: Page, base_url, route, shot):
    page.goto(base_url + route)
    wait_guide(page, ALL_GUIDES[route])
    raw, dept, empty = {}, {}, []
    for code in ui.LANGUAGES:
        ui.switch_language(page, code)
        expect(page.get_by_test_id('guide-loading')).to_have_count(0)
        body = page.get_by_test_id(ALL_GUIDES[route])
        expect(body).to_be_visible()
        text = ui.visible_text(page)
        if keys := ui.raw_i18n_keys(text):
            raw[code] = keys
        if found := sorted({m.group(0) for m in re.finditer(DEPARTMENT[code], text, re.I)}):
            dept[code] = found
        if len(body.inner_text()) < 400:      # a guide that silently lost its text
            empty.append(code)
        if raw.get(code) or dept.get(code):
            shot(f'guide{route.replace("/", "-").replace("?", "-")}-{code}-BAD')
    ui.switch_language(page, 'en')
    assert not raw, f'raw i18n keys on {route}: {raw}'
    assert not dept, f'department word ("Ministry") on {route}: {dept}'
    assert not empty, f'guide text missing on {route}: {empty}'


def test_arabic_guides_are_rtl(page: Page, base_url):
    for route, test_id in PLAYER_GUIDES.items():
        page.goto(base_url + route)
        wait_guide(page, test_id)
        ui.switch_language(page, 'ar')
        assert page.evaluate('document.documentElement.dir') == 'rtl'
        expect(page.get_by_test_id('guide-title')).to_have_text(
            tr({'/minister/guide': 'guide:player.title', '/tyrant/guide': 'guide:tyrantPlayer.title',
                '/svs/guide': 'guide:svsPlayer.title'}[route], 'ar'))
        ui.switch_language(page, 'en')


@pytest.mark.parametrize('event,page_path,link,guide_path,guide_id', [
    ('ministry', '/minister', 'ministry-guide-link', '/minister/guide', 'player-guide-ministry'),
    ('tyrant', '/tyrant', 'tyrant-guide-link', '/tyrant/guide', 'player-guide-tyrant'),
    ('svs', '/svs', 'svs-guide-link', '/svs/guide', 'player-guide-svs'),
])
def test_event_page_links_to_its_guide(page: Page, base_url, event, page_path, link, guide_path, guide_id):
    page.goto(base_url + page_path)
    page.get_by_test_id(link).click()
    page.wait_for_url('**' + guide_path)
    wait_guide(page, guide_id)
    # and back to the event page
    page.get_by_test_id('guide-back').click()
    page.wait_for_url(f'**{page_path}')


@pytest.fixture(scope='module')
def open_rounds(api):
    """Each event's wizard needs an open round to show its FID step."""
    for event, name in (('tyrant', 'Tyrant'), ('svs', 'SVS')):
        status, _ = api.call('GET', f'/api/events/{event}/current', ok=None)
        if status != 200:
            api.call('POST', f'/api/admin/events/{event}/start-new-round', {'name': f'{name} guides e2e {RUN}'}, admin=True)


@pytest.mark.parametrize('apply_path,link,guide_path', [
    ('/minister/apply', 'ministry-wizard-guide-link', '/minister/guide'),
    ('/tyrant/apply', 'tyrant-wizard-guide-link', '/tyrant/guide'),
    ('/svs/apply', 'svs-wizard-guide-link', '/svs/guide'),
])
def test_wizard_step1_links_to_the_guide(page: Page, base_url, open_rounds, apply_path, link, guide_path):
    page.goto(base_url + apply_path)
    page.get_by_test_id(link).click()
    page.wait_for_url('**' + guide_path)


def test_admin_guide_button_opens_current_event_with_basics_on_top(page: Page, base_url, api, open_rounds, shot):
    ui.use_admin_token(page, base_url, api.token(), ui.admin_dashboard_url('svs'))
    page.get_by_test_id('admin-guide-link').click()
    page.wait_for_url('**' + ui.admin_guide_url('svs'))
    wait_guide(page, 'admin-guide-svs')
    expect(page.get_by_test_id('guide-topic-event')).to_have_attribute('aria-selected', 'true')
    expect(page.get_by_test_id('guide-topic-event')).to_have_text(tr('guide:basics.eventTab', event=tr('svs:name')))
    # basics are linked above the event guide
    topics = page.get_by_test_id('guide-topics').bounding_box()
    body = page.get_by_test_id('admin-guide-svs').bounding_box()
    assert topics['y'] < body['y']
    page.get_by_test_id('guide-topic-basics').click()
    page.wait_for_url('**' + ui.admin_guide_url('svs') + '&topic=basics')
    wait_guide(page, 'admin-guide-basics')
    expect(page.get_by_role('heading', name=tr('guide:basics.startTitle'))).to_be_visible()
    shot('admin-guide-basics-en')
    # the event switch keeps the topic; the event tab goes back to that event's guide
    page.get_by_test_id('admin-event-tyrant').click()
    page.wait_for_url('**' + ui.admin_guide_url('tyrant') + '&topic=basics')
    wait_guide(page, 'admin-guide-basics')
    page.get_by_test_id('guide-topic-event').click()
    page.wait_for_url('**' + ui.admin_guide_url('tyrant'))
    wait_guide(page, 'admin-guide-tyrant')
    expect(page).to_have_title(re.compile('^' + re.escape(tr('guide:admin.title'))))


def test_svs_guide_plan_section_and_help_link_from_shared_plan(page: Page, base_url, api, open_rounds, shot):
    _, res = api.call('POST', '/api/admin/svs/rounds/current/plan/share', {'action': 'create'}, admin=True)
    path = res['share']['path']
    try:
        page.goto(base_url + path)
        expect(page.get_by_test_id('svs-plan-view')).to_be_visible()
        link = page.get_by_test_id('plan-help-link')
        expect(link).to_have_text(tr('common:guideLinks.planHelp'))
        link.click()
        page.wait_for_url('**/svs/guide#plan')
        wait_guide(page, 'player-guide-svs')
        section = page.get_by_test_id('guide-plan-section')
        expect(section).to_be_in_viewport()
        expect(section).to_contain_text(tr('guide:svsPlayer.planJoiners'))
        # the guide is static: nothing of the plan (its round name, its token) leaks onto it
        assert res['share']['token'] not in page.url
        shot('svs-guide-plan-section')
    finally:
        api.call('POST', '/api/admin/svs/rounds/current/plan/share', {'action': 'disable'}, admin=True)


def test_guides_are_a_lazy_chunk(page: Page, base_url):
    """Players opening an event page don't download the guide text; the guide page fetches it."""
    seen: list[str] = []
    page.on('request', lambda r: seen.append(r.url))
    page.goto(base_url + '/tyrant')
    page.wait_for_load_state('networkidle')
    assert not [u for u in seen if '/guide-' in u], [u for u in seen if '/guide-' in u]
    page.get_by_test_id('tyrant-guide-link').click()
    wait_guide(page, 'player-guide-tyrant')
    assert [u for u in seen if '/guide-en' in u]
