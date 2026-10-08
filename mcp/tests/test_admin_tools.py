"""Admin tools on /admin/mcp, plus authorisation of the admin endpoint."""
import httpx2
import pytest

from conftest import BEARER, call, connect, fid

pytestmark = pytest.mark.anyio

ADMIN_TOOLS = {'list_rounds', 'list_applications', 'get_application_by_id', 'update_application',
               'start_new_round', 'get_assignments', 'get_tyrant_summary'}
ANSWERS = {'construction_speedups_days': 1, 'general_speedups_days': 0, 'research_speedups_days': 0,
           'troop_training_speedups_days': 0, 'fire_crystals': 0, 'refined_fire_crystals': 0,
           'fire_crystal_shards': 0, 'time_slots_by_day': {'construction': ['10:00'], 'research': [], 'troop': []}}


def _apply(backend, f, alliance='ADM', name=None):
    r = httpx2.put(f'{backend}/api/events/ministry/current/application/{f}',
                   json={'profile': {'game_name': name or f'P{f}', 'alliance': alliance}, 'answers': ANSWERS})
    assert r.status_code in (200, 201), r.text
    return r.json()['application']


# ------------------------------------------------------------------ authorisation
async def test_admin_tools_not_exposed_on_public_endpoint(public):
    async with public() as c:
        names = {t.name for t in (await c.list_tools()).tools}
        assert not names & ADMIN_TOOLS
        res = await c.call_tool('list_rounds', {'event': 'ministry'})
        assert res.is_error  # unknown tool on this endpoint


@pytest.mark.parametrize('headers', [
    {},
    {'Authorization': 'Bearer wrong-token'},
    {'Authorization': f'Bearer {BEARER}x'},
    {'Authorization': BEARER[:-1]},
])
async def test_admin_endpoint_refuses_bad_or_missing_token(mcp_url, headers):
    body = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'list_rounds', 'arguments': {'event': 'ministry'}}}
    r = httpx2.post(f'{mcp_url}/admin/mcp', json=body,
                    headers={**headers, 'Accept': 'application/json, text/event-stream'})
    assert r.status_code == 401
    assert r.json()['code'] == 'UNAUTHORIZED'


async def test_admin_client_with_wrong_token_cannot_connect(mcp_url):
    with pytest.raises(Exception):
        async with connect(f'{mcp_url}/admin/mcp', 'not-the-token') as c:
            await c.call_tool('list_rounds', {'event': 'ministry'})


async def test_admin_endpoint_lists_public_and_admin_tools(admin):
    async with admin() as c:
        tools = {t.name: t for t in (await c.list_tools()).tools}
    assert ADMIN_TOOLS <= set(tools)
    assert tools['start_new_round'].annotations.destructive_hint is True
    assert tools['list_rounds'].annotations.read_only_hint is True


async def test_bare_token_also_accepted(mcp_url):
    async with httpx2.AsyncClient(headers={'Authorization': BEARER}) as http:
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client
        async with Client(streamable_http_client(f'{mcp_url}/admin/mcp', http_client=http)) as c:
            err, data = await call(c, 'list_rounds', {'event': 'ministry'})
            assert not err


# ------------------------------------------------------------------ admin tools
async def test_rounds_and_start_new_round(admin, api):
    api.start_round('Admin base round')
    async with admin() as c:
        err, data = await call(c, 'list_rounds', {'event': 'ministry'})
        assert not err and data['rounds'][0]['name'] == 'Admin base round'
        assert 'application_count' in data['rounds'][0] and data['total'] >= 1

        err, data = await call(c, 'list_rounds', {'event': 'ministry', 'limit': 1})
        assert not err and len(data['rounds']) == 1 and data['limit'] == 1

        err, data = await call(c, 'list_rounds', {'event': 'bogus'})
        assert err and data['code'] == 'UNKNOWN_EVENT'

        # Without confirm nothing changes.
        err, data = await call(c, 'start_new_round', {'event': 'ministry', 'name': 'Via MCP'})
        assert not err and data['preview'] is True and data['would_close']['name'] == 'Admin base round'
        err, data = await call(c, 'get_current_round', {'event': 'ministry'})
        assert data['name'] == 'Admin base round'

        err, data = await call(c, 'start_new_round', {'event': 'ministry', 'name': 'Via MCP', 'confirm': True,
                                                     'closing_time': '2099-01-01T00:00:00Z'})
        assert not err, data
        assert data['round']['name'] == 'Via MCP' and data['round']['status'] == 'open'
        assert data['closed_round']['name'] == 'Admin base round'

        err, data = await call(c, 'start_new_round', {'event': 'ministry', 'name': 'Bad', 'confirm': True,
                                                     'closing_time': 'not a date'})
        assert err and data['code'] == 'VALIDATION_ERROR' and data['field'] == 'closing_time'

        err, data = await call(c, 'start_new_round', {'event': 'tal', 'name': 'x', 'confirm': True})
        assert err and data['code'] == 'EVENT_HAS_NO_ROUNDS'


async def test_applications_list_get_update(admin, api, backend):
    rnd = api.start_round('Admin apps round')
    fids = [fid() for _ in range(5)]
    for i, f in enumerate(fids):
        _apply(backend, f, alliance='AAA' if i < 3 else 'BBB')
    async with admin() as c:
        err, data = await call(c, 'list_applications', {})  # defaults: current ministry round
        assert not err, data
        assert data['round_id'] == rnd['id'] and data['total'] == 5 and data['returned'] == 5
        first = data['applications'][0]
        assert 'profile' in first and 'monday_points' in first

        err, data = await call(c, 'list_applications', {'round_id': rnd['id'], 'alliance': 'AAA'})
        assert not err and data['total'] == 3
        assert {a['profile']['alliance'] for a in data['applications']} == {'AAA'}

        err, data = await call(c, 'list_applications', {'round_id': rnd['id'], 'limit': 2, 'offset': 4})
        assert not err and data['returned'] == 1 and data['total'] == 5

        err, data = await call(c, 'list_applications', {'round_id': 999999})
        assert err and data['code'] == 'NOT_FOUND'
        err, data = await call(c, 'list_applications', {'round_id': 'current', 'event': 'svs'})
        assert err and data['code'] == 'NO_CURRENT_ROUND'
        res = await c.call_tool('list_applications', {'limit': 100000})  # schema cap
        assert res.is_error

        app_id = first['id']
        err, data = await call(c, 'get_application_by_id', {'application_id': app_id})
        assert not err and data['id'] == app_id
        err, data = await call(c, 'get_application_by_id', {'application_id': 999999})
        assert err and data['code'] == 'NOT_FOUND' and data['http_status'] == 404

        err, data = await call(c, 'update_application', {'application_id': app_id,
                                                         'answers': {'fire_crystals': 99},
                                                         'profile': {'power': 5}})
        assert not err, data
        assert data['answers']['fire_crystals'] == 99
        assert data['answers']['construction_speedups_days'] == 1  # partial merge kept the rest

        err, data = await call(c, 'update_application', {'application_id': app_id,
                                                         'answers': {'fire_crystals': -1}})
        assert err and data['code'] == 'VALIDATION_ERROR' and data['field'] == 'answers.fire_crystals'
        err, data = await call(c, 'update_application', {'application_id': 999999, 'answers': {}})
        assert err and data['code'] == 'NOT_FOUND'
        err, data = await call(c, 'update_application', {'application_id': app_id})
        assert err and data['code'] == 'VALIDATION_ERROR'


async def test_get_assignments(admin, api, backend):
    rnd = api.start_round('Admin assign round')
    f = fid()
    _apply(backend, f, name='Assignee')
    status, body = api.admin('POST', '/api/admin/ministry/rounds/current/auto-assign', {'day': 'monday'})
    assert status == 200, body
    async with admin() as c:
        err, data = await call(c, 'get_assignments', {'day': 'monday'})
        assert not err, data
        assert data['round_id'] == rnd['id']
        assert data['assignments']['10:00'][0]['fid'] == f  # unpublished days are visible to admins

        err, data = await call(c, 'get_assignments', {'day': 'monday', 'round_id': rnd['id']})
        assert not err and data['round_id'] == rnd['id']

        err, data = await call(c, 'get_assignments', {'day': 'sunday'})
        assert err and data['code'] == 'VALIDATION_ERROR'
        err, data = await call(c, 'get_assignments', {'day': 'monday', 'round_id': 999999})
        assert err and data['code'] == 'NOT_FOUND'
