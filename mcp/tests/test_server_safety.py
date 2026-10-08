"""Server-level safety: disabled admin, bad admin password, rate limiting, token re-login, no secrets in logs."""
import httpx2
import pytest

from conftest import ADMIN_PASSWORD, BEARER, call, connect

pytestmark = pytest.mark.anyio


async def test_admin_endpoint_disabled_without_bearer_config(start_mcp):
    url = start_mcp(MCP_BEARER_TOKEN=None)
    r = httpx2.post(f'{url}/admin/mcp', json={}, headers={'Authorization': f'Bearer {BEARER}'})
    assert r.status_code == 503 and r.json()['code'] == 'ADMIN_DISABLED'
    assert httpx2.get(f'{url}/health').json() == {'status': 'healthy', 'admin_enabled': False}


async def test_short_bearer_disables_admin(start_mcp):
    url = start_mcp(MCP_BEARER_TOKEN='short')
    r = httpx2.post(f'{url}/admin/mcp', json={}, headers={'Authorization': 'Bearer short'})
    assert r.status_code == 503


async def test_wrong_admin_password_gives_structured_error(start_mcp):
    url = start_mcp(WOS_ADMIN_PASSWORD='definitely-wrong')
    async with connect(f'{url}/admin/mcp', BEARER) as c:
        err, data = await call(c, 'list_rounds', {'event': 'ministry'})
    assert err and data['code'] == 'ADMIN_LOGIN_FAILED' and data['http_status'] == 503
    assert 'definitely-wrong' not in str(data)


async def test_missing_admin_password(start_mcp):
    url = start_mcp(WOS_ADMIN_PASSWORD=None)
    async with connect(f'{url}/admin/mcp', BEARER) as c:
        err, data = await call(c, 'get_application_by_id', {'application_id': 1})
        assert err and data['code'] == 'ADMIN_NOT_CONFIGURED'
        err, data = await call(c, 'list_events')  # public tools still work
        assert not err


async def test_public_bearer_optional(start_mcp):
    url = start_mcp(MCP_PUBLIC_BEARER_TOKEN='p' * 40)
    assert httpx2.post(f'{url}/mcp', json={}).status_code == 401
    async with connect(f'{url}/mcp', 'p' * 40) as c:
        err, _ = await call(c, 'list_events')
        assert not err


async def test_rate_limit(start_mcp):
    url = start_mcp(MCP_RATE_LIMIT_PER_MINUTE='3')
    body = {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}
    codes = [httpx2.post(f'{url}/mcp', json=body, headers={'Accept': 'application/json, text/event-stream'}
                         ).status_code for _ in range(5)]
    assert codes[3:] == [429, 429], codes
    assert httpx2.get(f'{url}/health').status_code == 200  # health is not limited


async def test_wosapi_relogins_on_invalid_token(backend):
    from wos_mcp.api import WosApi
    from wos_mcp.config import Config
    api = WosApi(Config(api_base=backend, admin_password=ADMIN_PASSWORD))
    try:
        res = await api.admin('GET', '/api/admin/me')
        assert res.ok
        api._token = 'forged.token'  # simulate a token the backend no longer accepts
        res = await api.admin('GET', '/api/admin/me')
        assert res.ok and res.body == {'role': 'admin'}
        assert api._token != 'forged.token'
    finally:
        await api.aclose()


def test_no_secrets_in_logs(start_mcp):
    """Runs last in this module: every MCP server started so far must not have logged secrets."""
    logs = start_mcp.logs
    assert logs
    for log in logs:
        text = log.read_text()
        for secret in (ADMIN_PASSWORD, BEARER, 'definitely-wrong', 'p' * 40):
            assert secret not in text, f'secret leaked in {log}'
        assert 'Bearer ' not in text
        assert '"token"' not in text
