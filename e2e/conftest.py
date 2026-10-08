"""Shared fixtures for the wos-events smoke suite.

BASE_URL       app under test (default http://127.0.0.1:8091, the local docker container)
ADMIN_PASSWORD admin password (default 'admin123', the LOCAL DEV default only)
"""
from __future__ import annotations

import os
import re
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect

import ui

ARTIFACTS = Path(__file__).parent / 'artifacts'
RUN_ID = time.strftime('%Y%m%d-%H%M%S')

expect.set_options(timeout=10_000)

# ------------------------------------------------------------------ CSP watch
# Every browser context in the suite (pytest-playwright's `page`, test_mobile's phones, ad-hoc contexts)
# reports Content-Security-Policy violations here; the autouse fixture below fails the test that caused one.
# Two sources: Chromium's console error ("Refused to ... violates the following Content Security Policy
# directive") and the DOM `securitypolicyviolation` event, re-logged so a wording change can't hide one.
CSP_VIOLATIONS: list[str] = []
_CSP_EVENT_JS = """
document.addEventListener('securitypolicyviolation', (e) => {
  console.error('Content Security Policy violation (event): ' + e.violatedDirective + ' blocked ' +
                (e.blockedURI || 'inline') + ' at ' + location.pathname);
});
"""


def _watch_csp(ctx):
    def on_console(msg):
        if 'Content Security Policy' in msg.text:
            CSP_VIOLATIONS.append(f'{msg.type}: {msg.text}')
    ctx.on('console', on_console)
    ctx.add_init_script(_CSP_EVENT_JS)
    return ctx


_orig_new_context = Browser.new_context


def _new_context_with_csp_watch(self, *args, **kwargs):
    return _watch_csp(_orig_new_context(self, *args, **kwargs))


Browser.new_context = _new_context_with_csp_watch


@pytest.fixture(autouse=True)
def no_csp_violations(request):
    """Fails any browser test during which a page reported a CSP violation."""
    CSP_VIOLATIONS.clear()
    yield
    if request.node.get_closest_marker('csp_violations_expected'):
        CSP_VIOLATIONS.clear()
        return
    found, CSP_VIOLATIONS[:] = list(CSP_VIOLATIONS), []
    if found:
        pytest.fail('Content Security Policy violations:\n' + '\n'.join(dict.fromkeys(found)), pytrace=False)


@pytest.fixture(scope='session')
def base_url() -> str:
    """Overrides pytest-base-url's fixture so BASE_URL env works without a CLI flag."""
    url = os.environ.get('BASE_URL', 'http://127.0.0.1:8091').rstrip('/')
    try:
        with urllib.request.urlopen(url + '/health', timeout=5) as r:
            if r.status != 200:
                raise OSError(f'status {r.status}')
    except OSError as e:
        pytest.exit(f'App not reachable at {url}/health ({e}). Start it first.', returncode=2)
    return url


@pytest.fixture(scope='session')
def admin_password() -> str:
    return os.environ.get('ADMIN_PASSWORD', 'admin123')


@pytest.fixture(scope='session')
def browser_context_args(browser_context_args, base_url):
    # Desktop tests pin an English browser in UTC: the app now auto-detects both
    # (test_mobile.py covers the detection itself).
    return {**browser_context_args, 'base_url': base_url,
            'viewport': {'width': 1280, 'height': 900},
            'locale': 'en-US', 'timezone_id': 'UTC'}


@pytest.fixture
def shot(page: Page, request):
    """shot('step') -> artifacts/<run>/<test>-<step>.png"""
    out = ARTIFACTS / RUN_ID
    out.mkdir(parents=True, exist_ok=True)
    test = re.sub(r'[^\w.-]+', '_', request.node.name)

    def take(step: str, full_page: bool = True) -> Path:
        path = out / f'{test}-{step}.png'
        page.screenshot(path=str(path), full_page=full_page)
        return path
    return take


@pytest.fixture
def accept_dialogs(page: Page):
    """The form uses window.confirm() when no time slots are selected at all."""
    page.on('dialog', lambda d: d.accept())
    return page


@pytest.fixture(scope='session')
def api(base_url, admin_password) -> ui.Api:
    return ui.Api(base_url, admin_password)


@pytest.fixture(scope='session', autouse=True)
def ministry_round(base_url, admin_password):
    """A fresh install has no rounds: make sure an open ministry round exists for the suite."""
    return ui.Api(base_url, admin_password).ensure_open_round(f'E2E round {RUN_ID}')
