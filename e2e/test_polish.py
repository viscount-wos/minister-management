"""v2.1.0 polish: security headers + CSP in a real browser, compression and caching, the friendly 429 message,
player-facing dates (display timezone, month names, no seconds; en / ko / ar), the "find your player ID" hint,
the discreet Event Management link, and renaming a round from Event Management.

Rate limits themselves are tested in backend/tests/test_security.py (low limits via config): the e2e stack runs
with them off (e2e/docker-compose.e2e.yml), so the UI message is checked with a stubbed 429 here.
"""
from __future__ import annotations

import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from playwright.sync_api import Page, expect

import conftest
import ui
from ui import tr

RUN = time.strftime('%H%M%S')
SECONDS_RE = re.compile(r'\d{1,2}:\d{2}:\d{2}')
AR_MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر',
             'نوفمبر', 'ديسمبر']
EN_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec']


def fetch(base_url: str, path: str, headers: dict | None = None):
    req = urllib.request.Request(base_url + path, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, dict(r.headers.items()), r.read()


def asset_paths(base_url: str) -> list[str]:
    _, _, body = fetch(base_url, '/')
    return re.findall(r'(?:src|href)="(/assets/[^"]+)"', body.decode())


def open_round(api: ui.Api, event: str):
    status, res = api.call('GET', f'/api/events/{event}/current', ok=None)
    if status == 200:
        return res
    _, res = api.call('POST', f'/api/admin/events/{event}/start-new-round', {'name': f'Polish {event} {RUN}'},
                      admin=True)
    return res['round']


def set_display(page: Page, lang: str, tz: str) -> None:
    page.evaluate("([l, z]) => { localStorage.setItem('preferred_language', l);"
                  " localStorage.setItem('preferred_timezone', z); }", [lang, tz])


# ------------------------------------------------------------------ headers, CSP, compression, caching

def test_security_headers_on_page_api_and_assets(base_url):
    for path in ['/', '/tyrant', '/api/events', '/health', *asset_paths(base_url)]:
        _, h, _ = fetch(base_url, path)
        assert h['X-Content-Type-Options'] == 'nosniff', path
        assert h['X-Frame-Options'] == 'DENY', path
        assert h['Referrer-Policy'] == 'strict-origin-when-cross-origin', path
        assert 'camera=()' in h['Permissions-Policy'] and 'geolocation=()' in h['Permissions-Policy'], path
        csp = h['Content-Security-Policy']
        for d in ("default-src 'self'", "img-src 'self' data:", "connect-src 'self'", "object-src 'none'",
                  "base-uri 'self'", "frame-ancestors 'none'"):
            assert d in csp, (path, d)
        # the http e2e stack runs FLASK_ENV=development: no HSTS (it would pin http LAN hosts to https)
        assert 'Strict-Transport-Security' not in h, path
    _, h, _ = fetch(base_url, '/')
    assert re.search(r"script-src 'self' 'sha256-[A-Za-z0-9+/=]+'", h['Content-Security-Policy'])


def test_assets_compressed_and_immutable_html_no_cache(base_url):
    js = [p for p in asset_paths(base_url) if p.endswith('.js')]
    assert js, 'no script asset in index.html'
    for enc in ('br', 'gzip'):
        _, h, body = fetch(base_url, js[0], {'Accept-Encoding': enc})
        assert h.get('Content-Encoding') == enc
        assert h['Cache-Control'] == 'public, max-age=31536000, immutable'
        assert 'Accept-Encoding' in h.get('Vary', '')
        _, plain_h, plain = fetch(base_url, js[0])
        assert 'Content-Encoding' not in plain_h and len(body) < len(plain) / 2
    _, h, _ = fetch(base_url, '/')
    assert h['Cache-Control'] == 'no-cache'
    _, h, _ = fetch(base_url, '/api/events')
    assert h['Cache-Control'] == 'no-cache'


@pytest.mark.csp_violations_expected
def test_csp_watch_catches_a_violation(page: Page, base_url):
    """Self-test of the conftest CSP watch: an injected inline script is blocked AND reported."""
    page.goto(base_url + '/')
    page.evaluate("() => { const s = document.createElement('script'); s.textContent = 'window.__pwned = 1';"
                  " document.head.appendChild(s); }")
    page.wait_for_timeout(300)
    assert page.evaluate('window.__pwned') is None
    assert any('Content Security Policy' in v for v in conftest.CSP_VIOLATIONS), conftest.CSP_VIOLATIONS


def test_first_load_only_fetches_the_active_language(page: Page, base_url):
    seen: list[str] = []
    page.on('request', lambda r: seen.append(r.url))
    page.goto(base_url + '/tyrant')
    page.wait_for_load_state('networkidle')
    locales = sorted(u.rsplit('/', 1)[-1].split('-')[1] for u in seen if '/assets/locale-' in u)
    assert locales == ['en'], locales
    assert not [u for u in seen if re.search(r'/assets/(AdminShell|registry|Changelog|PlayerGuide)-', u)]
    # switching language loads that language on demand, then shows it
    ui.switch_language(page, 'ko')
    expect(page.get_by_test_id('times-shown-in')).to_contain_text('시간')
    assert any('/assets/locale-ko-' in u for u in seen)


# ------------------------------------------------------------------ rate limit message

def test_rate_limited_lookup_shows_friendly_message(page: Page, base_url, api):
    open_round(api, 'tyrant')
    def limited(route):
        route.fulfill(status=429, headers={'Retry-After': '42'}, content_type='application/json',
                      body='{"error": "Too many requests", "code": "RATE_LIMITED", "field": null,'
                           ' "details": {"retry_after": 42}}')
    page.route(re.compile(r'.*/api/(profile/\d+|events/\w+/(current/application|previous-application)/\d+)$'),
               limited)
    for path, lang in (('/minister/apply', 'en'), ('/tyrant/apply', 'ar')):
        page.goto(base_url + '/')
        set_display(page, lang, 'UTC')
        page.goto(base_url + path)
        page.wait_for_load_state('networkidle')
        page.get_by_test_id('fid-input').fill('12345678')
        page.get_by_test_id('wizard-next').click()
        expect(page.get_by_text(tr(lang, 'common:errors.rateLimited'))).to_be_visible()


# ------------------------------------------------------------------ dates and times

@pytest.fixture
def closing_soon(api):
    """Give the open Tyrant and Minister rounds a closing time 2 days ahead at :06 past (UTC); restore after."""
    when = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=14, minute=6, second=0, microsecond=0)
    iso = when.strftime('%Y-%m-%dT%H:%M:%SZ')
    rounds = [open_round(api, 'tyrant'), open_round(api, 'ministry')]
    for r in rounds:
        api.call('PUT', f'/api/admin/rounds/{r["id"]}', {'closing_time': iso}, admin=True)
    yield when
    for r in rounds:
        api.call('PUT', f'/api/admin/rounds/{r["id"]}', {'closing_time': r['closing_time']}, admin=True)


@pytest.mark.parametrize('lang', ['en', 'ko', 'ar'])
def test_closing_time_in_display_zone_with_month_name(page: Page, base_url, closing_soon, lang, shot):
    london = closing_soon.astimezone(ZoneInfo('Europe/London'))
    month = closing_soon.month
    page.goto(base_url + '/')
    set_display(page, lang, 'Europe/London')
    page.goto(base_url + '/tyrant')
    banner = page.get_by_test_id('closing-time-banner')
    expect(banner).to_contain_text(london.strftime('%H:%M'))
    text = banner.inner_text()
    assert '(London)' in text, text
    assert not SECONDS_RE.search(text), text
    assert not re.search(r'\d{1,2}/\d{1,2}/\d{4}', text), text      # no ambiguous numeric date
    if lang == 'en':
        assert EN_MONTHS[month - 1] in text or closing_soon.strftime('%B')[:3] in text, text
    elif lang == 'ko':
        assert f'{month}월' in text, text
    else:
        assert AR_MONTHS[month - 1] in text, text
        assert not re.search('[٠-٩]', text), text                     # Latin digits, like the rest of the app
        assert '\u2068' in banner.text_content()                      # isolated inside the RTL sentence
    # the page says which zone it uses (no more "All times are in UTC")
    expect(page.get_by_test_id('times-shown-in')).to_have_text(tr(lang, 'common:timesShownIn', zone='London'))
    shot(f'tyrant-{lang}')

    # the header timezone drives it: Korea -> +9 h, labelled KST
    page.get_by_test_id(ui.TIMEZONE_SELECT).select_option('Asia/Seoul')
    expect(banner).to_contain_text((closing_soon + timedelta(hours=9)).strftime('%H:%M'))
    expect(banner).to_contain_text('(KST)')

    # same helper on the Minister wizard's closing note
    page.goto(base_url + '/minister/apply')
    note = page.get_by_test_id('closing-note')
    expect(note).to_contain_text((closing_soon + timedelta(hours=9)).strftime('%H:%M'))
    assert not SECONDS_RE.search(note.inner_text())


def test_admin_closing_time_entered_in_display_zone(page: Page, base_url, api):
    rnd = open_round(api, 'tyrant')
    try:
        ui.use_admin_token(page, base_url, api.token())
        page.evaluate("localStorage.setItem('preferred_timezone', 'Asia/Seoul')")
        page.goto(base_url + ui.admin_dashboard_url('tyrant'))
        page.get_by_test_id('tab-settings').click()
        expect(page.get_by_test_id('closing-time-zone')).to_have_text(
            tr('en', 'admin:closingTimeZone', zone='KST'))
        page.get_by_test_id('closing-time').fill('2099-03-04T09:30')
        page.get_by_test_id('save-closing-time').click()
        expect(page.get_by_test_id('closing-time-status')).to_contain_text('09:30 (KST)')
        _, cur = api.call('GET', '/api/events/tyrant/current')
        assert cur['closing_time'].startswith('2099-03-04T00:30'), cur['closing_time']   # 09:30 KST = 00:30 UTC
    finally:
        api.call('PUT', f'/api/admin/rounds/{rnd["id"]}', {'closing_time': rnd['closing_time']}, admin=True)


# ------------------------------------------------------------------ find your player ID

@pytest.mark.parametrize('path', ['/minister/apply', '/tyrant/apply'])
@pytest.mark.parametrize('lang', ['en', 'ar'])
def test_fid_step_has_where_do_i_find_it_hint(page: Page, base_url, api, path, lang):
    open_round(api, 'tyrant')
    page.goto(base_url + '/')
    set_display(page, lang, 'UTC')
    page.goto(base_url + path)
    toggle = page.get_by_test_id('fid-help-toggle')
    expect(toggle).to_have_text(tr(lang, 'common:fidHelp.question'))
    assert toggle.bounding_box()['height'] >= 43.5
    expect(page.get_by_test_id('fid-help-text')).to_be_hidden()
    toggle.click()
    expect(page.get_by_test_id('fid-help-text')).to_have_text(tr(lang, 'common:fidHelp.answer'))
    # it is help, not a submit: still on the FID step
    expect(page.get_by_test_id('fid-input')).to_be_visible()


# ------------------------------------------------------------------ discreet admin link

@pytest.mark.parametrize('event,path', [('ministry', '/minister'), ('tyrant', '/tyrant')])
def test_event_management_is_a_small_link(page: Page, base_url, api, event, path):
    open_round(api, event)
    page.goto(base_url + path)
    link = page.get_by_test_id(f'{event}-admin-tile')
    tile = page.get_by_test_id(f'{event}-apply-tile')
    expect(link).to_have_text(tr('en', 'admin:title'))
    lb, tb = link.bounding_box(), tile.bounding_box()
    assert 43.5 <= lb['height'] <= 48, lb                           # still a 44px tap target, but one line
    assert lb['width'] < tb['width'] / 2 and lb['height'] < tb['height'] / 2, (lb, tb)
    assert lb['y'] > tb['y'] + tb['height'], 'link sits under the main actions'
    size = float(link.evaluate('e => parseFloat(getComputedStyle(e).fontSize)'))
    assert size <= 12.5, size
    link.click()
    page.wait_for_url(f'**/admin?event={event}')


# ------------------------------------------------------------------ round renaming

def test_rename_round_from_event_management(page: Page, base_url, api):
    rnd = open_round(api, 'tyrant')
    new_name = f'Renamed {RUN}'
    try:
        ui.use_admin_token(page, base_url, api.token(), ui.admin_dashboard_url('tyrant'))
        page.get_by_test_id('rename-round').click()
        expect(page.get_by_test_id('rename-round-input')).to_have_value(rnd['name'])
        page.get_by_test_id('rename-round-input').fill('   ')
        page.get_by_test_id('rename-round-save').click()
        expect(page.get_by_test_id('rename-round-error')).to_have_text(tr('en', 'admin:round.nameRequired'))
        page.get_by_test_id('rename-round-input').fill(new_name)
        page.get_by_test_id('rename-round-save').click()
        expect(page.get_by_test_id('rename-round-form')).to_have_count(0)
        expect(page.get_by_test_id('round-select').locator('option:checked')).to_contain_text(new_name)
        _, cur = api.call('GET', '/api/events/tyrant/current')
        assert cur['name'] == new_name
        # cancel leaves it alone
        page.get_by_test_id('rename-round').click()
        page.get_by_test_id('rename-round-input').fill('nope')
        page.get_by_test_id('rename-round-cancel').click()
        _, cur = api.call('GET', '/api/events/tyrant/current')
        assert cur['name'] == new_name
    finally:
        api.call('PATCH', f'/api/admin/rounds/{rnd["id"]}', {'name': rnd['name']}, admin=True)
