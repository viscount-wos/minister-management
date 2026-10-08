"""SVS battle planner through the MCP (read-mostly): get_svs_plan (admin), svs_plan_share (admin) and
get_svs_plan_shared (public, needs the secret token)."""
import pytest

from conftest import call, fid

pytestmark = pytest.mark.anyio


def plan_doc(leader_fid, joiner_fid):
    return {'strategy': 'main_counter', 'show_real_names': False,
            'groups': [{'id': 'main', 'kind': 'main', 'name': 'Main',
                        'min_requirements': {'lancer': {'min_camp': 'FC8', 'min_tier': 11}}},
                       {'id': 'counter', 'kind': 'counter', 'name': 'Counter'}],
            'leaders': [{'id': 'L1', 'group_id': 'main', 'order': 0, 'player': {'fid': leader_fid},
                         'disguise': {'pfp_hero': 'flint', 'alias': 'Rally Caller 01'},
                         'rally': {'heroes': ['jeronimo', 'molly', 'zinman'], 'ratio': {'inf': 50, 'lan': 20, 'mks': 30}},
                         'pet_buff': 'two_hours',
                         'named_joiners': [{'player': {'fid': joiner_fid}, 'rally': {'lead_hero': 'jessie'}}],
                         'extra_joiners': [{'player': {'name': 'Walk-in'}}]}]}


async def test_plan_tools(public, admin, api):
    api.start_round('MCP SVS plan', event='svs')
    lead, join = fid(), fid()
    for f in (lead, join):
        status, data = api.admin('POST', '/api/admin/rounds/current/applications?event=svs',
                                 {'fid': f, 'profile': {'game_name': f'P{f}', 'alliance': 'MCP'},
                                  'answers': {'hours': ['11:00']}})
        assert status == 201, data
    status, data = api.admin('PUT', '/api/admin/svs/rounds/current/plan', {'revision': 0, 'plan': plan_doc(lead, join)})
    assert status == 200, data

    async with public() as c:
        names = {t.name for t in (await c.list_tools()).tools}
        assert 'get_svs_plan_shared' in names and 'get_svs_plan' not in names and 'svs_plan_share' not in names
        err, data = await call(c, 'get_svs_plan_shared', {'token': 'A' * 22})
        assert err and data['code'] == 'PLAN_NOT_FOUND'

    async with admin() as c:
        err, data = await call(c, 'get_svs_plan', {})
        assert not err, data
        assert data['revision'] == 1 and data['share']['enabled'] is False
        assert data['pet_buff_times']['two_hours'] == '13:00'
        lv = data['view']['groups'][0]['leaders'][0]
        assert lv['player']['name'] == f'P{lead}' and lv['alias'] == 'Rally Caller 01'  # admin: real names
        assert data['people'][join]['signed_up'] is True
        err, data = await call(c, 'svs_plan_share', {'action': 'create'})
        assert not err and data['share']['enabled']
        token = data['share']['token']
        err, data = await call(c, 'svs_plan_share', {'action': 'nuke'})
        assert err

    async with public() as c:
        err, data = await call(c, 'get_svs_plan_shared', {'token': token})
        assert not err, data
        lv = data['groups'][0]['leaders'][0]
        assert lv['player'] is None and lv['alias'] == 'Rally Caller 01'  # show_real_names off
        assert lv['pet_buff_time'] == '13:00' and [h['slug'] for h in lv['rally']['heroes']] == ['jeronimo', 'molly', 'zinman']
        assert lv['named_joiners'][0]['rally']['ratio'] == {'inf': 50, 'lan': 20, 'mks': 30}
        assert data['groups'][0]['min_requirements']['lancer'] == {'min_camp': 'FC8', 'min_tier': 11}

    async with admin() as c:
        err, data = await call(c, 'svs_plan_share', {'action': 'rotate'})
        assert not err and data['share']['token'] != token
        new = data['share']['token']
        err, data = await call(c, 'svs_plan_share', {'action': 'disable'})
        assert not err and data['share']['enabled'] is False
    async with public() as c:
        for t in (token, new):
            err, data = await call(c, 'get_svs_plan_shared', {'token': t})
            assert err and data['code'] == 'PLAN_NOT_FOUND'


async def test_plan_place_tool(public, admin, api):
    api.start_round('MCP SVS place', event='svs')
    lead, a, b, c = fid(), fid(), fid(), fid()
    for f in (lead, a, b, c):
        status, data = api.admin('POST', '/api/admin/rounds/current/applications?event=svs',
                                 {'fid': f, 'profile': {'game_name': f'P{f}', 'alliance': 'MCP'}})
        assert status == 201, data
    plan = plan_doc(lead, a)
    plan['leaders'][0]['extra_joiners'] = []
    status, data = api.admin('PUT', '/api/admin/svs/rounds/current/plan', {'revision': 0, 'plan': plan})
    assert status == 200, data

    async with public() as cl:
        assert 'svs_plan_place' not in {t.name for t in (await cl.list_tools()).tools}

    async with admin() as cl:
        tools = {t.name: t for t in (await cl.list_tools()).tools}
        assert 'mode' in tools['svs_plan_place'].input_schema['properties']
        err, data = await call(cl, 'svs_plan_place', {'fid': b, 'leader_id': 'L1', 'mode': 'named'})
        assert not err, data
        assert data['revision'] == 2 and data['result']['placed'][0]['as'] == 'named'
        assert data['plan']['leaders'][0]['named_joiners'][1]['player'] == {'fid': b}
        # already placed: DOUBLE_BOOKED, then an explicit move
        err, data = await call(cl, 'svs_plan_place', {'fid': a, 'group_id': 'counter', 'mode': 'leader'})
        assert err and data['code'] == 'DOUBLE_BOOKED' and data['details']['leader_id'] == 'L1'
        err, data = await call(cl, 'svs_plan_place', {'fid': a, 'group_id': 'counter', 'mode': 'leader', 'move': True})
        assert not err and data['result']['moved'][0]['from']['position'] == 'named_joiner'
        # bulk: one skipped (already placed), one placed as extra
        err, data = await call(cl, 'svs_plan_place', {'fids': [b, c], 'leader_id': 'L1', 'mode': 'extra',
                                                     'expected_revision': data['revision']})
        assert not err, data
        assert [s['player']['fid'] for s in data['result']['skipped']] == [b]
        assert data['result']['skipped'][0]['where']['position'] == 'named_joiner'
        assert data['plan']['leaders'][0]['extra_joiners'] == [{'player': {'fid': c}}]
        err, data = await call(cl, 'svs_plan_place', {'fid': c, 'leader_id': 'L1', 'expected_revision': 1})
        assert err and data['code'] == 'PLAN_CONFLICT'
        err, data = await call(cl, 'svs_plan_place', {'leader_id': 'L1'})
        assert err and data['code'] == 'VALIDATION_ERROR'
        err, data = await call(cl, 'list_applications', {'event': 'svs', 'svs_filters': {'in_plan': 'no'}})
        assert not err and data['total'] == 0
        err, data = await call(cl, 'list_applications', {'event': 'svs', 'svs_filters': {'in_plan': 'yes'}})
        assert not err and data['total'] == 4
        assert {x['fid']: x['plan_place']['position'] for x in data['applications']}[c] == 'extra_joiner'
