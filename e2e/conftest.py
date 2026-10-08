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
from playwright.sync_api import Page, expect

ARTIFACTS = Path(__file__).parent / 'artifacts'
RUN_ID = time.strftime('%Y%m%d-%H%M%S')

expect.set_options(timeout=10_000)


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
    return {**browser_context_args, 'base_url': base_url,
            'viewport': {'width': 1280, 'height': 900}}


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
    """v1.4 uses window.confirm() when a day has no time slots selected."""
    page.on('dialog', lambda d: d.accept())
    return page
