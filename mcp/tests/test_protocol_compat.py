"""Older clients (e.g. Claude Code) use the initialize handshake (protocol 2025-06-18 and earlier).

Drive that handshake with raw JSON-RPC over HTTP so we know a non-SDK client works too.
"""
import httpx2
import pytest

from conftest import BEARER

HEADERS = {'Accept': 'application/json, text/event-stream', 'Content-Type': 'application/json'}


def rpc(url, method, params=None, id_=1, headers=None, session=None):
    h = {**HEADERS, **(headers or {}), 'MCP-Protocol-Version': '2025-06-18'}
    if session:
        h['Mcp-Session-Id'] = session
    body = {'jsonrpc': '2.0', 'method': method}
    if id_ is not None:
        body['id'] = id_
    if params is not None:
        body['params'] = params
    return httpx2.post(url, json=body, headers=h)


@pytest.mark.parametrize('version', ['2025-03-26', '2025-06-18', '2025-11-25'])
def test_handshake_era_client(mcp_url, version):
    url = f'{mcp_url}/admin/mcp'
    auth = {'Authorization': f'Bearer {BEARER}'}
    r = rpc(url, 'initialize', {'protocolVersion': version, 'capabilities': {},
                                'clientInfo': {'name': 'claude-code-like', 'version': '0'}}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()['result']['protocolVersion'] == version
    session = r.headers.get('mcp-session-id')
    rpc(url, 'notifications/initialized', id_=None, headers=auth, session=session)
    r = rpc(url, 'tools/list', id_=2, headers=auth, session=session)
    names = {t['name'] for t in r.json()['result']['tools']}
    assert {'list_events', 'list_rounds', 'start_new_round'} <= names
    r = rpc(url, 'tools/call', {'name': 'get_profile', 'arguments': {'fid': '424242'}}, id_=3,
            headers=auth, session=session)
    result = r.json()['result']
    assert result['isError'] is True and result['structuredContent']['code'] == 'NOT_FOUND'
