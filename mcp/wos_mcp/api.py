"""Thin async client for the wos-events HTTP API.

This is the ONLY way the MCP server touches app data: every read and write goes
through the public/admin HTTP API so validation stays in the backend.

Every call returns an ``ApiResult`` instead of raising: the backend's JSON body
(success or ``{error, code, field}``) is kept verbatim together with the HTTP
status, so tools can hand it to the caller faithfully.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx2

from .config import Config

logger = logging.getLogger(__name__)

# Re-login this long before the backend's 12 h expiry.
TOKEN_REFRESH_MARGIN = 300
# Admin-call failures that mean "get a fresh token and retry once".
_RELOGIN_CODES = {'TOKEN_EXPIRED', 'INVALID_TOKEN', 'UNAUTHORIZED'}


@dataclass
class ApiResult:
    status: int
    body: dict[str, Any]

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def code(self) -> str | None:
        return self.body.get('code') if not self.ok else None


def seg(value: Any) -> str:
    """Percent-encode one URL path segment (``/``, ``?``, ``#``, ``..`` cannot escape it)."""
    text = str(value)
    if text in ('.', '..'):
        text = text.replace('.', '%2E')
    return quote(text, safe='')


class WosApi:
    def __init__(self, config: Config, transport: httpx2.AsyncBaseTransport | None = None):
        self._config = config
        self._client = httpx2.AsyncClient(
            base_url=config.api_base,
            timeout=config.api_timeout_seconds,
            follow_redirects=False,
            headers={'Accept': 'application/json', 'User-Agent': 'wos-events-mcp/0.1'},
            transport=transport,
        )
        self._token: str | None = None
        self._token_deadline = 0.0
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ core
    async def request(self, method: str, path: str, *, json: Any = None,
                      params: dict[str, Any] | None = None,
                      headers: dict[str, str] | None = None) -> ApiResult:
        try:
            resp = await self._client.request(method, path, json=json, params=params, headers=headers)
        except httpx2.TimeoutException:
            return ApiResult(504, {'error': 'The wos-events API did not answer in time',
                                   'code': 'API_TIMEOUT', 'field': None})
        except httpx2.HTTPError as exc:
            # Exception text can carry the URL but never headers; keep the class only.
            logger.warning('API %s %s failed: %s', method, path, type(exc).__name__)
            return ApiResult(502, {'error': 'The wos-events API is unreachable',
                                   'code': 'API_UNREACHABLE', 'field': None})
        try:
            body = resp.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            return ApiResult(resp.status_code if resp.status_code >= 400 else 502, {
                'error': f'Unexpected non-JSON response from the API (HTTP {resp.status_code})',
                'code': 'UPSTREAM_ERROR', 'field': None})
        return ApiResult(resp.status_code, body)

    async def get(self, path: str, **kw: Any) -> ApiResult:
        return await self.request('GET', path, **kw)

    async def put(self, path: str, body: Any, **kw: Any) -> ApiResult:
        return await self.request('PUT', path, json=body, **kw)

    async def post(self, path: str, body: Any, **kw: Any) -> ApiResult:
        return await self.request('POST', path, json=body, **kw)

    # ----------------------------------------------------------------- admin
    async def _login(self) -> ApiResult | None:
        """Obtain a signed admin token. Returns an error ApiResult on failure, None on success."""
        if not self._config.admin_password:
            return ApiResult(503, {'error': 'Admin tools are not configured on this MCP server '
                                            '(WOS_ADMIN_PASSWORD unset)',
                                   'code': 'ADMIN_NOT_CONFIGURED', 'field': None})
        res = await self.post('/api/admin/login', {'password': self._config.admin_password})
        if not res.ok:
            logger.warning('Admin login to the API failed: %s', res.code)
            if res.code == 'INVALID_PASSWORD':
                # Do not leak "the MCP password is wrong" details beyond the code.
                return ApiResult(503, {'error': 'The MCP server could not log in to the API',
                                       'code': 'ADMIN_LOGIN_FAILED', 'field': None})
            return res
        token = res.body.get('token')
        if not isinstance(token, str) or not token:
            return ApiResult(502, {'error': 'API login returned no token', 'code': 'UPSTREAM_ERROR',
                                   'field': None})
        expires_in = res.body.get('expires_in')
        expires_in = expires_in if isinstance(expires_in, (int, float)) else 3600
        self._token = token
        self._token_deadline = time.monotonic() + max(60.0, expires_in - TOKEN_REFRESH_MARGIN)
        logger.info('Obtained admin API token (role=%s)', res.body.get('role'))
        return None

    async def _ensure_token(self, force: bool = False) -> ApiResult | None:
        async with self._lock:
            if force or not self._token or time.monotonic() >= self._token_deadline:
                self._token = None
                return await self._login()
            return None

    async def admin(self, method: str, path: str, *, json: Any = None,
                    params: dict[str, Any] | None = None) -> ApiResult:
        """Call an /api/admin endpoint with the server-held admin token (re-login once on 401)."""
        res = ApiResult(500, {'error': 'unreachable', 'code': 'INTERNAL_ERROR', 'field': None})
        for attempt in (0, 1):
            err = await self._ensure_token(force=attempt == 1)
            if err is not None:
                return err
            res = await self.request(method, path, json=json, params=params,
                                     headers={'Authorization': f'Bearer {self._token}'})
            if res.status == 401 and res.code in _RELOGIN_CODES and attempt == 0:
                continue
            return res
        return res
