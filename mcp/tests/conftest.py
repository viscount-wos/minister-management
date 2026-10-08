"""End-to-end fixtures: real Flask backend + real MCP server, both as subprocesses.

The backend runs from ../backend with a temp SQLite DB, FLASK_ENV=development and
ADMIN_PASSWORD set. The MCP server runs ``python -m wos_mcp`` against it. Tests talk
to the MCP server only through a real MCP client over streamable HTTP.
"""
from __future__ import annotations

import contextlib
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

MCP_DIR = Path(__file__).resolve().parents[1]
REPO = MCP_DIR.parent
BACKEND_DIR = REPO / 'backend'

ADMIN_PASSWORD = 'pw-' + secrets.token_hex(12)
BEARER = 'mcp-' + secrets.token_hex(24)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def backend_python() -> str:
    explicit = os.getenv('WOS_BACKEND_PYTHON')
    if explicit:
        return explicit
    venv = BACKEND_DIR / 'venv' / 'bin' / 'python'
    return str(venv) if venv.exists() else sys.executable


def wait_http(url: str, proc: subprocess.Popen, log: Path, timeout: float = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f'process exited early:\n{log.read_text()[-4000:]}')
        try:
            if httpx2.get(url, timeout=1).status_code == 200:
                return
        except httpx2.HTTPError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f'{url} not ready:\n{log.read_text()[-4000:]}')


def stop(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope='session')
def backend(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('backend')
    port = free_port()
    log = tmp / 'backend.log'
    env = {**os.environ, 'FLASK_ENV': 'development', 'ADMIN_PASSWORD': ADMIN_PASSWORD,
           'MINISTER_PASSWORD': 'minister-' + secrets.token_hex(8),
           'SECRET_KEY': secrets.token_urlsafe(32), 'DATABASE_PATH': str(tmp / 'data' / 'test.db')}
    code = (f'from app import create_app; create_app({{"STATIC_DIR": "/nonexistent"}})'
            f'.run(host="127.0.0.1", port={port}, debug=False, use_reloader=False)')
    with open(log, 'w') as fh:
        proc = subprocess.Popen([backend_python(), '-c', code], cwd=BACKEND_DIR, env=env,
                                stdout=fh, stderr=subprocess.STDOUT)
    base = f'http://127.0.0.1:{port}'
    try:
        wait_http(f'{base}/health', proc, log)
        yield base
    finally:
        stop(proc)


class Api:
    """Direct API access for test setup (rounds, publishing) and cross-checks."""

    def __init__(self, base: str):
        self.base = base
        token = httpx2.post(f'{base}/api/admin/login', json={'password': ADMIN_PASSWORD}).json()['token']
        self.h = {'Authorization': f'Bearer {token}'}

    def admin(self, method: str, path: str, json=None):
        r = httpx2.request(method, f'{self.base}{path}', json=json, headers=self.h)
        return r.status_code, r.json()

    def start_round(self, name: str, event: str = 'ministry', **body) -> dict:
        status, data = self.admin('POST', f'/api/admin/events/{event}/start-new-round', {'name': name, **body})
        assert status == 201, data
        return data['round']


@pytest.fixture(scope='session')
def api(backend) -> Api:
    return Api(backend)


@pytest.fixture(scope='session')
def start_mcp(backend, tmp_path_factory):
    procs: list[subprocess.Popen] = []
    logs: list[Path] = []

    def _start(**overrides) -> str:
        port = free_port()
        log = tmp_path_factory.mktemp('mcp') / 'mcp.log'
        env = {**os.environ, 'WOS_API_BASE': backend, 'MCP_HOST': '127.0.0.1', 'MCP_PORT': str(port),
               'MCP_BEARER_TOKEN': BEARER, 'WOS_ADMIN_PASSWORD': ADMIN_PASSWORD,
               'MCP_RATE_LIMIT_PER_MINUTE': '0', 'PYTHONUNBUFFERED': '1'}
        for k, v in overrides.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
        with open(log, 'w') as fh:
            proc = subprocess.Popen([sys.executable, '-m', 'wos_mcp'], cwd=MCP_DIR, env=env,
                                    stdout=fh, stderr=subprocess.STDOUT)
        procs.append(proc)
        logs.append(log)
        url = f'http://127.0.0.1:{port}'
        wait_http(f'{url}/health', proc, log)
        return url

    _start.logs = logs  # type: ignore[attr-defined]
    yield _start
    for p in procs:
        stop(p)


@pytest.fixture(scope='session')
def mcp_url(start_mcp) -> str:
    return start_mcp()


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@contextlib.asynccontextmanager
async def connect(url: str, token: str | None = None):
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    async with httpx2.AsyncClient(headers=headers, timeout=30) as http:
        async with Client(streamable_http_client(url, http_client=http)) as client:
            yield client


@pytest.fixture
def public(mcp_url):
    return lambda: connect(f'{mcp_url}/mcp')


@pytest.fixture
def admin(mcp_url):
    return lambda token=BEARER: connect(f'{mcp_url}/admin/mcp', token)


async def call(client, name: str, args: dict | None = None):
    """Call a tool; return (is_error, structured_content)."""
    res = await client.call_tool(name, args or {})
    return bool(res.is_error), res.structured_content


def fid() -> str:
    return str(10_000_000 + secrets.randbelow(89_999_999))
