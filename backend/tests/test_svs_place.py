"""SVS \"Add to rally\" (players table): POST /api/admin/svs/rounds/<ref>/plan/place, applied atomically to the stored
plan: every `as` mode, capacity limits (4 named / 14 extra), double booking, move, revision conflict, bulk reports,
and the players list's plan_place + in_plan filter + summary counts."""
import pytest

from tests.conftest import start_round
from tests.test_svs_plan import base_plan, get_plan, leader, put_plan, signup

URL = '/api/admin/svs/rounds/current/plan/place'
FIDS = [str(9100 + i) for i in range(22)]


@pytest.fixture
def svs(client, admin):
    rnd = start_round(client, admin, 'SVS place', event='svs')
    for i, fid in enumerate(FIDS):
        signup(client, fid, f'P{i:02d}')
    plan = base_plan([leader('L1', 'main', FIDS[0], disguise={'pfp_hero': None, 'alias': 'Rally Caller 01'}),
                      leader('L2', 'counter', FIDS[1])])
    plan['groups'].append({'id': 'tur', 'kind': 'extra', 'name': 'Turrets', 'players': []})
    r = put_plan(client, admin, plan, 0)
    assert r.status_code == 200, r.json
    return rnd


def place(client, admin, **body):
    return client.post(URL, json=body, headers=admin)


def ld(body, lid):
    return next(x for x in body['plan']['leaders'] if x['id'] == lid)


def test_named_then_extra_modes(client, admin, svs):
    r = place(client, admin, fid=FIDS[2], leader_id='L1', **{'as': 'named'})
    assert r.status_code == 200, r.json
    b = r.json
    assert b['changed'] is True and b['revision'] == 2
    assert ld(b, 'L1')['named_joiners'][0]['player'] == {'fid': FIDS[2]}
    assert ld(b, 'L1')['named_joiners'][0]['rally']['lead_hero'] is None  # lead hero left for the planner
    assert b['result']['placed'][0]['as'] == 'named' and b['result']['placed'][0]['slot'] == 0
    r = place(client, admin, fid=FIDS[3], leader_id='L1', **{'as': 'extra'})
    assert r.status_code == 200
    assert ld(r.json, 'L1')['extra_joiners'] == [{'player': {'fid': FIDS[3]}}]
    # the plan survived intact (heroes, alias) and the GET agrees
    g = get_plan(client, admin)
    assert g['revision'] == 3 and ld(g, 'L1')['disguise']['alias'] == 'Rally Caller 01'
    assert ld(g, 'L1')['rally']['heroes'] == ['jeronimo', 'molly', 'zinman']


def test_named_slot_choice_and_slot_taken(client, admin, svs):
    r = place(client, admin, fid=FIDS[2], leader_id='L1', slot=2, **{'as': 'named'})
    assert r.status_code == 200 and ld(r.json, 'L1')['named_joiners'][2]['player'] == {'fid': FIDS[2]}
    r = place(client, admin, fid=FIDS[3], leader_id='L1', slot=2, **{'as': 'named'})
    assert r.status_code == 422 and r.json['code'] == 'SLOT_TAKEN'
    r = place(client, admin, fid=FIDS[3], leader_id='L1', slot=1, **{'as': 'extra'})
    assert r.status_code == 400 and r.json['field'] == 'slot'


def test_auto_fills_named_then_extra_and_capacity(client, admin, svs):
    # 4 named, then 14 extra, then full
    for i, fid in enumerate(FIDS[2:20]):
        r = place(client, admin, fid=fid, leader_id='L1', **{'as': 'auto'})
        assert r.status_code == 200, (i, r.json)
        assert r.json['result']['placed'][0]['as'] == ('named' if i < 4 else 'extra')
    b = get_plan(client, admin)
    assert sum(1 for j in ld(b, 'L1')['named_joiners'] if j['player']) == 4
    assert len(ld(b, 'L1')['extra_joiners']) == 14
    rev = b['revision']
    for mode in ('auto', 'named', 'extra'):
        r = place(client, admin, fid=FIDS[20], leader_id='L1', **{'as': mode})
        assert r.status_code == 422 and r.json['code'] == 'RALLY_FULL', r.json
        assert r.json['details']['named_used'] == 4 and r.json['details']['extra_used'] == 14
    assert get_plan(client, admin)['revision'] == rev  # nothing written


def test_named_full_goes_to_extra_only_when_asked(client, admin, svs):
    for fid in FIDS[2:6]:
        assert place(client, admin, fid=fid, leader_id='L1', **{'as': 'named'}).status_code == 200
    r = place(client, admin, fid=FIDS[6], leader_id='L1', **{'as': 'named'})
    assert r.status_code == 422 and r.json['code'] == 'RALLY_FULL'
    r = place(client, admin, fid=FIDS[6], leader_id='L1', **{'as': 'auto'})
    assert r.status_code == 200 and r.json['result']['placed'][0]['as'] == 'extra'


def test_leader_and_group_modes(client, admin, svs):
    r = place(client, admin, fid=FIDS[2], group_id='counter', **{'as': 'leader'})
    assert r.status_code == 200, r.json
    new = [x for x in r.json['plan']['leaders'] if x['player'] == {'fid': FIDS[2]}]
    assert len(new) == 1 and new[0]['group_id'] == 'counter' and new[0]['order'] == 1
    assert r.json['result']['placed'][0]['leader_id'] == new[0]['id']
    r = place(client, admin, fid=FIDS[3], group_id='tur', **{'as': 'group'})
    assert r.status_code == 200
    tur = next(g for g in r.json['plan']['groups'] if g['id'] == 'tur')
    assert tur['players'] == [{'fid': FIDS[3]}]
    # wrong group kinds
    r = place(client, admin, fid=FIDS[4], group_id='tur', **{'as': 'leader'})
    assert r.status_code == 400 and r.json['field'] == 'group_id'
    r = place(client, admin, fid=FIDS[4], group_id='main', **{'as': 'group'})
    assert r.status_code == 400
    r = place(client, admin, fid=FIDS[4], group_id='nope', **{'as': 'group'})
    assert r.status_code == 404 and r.json['code'] == 'GROUP_NOT_FOUND'
    r = place(client, admin, fid=FIDS[4], leader_id='nope', **{'as': 'named'})
    assert r.status_code == 404 and r.json['code'] == 'LEADER_NOT_FOUND'
    r = place(client, admin, fid=FIDS[4], leader_id='L1', **{'as': 'boss'})
    assert r.status_code == 400 and r.json['field'] == 'as'


def test_fill_empty_leader_card(client, admin, svs):
    plan = get_plan(client, admin)
    doc = plan['plan']
    doc['leaders'].append(leader('L3', 'main'))
    assert put_plan(client, admin, doc, plan['revision']).status_code == 200
    r = place(client, admin, fid=FIDS[5], leader_id='L3', **{'as': 'leader'})
    assert r.status_code == 200 and ld(r.json, 'L3')['player'] == {'fid': FIDS[5]}
    r = place(client, admin, fid=FIDS[6], leader_id='L3', **{'as': 'leader'})
    assert r.status_code == 422 and r.json['code'] == 'SLOT_TAKEN'


def test_double_booking_and_move(client, admin, svs):
    assert place(client, admin, fid=FIDS[2], leader_id='L1', **{'as': 'named'}).status_code == 200
    # already a named joiner of L1 -> refused at L2 without move
    r = place(client, admin, fid=FIDS[2], leader_id='L2', **{'as': 'extra'})
    assert r.status_code == 422 and r.json['code'] == 'DOUBLE_BOOKED'
    d = r.json['details']
    assert d['leader_id'] == 'L1' and d['position'] == 'named_joiner' and d['leader_label'] == 'Rally Caller 01'
    # a leader cannot be added as a joiner either
    r = place(client, admin, fid=FIDS[1], leader_id='L1', **{'as': 'named'})
    assert r.status_code == 422 and r.json['details']['position'] == 'leader'
    # explicit move: gone from L1, now an extra of L2
    r = place(client, admin, fid=FIDS[2], leader_id='L2', move=True, **{'as': 'extra'})
    assert r.status_code == 200, r.json
    assert all(j['player'] is None for j in ld(r.json, 'L1')['named_joiners'])
    assert ld(r.json, 'L2')['extra_joiners'] == [{'player': {'fid': FIDS[2]}}]
    assert r.json['result']['moved'][0]['from']['leader_id'] == 'L1'
    # moving a leader keeps their card (empty)
    r = place(client, admin, fid=FIDS[1], leader_id='L1', move=True, **{'as': 'named'})
    assert r.status_code == 200 and ld(r.json, 'L2')['player'] is None
    assert ld(r.json, 'L2')['rally']['heroes'] == ['jeronimo', 'molly', 'zinman']
    # already exactly there: no write, no new revision
    rev = r.json['revision']
    r = place(client, admin, fid=FIDS[1], leader_id='L1', **{'as': 'auto'})
    assert r.status_code == 200 and r.json['changed'] is False and r.json['revision'] == rev
    assert r.json['result']['unchanged'][0]['player'] == {'fid': FIDS[1]}


def test_move_refused_when_full_keeps_player(client, admin, svs):
    assert place(client, admin, fid=FIDS[2], leader_id='L2', **{'as': 'named'}).status_code == 200
    for fid in FIDS[3:7]:
        assert place(client, admin, fid=fid, leader_id='L1', **{'as': 'named'}).status_code == 200
    r = place(client, admin, fid=FIDS[2], leader_id='L1', move=True, **{'as': 'named'})
    assert r.status_code == 422 and r.json['code'] == 'RALLY_FULL'
    assert ld(get_plan(client, admin), 'L2')['named_joiners'][0]['player'] == {'fid': FIDS[2]}


def test_revision_conflict(client, admin, svs):
    rev = get_plan(client, admin)['revision']
    r = place(client, admin, fid=FIDS[2], leader_id='L1', expected_revision=rev - 1, **{'as': 'named'})
    assert r.status_code == 409 and r.json['code'] == 'PLAN_CONFLICT' and r.json['details']['revision'] == rev
    assert get_plan(client, admin)['revision'] == rev
    r = place(client, admin, fid=FIDS[2], leader_id='L1', expected_revision=rev, **{'as': 'named'})
    assert r.status_code == 200 and r.json['revision'] == rev + 1
    # the planner's next save with the old revision now conflicts (never a silent overwrite)
    g = get_plan(client, admin)
    r = put_plan(client, admin, g['plan'], rev)
    assert r.status_code == 409


def test_never_clobbers_other_edits(client, admin, svs):
    """Someone saved a change after we loaded: a place without expected_revision merges onto THEIR plan."""
    g = get_plan(client, admin)
    doc = g['plan']
    for x in doc['leaders']:
        if x['id'] == 'L2':
            x['pet_buff'] = 'last_hour'
    assert put_plan(client, admin, doc, g['revision']).status_code == 200
    r = place(client, admin, fid=FIDS[2], leader_id='L1', **{'as': 'named'})
    assert r.status_code == 200 and ld(r.json, 'L2')['pet_buff'] == 'last_hour'


def test_bulk_reports_skipped_and_overflow(client, admin, svs):
    assert place(client, admin, fid=FIDS[2], leader_id='L2', **{'as': 'named'}).status_code == 200
    # L1 has room for 4 named + 14 extra = 18; send 20 incl. one already placed + one leader + an unknown FID
    fids = FIDS[2:22] + ['555555']
    r = place(client, admin, fids=fids, leader_id='L1', **{'as': 'auto'})
    assert r.status_code == 200, r.json
    res = r.json['result']
    assert [s['player']['fid'] for s in res['skipped']] == [FIDS[2]]
    assert res['skipped'][0]['reason'] == 'already_placed' and res['skipped'][0]['where']['leader_id'] == 'L2'
    assert [p['as'] for p in res['placed']] == ['named'] * 4 + ['extra'] * 14
    assert [p['player']['fid'] for p in res['overflow']] == [FIDS[21]]
    assert res['not_found'] == [{'player': {'fid': '555555'}}]
    b = r.json
    assert sum(1 for j in ld(b, 'L1')['named_joiners'] if j['player']) == 4 and len(ld(b, 'L1')['extra_joiners']) == 14


def test_bulk_extra_group_and_validation(client, admin, svs):
    r = place(client, admin, fids=[FIDS[2], FIDS[3], FIDS[2]], group_id='tur', **{'as': 'group'})
    assert r.status_code == 200
    assert next(g for g in r.json['plan']['groups'] if g['id'] == 'tur')['players'] == [{'fid': FIDS[2]}, {'fid': FIDS[3]}]
    assert place(client, admin, fids=[], leader_id='L1').status_code == 400
    assert place(client, admin, fids=[str(i) for i in range(101)], leader_id='L1').status_code == 400
    assert place(client, admin, leader_id='L1').status_code == 400
    r = place(client, admin, fid='777777', leader_id='L1')
    assert r.status_code == 404 and r.json['code'] == 'PLAYER_NOT_FOUND'
    assert client.post(URL, json={'fid': FIDS[5], 'leader_id': 'L1'}).status_code == 401


def test_no_plan_yet(client, admin):
    start_round(client, admin, 'SVS empty', event='svs')
    signup(client, '9300', 'Solo')
    r = place(client, admin, fid='9300', leader_id='L1', **{'as': 'named'})
    assert r.status_code == 404 and r.json['code'] == 'LEADER_NOT_FOUND'
    r = place(client, admin, fid='9300', group_id='main', **{'as': 'leader'}, expected_revision=0)
    assert r.status_code == 200 and r.json['revision'] == 1
    assert r.json['plan']['leaders'][0]['player'] == {'fid': '9300'}


def test_players_list_plan_place_and_filter(client, admin, svs):
    place(client, admin, fid=FIDS[2], leader_id='L1', **{'as': 'named'})
    place(client, admin, fid=FIDS[3], group_id='tur', **{'as': 'group'})
    r = client.get('/api/admin/svs/rounds/current/applications?limit=100', headers=admin)
    by = {a['fid']: a['plan_place'] for a in r.json['applications']}
    assert by[FIDS[0]]['position'] == 'leader' and by[FIDS[0]]['group_kind'] == 'main'
    assert by[FIDS[2]] == {'group_id': 'main', 'group_kind': 'main', 'leader_id': 'L1', 'position': 'named_joiner',
                           'slot': 0}
    assert by[FIDS[3]]['position'] == 'extra_group' and by[FIDS[4]] is None
    r = client.get('/api/admin/svs/rounds/current/applications?in_plan=yes', headers=admin)
    assert sorted(a['fid'] for a in r.json['applications']) == sorted([FIDS[0], FIDS[1], FIDS[2], FIDS[3]])
    r = client.get('/api/admin/svs/rounds/current/applications?in_plan=no', headers=admin)
    assert r.json['total'] == len(FIDS) - 4
    s = client.get('/api/admin/svs/rounds/current/summary', headers=admin).json
    assert s['plan'] == {'in': 4, 'out': len(FIDS) - 4}
    s = client.get('/api/admin/svs/rounds/current/summary?in_plan=no', headers=admin).json
    assert s['total'] == len(FIDS) - 4 and s['filters']['in_plan'] == 'no'
    assert client.get('/api/admin/svs/rounds/current/applications?in_plan=maybe', headers=admin).status_code == 400
    r = client.get('/api/admin/svs/rounds/current/export.csv?in_plan=yes', headers=admin)
    assert r.status_code == 200 and len(r.data.decode().strip().splitlines()) == 5


def test_closed_round_refuses(client, admin, svs):
    rid = svs['id'] if isinstance(svs, dict) else svs
    start_round(client, admin, 'SVS next', event='svs')
    r = client.post(f'/api/admin/svs/rounds/{rid}/plan/place', json={'fid': FIDS[2], 'leader_id': 'L1'},
                    headers=admin)
    assert r.status_code == 409 and r.json['code'] == 'ROUND_CLOSED'
