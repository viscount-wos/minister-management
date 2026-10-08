"""SVS battle planner (phase 2): plan validation, double booking, revisions (409), generation limits, the share-link
lifecycle and the public read-only view (no plan without a valid token)."""
import copy

import pytest

from app import create_app
from tests.conftest import ADMIN_PW, start_round

EVENT = 'svs'


def troops(camp='FC10', tier=11):
    return {k: {'furnace_level': camp, 'tier': tier} for k in ('infantry', 'lancer', 'marksman')}


def signup(client, fid, name, camp='FC10', tier=11, alliance='ABC'):
    r = client.put(f'/api/events/svs/current/application/{fid}',
                   json={'profile': {'game_name': name, 'alliance': alliance, 'troops': troops(camp, tier)},
                         'answers': {'hours': ['11:00', '12:00'], 'discord_vc': True}})
    assert r.status_code in (200, 201), r.json


def leader(lid, gid, fid=None, **kw):
    ld = {'id': lid, 'group_id': gid, 'order': 0, 'player': {'fid': fid} if fid else None,
          'disguise': {'pfp_hero': None, 'alias': None}, 'split': False,
          'rally': {'heroes': ['jeronimo', 'molly', 'zinman'], 'ratio': {'inf': 50, 'lan': 20, 'mks': 30}},
          'garrison': None, 'pet_buff': 'open', 'named_joiners': [], 'other_joiner_heroes': {'rally': [], 'garrison': []},
          'extra_joiners': []}
    ld.update(kw)
    return ld


def base_plan(leaders=()):
    return {'strategy': 'main_counter', 'show_real_names': True,
            'groups': [{'id': 'main', 'kind': 'main', 'name': 'Main', 'alliance_tag': 'ABC',
                        'min_requirements': {'infantry': {'min_camp': 'FC8', 'min_tier': 11}}},
                       {'id': 'counter', 'kind': 'counter', 'name': 'Counter', 'alliance_tag': 'XYZ'}],
            'leaders': list(leaders)}


@pytest.fixture
def svs(client, admin):
    rnd = start_round(client, admin, 'SVS 1', event=EVENT)
    for fid, name in [('9001', 'Alpha'), ('9002', 'Bravo'), ('9003', 'Charlie'),
                      ('9004', 'Delta'), ('9005', 'Echo'), ('9006', 'Foxtrot')]:
        signup(client, fid, name)
    return rnd


def get_plan(client, admin, ref='current'):
    r = client.get(f'/api/admin/svs/rounds/{ref}/plan', headers=admin)
    assert r.status_code == 200, r.json
    return r.json


def put_plan(client, admin, plan, revision, ref='current'):
    return client.put(f'/api/admin/svs/rounds/{ref}/plan', json={'revision': revision, 'plan': plan}, headers=admin)


def share(client, admin, action, ref='current'):
    r = client.post(f'/api/admin/svs/rounds/{ref}/plan/share', json={'action': action}, headers=admin)
    assert r.status_code == 200, r.json
    return r.json['share']


# ---------------------------------------------------------------- basics

def test_empty_plan_and_context(client, admin, svs):
    body = get_plan(client, admin)
    assert body['revision'] == 0 and body['updated_at'] is None
    assert body['plan']['strategy'] == 'main_counter'
    assert [g['kind'] for g in body['plan']['groups']] == ['main', 'counter']
    assert body['plan']['leaders'] == []
    assert body['share'] == {'enabled': False, 'token': None, 'path': None, 'created_at': None}
    assert body['battle'] == {'start': '11:00', 'hours': 5, 'end': '16:00'}
    assert body['pet_buff_times'] == {'open': '11:00', 'two_hours': '13:00', 'last_hour': '15:00'}
    assert body['state_generation'] == 17


def test_admin_only(client, svs):
    assert client.get('/api/admin/svs/rounds/current/plan').status_code == 401
    assert client.put('/api/admin/svs/rounds/current/plan', json={'revision': 0, 'plan': base_plan()}).status_code == 401
    assert client.post('/api/admin/svs/rounds/current/plan/share', json={'action': 'create'}).status_code == 401


def test_save_normalises_and_bumps_revision(client, admin, svs):
    ld = leader('L1', 'main', '9001', split=True,
                garrison={'heroes': ['natalia'], 'ratio': {'inf': 60, 'lan': 20, 'mks': 20}},
                disguise={'pfp_hero': 'flint', 'alias': ' Rally Caller 01 '},
                named_joiners=[{'player': {'fid': '9003'}, 'rally': {'lead_hero': 'jessie'},
                                'garrison': {'lead_hero': 'sergey', 'ratio_override': {'inf': 70, 'lan': 10, 'mks': 20}}},
                               {'player': {'name': 'Quick Guy'}, 'rally': {'lead_hero': 'jessie'}}],
                other_joiner_heroes={'rally': ['jessie', 'jessie', 'sergey'], 'garrison': ['patrick']},
                extra_joiners=[{'player': {'fid': '9004'}}, {'player': None}])
    r = put_plan(client, admin, base_plan([ld, leader('L2', 'counter', '9002', order=5)]), 0)
    assert r.status_code == 200, r.json
    body = r.json
    assert body['revision'] == 1 and body['updated_at']
    plan = body['plan']
    l1 = plan['leaders'][0]
    assert l1['disguise']['alias'] == 'Rally Caller 01'
    assert l1['garrison']['heroes'] == ['natalia', None, None]
    assert len(l1['named_joiners']) == 4 and l1['named_joiners'][2]['player'] is None
    assert l1['extra_joiners'] == [{'player': {'fid': '9004'}}]
    assert plan['leaders'][1]['order'] == 0  # renumbered per group
    assert plan['groups'][0]['min_requirements']['lancer'] == {'min_camp': None, 'min_tier': None}
    assert body['people']['9001'] == {'game_name': 'Alpha', 'alliance': 'ABC', 'signed_up': True}
    # resolved view: inherited vs overridden joiner ratios, pet-buff time, hero objects
    v = body['view']['groups'][0]['leaders'][0]
    assert v['player']['name'] == 'Alpha' and v['alias'] == 'Rally Caller 01' and v['pfp_hero']['name'] == 'Flint'
    assert v['pet_buff_time'] == '11:00'
    j = v['named_joiners'][0]
    assert j['rally']['ratio'] == {'inf': 50, 'lan': 20, 'mks': 30} and not j['rally']['ratio_overridden']
    assert j['garrison']['ratio'] == {'inf': 70, 'lan': 10, 'mks': 20} and j['garrison']['ratio_overridden']
    assert v['named_joiners'][1]['player'] == {'name': 'Quick Guy', 'fid': None, 'alliance': None}
    assert [h['slug'] for h in v['rally']['other_joiner_heroes']] == ['jessie', 'jessie', 'sergey']
    assert get_plan(client, admin)['revision'] == 1


def test_garrison_kept_while_unsplit_but_hidden(client, admin, svs):
    ld = leader('L1', 'main', '9001', split=False, garrison={'heroes': ['natalia'], 'ratio': None})
    body = put_plan(client, admin, base_plan([ld]), 0).json
    assert body['plan']['leaders'][0]['garrison']['heroes'][0] == 'natalia'
    assert body['view']['groups'][0]['leaders'][0]['garrison'] is None


@pytest.mark.parametrize('mutate, field', [
    (lambda p: p['leaders'][0]['rally'].update(ratio={'inf': 50, 'lan': 20, 'mks': 20}), 'plan.leaders[0].rally.ratio'),
    (lambda p: p['leaders'][0]['rally'].update(ratio={'inf': 50.5, 'lan': 20, 'mks': 29.5}), 'plan.leaders[0].rally.ratio.inf'),
    (lambda p: p['leaders'][0]['rally'].update(heroes=['jeronimo', 'jeronimo']), 'plan.leaders[0].rally.heroes'),
    (lambda p: p['leaders'][0]['rally'].update(heroes=['nobody']), 'plan.leaders[0].rally.heroes[0]'),
    (lambda p: p['leaders'][0]['rally'].update(heroes=['a', 'b', 'c', 'd']), 'plan.leaders[0].rally.heroes'),
    (lambda p: p['leaders'][0].update(pet_buff='noon'), 'plan.leaders[0].pet_buff'),
    (lambda p: p['leaders'][0].update(group_id='nope'), 'plan.leaders[0].group_id'),
    (lambda p: p['leaders'][0].update(named_joiners=[{}] * 5), 'plan.leaders[0].named_joiners'),
    (lambda p: p['leaders'][0].update(extra_joiners=[{'player': {'name': f'x{i}'}} for i in range(15)]),
     'plan.leaders[0].extra_joiners'),
    (lambda p: p['leaders'][0].update(other_joiner_heroes={'rally': ['jessie'] * 5}),
     'plan.leaders[0].other_joiner_heroes.rally'),
    (lambda p: p['leaders'][0].update(player={'fid': 'x y'}), 'plan.leaders[0].player.fid'),
    (lambda p: p['leaders'][0].update(player={}), 'plan.leaders[0].player'),
    (lambda p: p['leaders'][0].update(disguise={'alias': 'x' * 31}), 'plan.leaders[0].disguise.alias'),
    (lambda p: p['leaders'].append(leader('L1', 'counter')), 'plan.leaders'),
    (lambda p: p.update(strategy='single'), 'plan.groups'),
    (lambda p: p.update(strategy='blitz'), 'plan.strategy'),
    (lambda p: p['groups'][0].update(min_requirements={'infantry': {'min_tier': 9}}),
     'plan.groups[0].min_requirements.infantry.min_tier'),
    (lambda p: p['groups'][0].update(min_requirements={'infantry': {'min_camp': '25'}}),
     'plan.groups[0].min_requirements.infantry.min_camp'),
    (lambda p: p['groups'].append({'id': 'main', 'kind': 'extra'}), 'plan.groups'),
])
def test_validation(client, admin, svs, mutate, field):
    plan = base_plan([leader('L1', 'main', '9001')])
    mutate(plan)
    r = put_plan(client, admin, plan, 0)
    assert r.status_code == 400 and r.json['code'] == 'VALIDATION_ERROR' and r.json['field'] == field, r.json
    assert get_plan(client, admin)['revision'] == 0  # nothing written


def test_single_strategy_and_extra_group(client, admin, svs):
    plan = {'strategy': 'single', 'groups': [
        {'id': 'g1', 'kind': 'main', 'name': 'All in'},
        {'id': 'tur', 'kind': 'extra', 'name': 'Turrets', 'notes': 'Hold the north turret',
         'players': [{'fid': '9005'}, {'name': 'Walk-in'}]}],
        'leaders': [leader('L1', 'g1', '9001')]}
    r = put_plan(client, admin, plan, 0)
    assert r.status_code == 200, r.json
    groups = r.json['view']['groups']
    assert [g['kind'] for g in groups] == ['main', 'extra']
    assert [p['name'] for p in groups[1]['players']] == ['Echo', 'Walk-in']
    # leaders can't sit in an extra group
    plan['leaders'][0]['group_id'] = 'tur'
    assert put_plan(client, admin, plan, 1).json['field'] == 'plan.leaders[0].group_id'


# ---------------------------------------------------------------- double booking

@pytest.mark.parametrize('second', ['leader', 'named', 'extra', 'extra_group'])
def test_double_booking_rejected(client, admin, svs, second):
    first = leader('L1', 'main', '9001', disguise={'pfp_hero': None, 'alias': 'Rally Caller 01'},
                   named_joiners=[{'player': {'fid': '9003'}}])
    other = leader('L2', 'counter', '9002')
    plan = base_plan([first, other])
    if second == 'leader':
        other['player'] = {'fid': '9003'}
    elif second == 'named':
        other['named_joiners'] = [{'player': {'fid': '9003'}}]
    elif second == 'extra':
        other['extra_joiners'] = [{'player': {'fid': '9003'}}]
    else:
        plan['groups'].append({'id': 'x', 'kind': 'extra', 'name': 'Turrets', 'players': [{'fid': '9003'}]})
    r = put_plan(client, admin, plan, 0)
    assert r.status_code == 422 and r.json['code'] == 'DOUBLE_BOOKED', r.json
    d = r.json['details']
    assert d['leader_id'] == 'L1' and d['leader_label'] == 'Rally Caller 01' and d['position'] == 'named_joiner'
    assert d['group_id'] == 'main' and d['group_name'] == 'Main' and d['player_name'] == 'Charlie'
    assert 'Rally Caller 01' in r.json['error']
    assert get_plan(client, admin)['revision'] == 0


def test_double_booking_same_leader_and_quick_add_names(client, admin, svs):
    ld = leader('L1', 'main', '9001', named_joiners=[{'player': {'fid': '9001'}}])
    r = put_plan(client, admin, base_plan([ld]), 0)
    assert r.status_code == 422 and r.json['details']['position'] == 'leader'
    ld = leader('L1', 'main', None, extra_joiners=[{'player': {'name': 'Walk In'}}, {'player': {'name': ' walk  in '}}])
    r = put_plan(client, admin, base_plan([ld]), 0)
    assert r.status_code == 422 and r.json['field'] == 'plan.leaders[0].extra_joiners[1].player'
    # different quick-add names are fine; an FID ref with a name is keyed by the FID
    ld = leader('L1', 'main', None, extra_joiners=[{'player': {'name': 'Walk In'}}, {'player': {'name': 'Walk Out'}},
                                                   {'player': {'fid': '9006', 'name': 'Walk In'}}])
    assert put_plan(client, admin, base_plan([ld]), 0).status_code == 200


# ---------------------------------------------------------------- revisions

def test_stale_revision_conflict(client, admin, svs):
    assert put_plan(client, admin, base_plan([leader('L1', 'main', '9001')]), 0).status_code == 200
    # a second editor still on revision 0
    r = put_plan(client, admin, base_plan([leader('L9', 'main', '9002')]), 0)
    assert r.status_code == 409 and r.json['code'] == 'PLAN_CONFLICT' and r.json['details']['revision'] == 1
    body = get_plan(client, admin)
    assert body['revision'] == 1 and [ld['id'] for ld in body['plan']['leaders']] == ['L1']
    for bad in (None, -1, '1', True):
        r = put_plan(client, admin, base_plan(), bad)
        assert r.status_code == 400 and r.json['field'] == 'revision'
    assert put_plan(client, admin, base_plan(), 1).json['revision'] == 2
    # share actions don't bump the revision
    share(client, admin, 'create')
    assert get_plan(client, admin)['revision'] == 2


def test_closed_round_read_only(client, admin, svs):
    put_plan(client, admin, base_plan([leader('L1', 'main', '9001')]), 0)
    start_round(client, admin, 'SVS 2', event=EVENT)  # closes SVS 1
    r = put_plan(client, admin, base_plan(), 1, ref=svs['id'])
    assert r.status_code == 409 and r.json['code'] == 'ROUND_CLOSED'
    assert get_plan(client, admin, ref=svs['id'])['revision'] == 1
    assert get_plan(client, admin)['revision'] == 0  # the new round has its own (empty) plan


def test_plan_is_svs_only(client, admin, svs):
    other = start_round(client, admin, 'Minister', event='ministry')
    assert client.get(f'/api/admin/svs/rounds/{other["id"]}/plan', headers=admin).status_code == 404


# ---------------------------------------------------------------- generation limit

def test_generation_limit(client, admin, svs):
    assert client.put('/api/admin/settings', json={'state_generation': 5}, headers=admin).status_code == 200
    ld = leader('L1', 'main', '9001')
    ld['rally']['heroes'] = ['gatot', 'molly', None]  # Gatot is generation 8
    r = put_plan(client, admin, base_plan([ld]), 0)
    assert r.status_code == 400 and r.json['field'] == 'plan.leaders[0].rally.heroes[0]'
    assert r.json['details'] == {'hero': 'gatot', 'generation': 8, 'state_generation': 5}
    ld['rally']['heroes'] = ['hector', 'molly', 'sergey']  # gen 5, gen 1, epic (no generation): fine
    ld['named_joiners'] = [{'player': {'fid': '9003'}, 'rally': {'lead_hero': 'ling-xue'}}]
    assert put_plan(client, admin, base_plan([ld]), 0).status_code == 200
    # a hero saved before the generation was lowered stays allowed (the old plan stays editable) ...
    client.put('/api/admin/settings', json={'state_generation': 9}, headers=admin)
    ld['rally']['heroes'] = ['gatot', 'molly', 'sergey']
    assert put_plan(client, admin, base_plan([ld]), 1).status_code == 200
    client.put('/api/admin/settings', json={'state_generation': 5}, headers=admin)
    ld['extra_joiners'] = [{'player': {'fid': '9004'}}]
    assert put_plan(client, admin, base_plan([ld]), 2).status_code == 200
    # ... but a NEW one above the limit is not
    ld['other_joiner_heroes'] = {'rally': ['sonya']}
    r = put_plan(client, admin, base_plan([ld]), 3)
    assert r.status_code == 400 and r.json['field'] == 'plan.leaders[0].other_joiner_heroes.rally[0]'


# ---------------------------------------------------------------- share link + public view

def test_share_lifecycle_and_public_view(client, admin, svs):
    ld = leader('L1', 'main', '9001', disguise={'pfp_hero': 'flint', 'alias': 'Rally Caller 01'},
                named_joiners=[{'player': {'fid': '9003'}, 'rally': {'lead_hero': 'jessie'}}])
    put_plan(client, admin, base_plan([ld]), 0)
    s1 = share(client, admin, 'create')
    assert s1['enabled'] and len(s1['token']) == 22 and s1['path'] == f'/svs/plan/{s1["token"]}'
    assert share(client, admin, 'create')['token'] == s1['token']  # idempotent
    r = client.get(f'/api/svs/plan/{s1["token"]}')
    assert r.status_code == 200, r.json
    assert r.headers['X-Robots-Tag'].startswith('noindex')
    assert r.headers['Referrer-Policy'] == 'no-referrer' and r.headers['Cache-Control'] == 'no-store'
    v = r.json
    assert v['round_name'] == 'SVS 1' and v['battle']['start'] == '11:00'
    lv = v['groups'][0]['leaders'][0]
    assert lv['alias'] == 'Rally Caller 01' and lv['player']['name'] == 'Alpha'
    assert lv['named_joiners'][0]['player']['name'] == 'Charlie'
    assert 'share' not in v and 'people' not in v and 'token' not in str(v)
    # rotate: the old link dies at once
    s2 = share(client, admin, 'rotate')
    assert s2['token'] != s1['token']
    assert client.get(f'/api/svs/plan/{s1["token"]}').status_code == 404
    assert client.get(f'/api/svs/plan/{s2["token"]}').status_code == 200
    # disable
    s3 = share(client, admin, 'disable')
    assert s3 == {'enabled': False, 'token': None, 'path': None, 'created_at': None}
    r = client.get(f'/api/svs/plan/{s2["token"]}')
    assert r.status_code == 404 and r.json['code'] == 'PLAN_NOT_FOUND'
    assert r.headers['X-Robots-Tag'].startswith('noindex')
    r = client.post('/api/admin/svs/rounds/current/plan/share', json={'action': 'publish'}, headers=admin)
    assert r.status_code == 400 and r.json['field'] == 'action'


def test_public_view_needs_a_valid_token(client, admin, svs):
    put_plan(client, admin, base_plan([leader('L1', 'main', '9001')]), 0)
    for token in ('x', 'A' * 22, '..%2F..', 'a' * 65, ''):
        r = client.get(f'/api/svs/plan/{token}')
        assert r.status_code == 404, (token, r.status_code)
        assert 'Alpha' not in r.get_data(as_text=True)
    # an unshared plan is not reachable at all
    assert client.get('/api/svs/plan/').status_code == 404


def test_real_names_toggle(client, admin, svs):
    plan = base_plan([leader('L1', 'main', '9001', disguise={'pfp_hero': 'flint', 'alias': 'RC 01'}),
                      leader('L2', 'counter', '9002')])
    plan['show_real_names'] = False
    put_plan(client, admin, plan, 0)
    token = share(client, admin, 'create')['token']
    v = client.get(f'/api/svs/plan/{token}').json
    l1 = v['groups'][0]['leaders'][0]
    assert l1['player'] is None and l1['alias'] == 'RC 01'
    assert 'Alpha' not in str(v) and '9001' not in str(v)
    assert v['groups'][1]['leaders'][0]['player']['name'] == 'Bravo'  # no alias: nothing to hide
    # the admin view always has the real names
    assert get_plan(client, admin)['view']['groups'][0]['leaders'][0]['player']['name'] == 'Alpha'


def test_spa_route_headers(client, admin, svs):
    r = client.get('/svs/plan/whatever-token-123456')
    assert r.headers['Referrer-Policy'] == 'no-referrer' and r.headers['X-Robots-Tag'].startswith('noindex')
    assert client.get('/svs').headers['Referrer-Policy'] != 'no-referrer'


def test_public_view_rate_limited(db_path):
    app = create_app({'TESTING': True, 'DATABASE_PATH': db_path, 'SECRET_KEY': 'test-secret-key-not-a-placeholder',
                      'ADMIN_PASSWORD': ADMIN_PW, 'STATIC_DIR': '/nonexistent',
                      'RATE_LIMIT_LOOKUPS_PER_MIN': 3, 'RATE_LIMIT_SUBMITS_PER_MIN': 0})
    c = app.test_client()
    codes = [c.get('/api/svs/plan/' + 'B' * 22).status_code for _ in range(5)]
    assert codes[:3] == [404] * 3 and codes[3:] == [429, 429]


def test_view_is_deterministic_copy(client, admin, svs):
    """GET returns what PUT stored (round-trip): re-saving the returned plan is a no-op apart from the revision."""
    put_plan(client, admin, base_plan([leader('L1', 'main', '9001'), leader('L2', 'main', '9002', order=1)]), 0)
    body = get_plan(client, admin)
    again = put_plan(client, admin, copy.deepcopy(body['plan']), 1).json
    assert again['plan'] == body['plan'] and again['revision'] == 2
