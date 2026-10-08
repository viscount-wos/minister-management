"""Admin Edit / Delete in the SVS and Frost Dragon Tyrant player lists (v2.2.1).

Edit is the generic PUT /api/admin/applications/<id> (admin mode: blanks allowed, partial profile + answers merged
then validated). Name, alliance and troops live in the SHARED profile, so an edit through one event shows in the
others. Deleting an SVS sign-up also takes the player out of that round's battle plan, in the same transaction, with
a +1 plan revision.
"""
from tests.conftest import start_round
from tests.test_svs_plan import base_plan, get_plan, leader, put_plan, signup


def app_id(client, admin, event, fid, ref='current'):
    r = client.get(f'/api/admin/{event}/rounds/{ref}/applications', headers=admin)
    assert r.status_code == 200, r.json
    return next(a['id'] for a in r.json['applications'] if a['fid'] == fid)


def tyrant_signup(client, fid, name, alliance='TYR'):
    tr = {k: {'furnace_level': 'FC8', 'tier': 10} for k in ('infantry', 'lancer', 'marksman')}
    r = client.put(f'/api/events/tyrant/current/application/{fid}',
                   json={'profile': {'game_name': name, 'alliance': alliance, 'troops': tr, 'power': 400_000_000},
                         'answers': {'availability': ['w1'], 'discord_vc': False, 'gem_spend': 1000,
                                     'roles': ['joiner']}})
    assert r.status_code in (200, 201), r.json


def svs_with_plan(client, admin):
    rnd = start_round(client, admin, 'SVS edit', event='svs')
    for fid, name in [('9001', 'Alpha'), ('9002', 'Bravo'), ('9003', 'Charlie'), ('9004', 'Delta')]:
        signup(client, fid, name)
    named = [{'player': None, 'rally': {'lead_hero': None, 'ratio_override': None},
              'garrison': {'lead_hero': None, 'ratio_override': None}} for _ in range(4)]
    named[1]['player'] = {'fid': '9002'}
    named[1]['rally']['lead_hero'] = 'molly'
    plan = base_plan([leader('L1', 'main', '9001', disguise={'pfp_hero': None, 'alias': 'Rally Caller 01'},
                             named_joiners=named, extra_joiners=[{'player': {'fid': '9003'}}])])
    r = put_plan(client, admin, plan, 0)
    assert r.status_code == 200, r.json
    return rnd


# ---------------------------------------------------------------- SVS delete vs the battle plan

def test_svs_delete_named_joiner_removes_from_plan_atomically(client, admin):
    svs_with_plan(client, admin)
    rev = get_plan(client, admin)['revision']
    r = client.delete(f'/api/admin/applications/{app_id(client, admin, "svs", "9002")}', headers=admin)
    assert r.status_code == 200, r.json
    assert r.json['deleted'] is True and r.json['plan_revision'] == rev + 1
    [gone] = r.json['plan_removed']
    assert gone['position'] == 'named_joiner' and gone['slot'] == 1 and gone['leader_id'] == 'L1'
    assert gone['leader_label'] == 'Rally Caller 01'
    body = get_plan(client, admin)
    assert body['revision'] == rev + 1
    ld = body['plan']['leaders'][0]
    assert ld['named_joiners'][1]['player'] is None
    assert ld['named_joiners'][1]['rally']['lead_hero'] == 'molly'  # the slot keeps its heroes (planner "Move")
    assert ld['extra_joiners'] == [{'player': {'fid': '9003'}}]      # nobody else touched
    # an editor holding the old revision now gets a conflict instead of silently re-adding the player
    stale = put_plan(client, admin, body['plan'], rev)
    assert stale.status_code == 409 and stale.json['code'] == 'PLAN_CONFLICT'


def test_svs_delete_leader_and_extra(client, admin):
    svs_with_plan(client, admin)
    r = client.delete(f'/api/admin/applications/{app_id(client, admin, "svs", "9001")}', headers=admin)
    assert r.status_code == 200 and r.json['plan_removed'][0]['position'] == 'leader'
    r = client.delete(f'/api/admin/applications/{app_id(client, admin, "svs", "9003")}', headers=admin)
    assert r.status_code == 200 and r.json['plan_removed'][0]['position'] == 'extra_joiner'
    ld = get_plan(client, admin)['plan']['leaders'][0]
    assert ld['player'] is None and ld['disguise']['alias'] == 'Rally Caller 01'  # the card stays for a new leader
    assert ld['rally']['heroes'] == ['jeronimo', 'molly', 'zinman']
    assert ld['extra_joiners'] == []
    assert ld['named_joiners'][1]['player'] == {'fid': '9002'}


def test_svs_delete_not_in_plan_keeps_revision(client, admin):
    svs_with_plan(client, admin)
    rev = get_plan(client, admin)['revision']
    r = client.delete(f'/api/admin/applications/{app_id(client, admin, "svs", "9004")}', headers=admin)
    assert r.status_code == 200 and r.json['plan_removed'] == [] and r.json['plan_revision'] == rev
    assert get_plan(client, admin)['revision'] == rev


def test_svs_delete_without_any_plan(client, admin):
    start_round(client, admin, 'SVS no plan', event='svs')
    signup(client, '9010', 'Solo')
    r = client.delete(f'/api/admin/applications/{app_id(client, admin, "svs", "9010")}', headers=admin)
    assert r.status_code == 200 and r.json['plan_removed'] == [] and r.json['plan_revision'] == 0


def test_closed_round_delete_and_edit_refused_plan_untouched(client, admin):
    rnd = svs_with_plan(client, admin)
    aid = app_id(client, admin, 'svs', '9002')
    plan_before = get_plan(client, admin)
    start_round(client, admin, 'SVS next', event='svs')  # closes the first round
    r = client.delete(f'/api/admin/applications/{aid}', headers=admin)
    assert r.status_code == 409 and r.json['code'] == 'ROUND_CLOSED'
    r = client.put(f'/api/admin/applications/{aid}', json={'profile': {'game_name': 'Nope'}}, headers=admin)
    assert r.status_code == 409 and r.json['code'] == 'ROUND_CLOSED'
    after = get_plan(client, admin, ref=str(rnd['id']))
    assert after['revision'] == plan_before['revision'] and after['plan'] == plan_before['plan']


def test_ministry_delete_response_unchanged(client, admin):
    from tests.conftest import application_id, apply
    start_round(client, admin, 'Min')
    apply(client, '7001', expect=201)
    r = client.delete(f'/api/admin/applications/{application_id(client, admin, "7001")}', headers=admin)
    assert r.status_code == 200 and r.json == {'deleted': True, 'id': r.json['id']}


# ---------------------------------------------------------------- edit: shared profile + event answers

def test_svs_edit_shared_profile_shows_in_tyrant(client, admin):
    start_round(client, admin, 'FDT', event='tyrant')
    tyrant_signup(client, '9100', 'Before', alliance='OLD')
    start_round(client, admin, 'SVS', event='svs')
    signup(client, '9100', 'Before', camp='FC9', tier=10, alliance='OLD')
    aid = app_id(client, admin, 'svs', '9100')
    r = client.put(f'/api/admin/applications/{aid}', headers=admin, json={
        'profile': {'game_name': 'After', 'alliance': 'new',
                    'troops': {'infantry': {'furnace_level': 'FC10', 'tier': 11}}},
        'answers': {'hours': ['13:00'], 'discord_vc': False}})
    assert r.status_code == 200, r.json
    b = r.json
    assert b['profile']['game_name'] == 'After' and b['profile']['alliance'] == 'NEW'
    assert b['answers']['hours'] == ['13:00'] and b['answers']['discord_vc'] is False
    assert b['joiner_strength'] is not None and 'furnace_level' not in b['profile']
    tr = b['profile']['troops']
    # merge rule: the sent type/field replaces, the rest is kept
    assert tr['infantry'] == {'furnace_level': 'FC10', 'tier': 11}
    assert tr['lancer'] == {'furnace_level': 'FC9', 'tier': 10}
    # the Tyrant list reads the same shared profile
    rows = client.get('/api/admin/tyrant/rounds/current/applications', headers=admin).json['applications']
    row = next(a for a in rows if a['fid'] == '9100')
    assert row['profile']['game_name'] == 'After' and row['profile']['alliance'] == 'NEW'
    assert row['profile']['troops']['infantry'] == {'furnace_level': 'FC10', 'tier': 11}
    assert row['profile']['power'] == 400_000_000  # a field SVS doesn't show is untouched


def test_svs_edit_admin_blanks_and_rules(client, admin):
    start_round(client, admin, 'SVS', event='svs')
    signup(client, '9200', 'Blank')
    aid = app_id(client, admin, 'svs', '9200')
    # admin mode: no hours and an unknown VC are allowed
    r = client.put(f'/api/admin/applications/{aid}', json={'answers': {'hours': [], 'discord_vc': None}},
                   headers=admin)
    assert r.status_code == 200 and r.json['answers']['hours'] == [] and r.json['answers']['discord_vc'] is None
    # a blank troop value never clears what is stored
    r = client.put(f'/api/admin/applications/{aid}', headers=admin,
                   json={'profile': {'troops': {'lancer': {'furnace_level': None, 'tier': None}}}})
    assert r.status_code == 200 and r.json['profile']['troops']['lancer'] == {'furnace_level': 'FC10', 'tier': 11}
    # SVS tiers are T10/T11 only, on the right field
    r = client.put(f'/api/admin/applications/{aid}', headers=admin,
                   json={'profile': {'troops': {'infantry': {'tier': 9}}}})
    assert r.status_code == 400 and r.json['field'] == 'profile.troops.infantry.tier'
    # the name stays required; SVS ignores fields it doesn't ask (discord_id) instead of changing the profile
    r = client.put(f'/api/admin/applications/{aid}', json={'profile': {'game_name': ''}}, headers=admin)
    assert r.status_code == 400 and r.json['field'] == 'profile.game_name'
    r = client.put(f'/api/admin/applications/{aid}', json={'profile': {'discord_id': 'x#1'}}, headers=admin)
    assert r.status_code == 200 and not r.json['profile'].get('discord_id')


def test_svs_edit_keeps_an_old_hour(client, admin):
    rnd = start_round(client, admin, 'SVS', event='svs')
    signup(client, '9300', 'Early')  # 11:00 + 12:00
    r = client.put(f'/api/admin/rounds/{rnd["id"]}', json={'settings': {'battle_start': '12:00'}}, headers=admin)
    assert r.status_code == 200, r.json
    aid = app_id(client, admin, 'svs', '9300')
    r = client.put(f'/api/admin/applications/{aid}', json={'answers': {'hours': ['11:00', '14:00']}}, headers=admin)
    assert r.status_code == 200 and r.json['answers']['hours'] == ['14:00', '11:00']
    r = client.put(f'/api/admin/applications/{aid}', json={'answers': {'hours': ['10:00']}}, headers=admin)
    assert r.status_code == 400 and r.json['field'] == 'answers.hours'


def test_tyrant_edit_windows_troops_and_errors(client, admin):
    start_round(client, admin, 'FDT', event='tyrant')
    tyrant_signup(client, '9400', 'Tyra')
    aid = app_id(client, admin, 'tyrant', '9400')
    r = client.put(f'/api/admin/applications/{aid}', headers=admin, json={
        'profile': {'game_name': 'Tyra 2', 'discord_id': 'tyra#7', 'power': 512_000_000,
                    'troops': {'marksman': {'furnace_level': 'FC5', 'tier': 8}}},
        'answers': {'availability': ['w3', 'w2'], 'roles': ['rally_leader', 'joiner'], 'discord_vc': True,
                    'gem_spend': None}})
    assert r.status_code == 200, r.json
    b = r.json
    assert b['answers']['availability'] == ['w2', 'w3'] and b['answers']['roles'] == ['rally_leader', 'joiner']
    assert b['answers']['discord_vc'] is True and b['answers']['gem_spend'] is None
    assert b['profile']['discord_id'] == 'tyra#7' and b['profile']['power'] == 512_000_000
    assert b['profile']['troops']['marksman'] == {'furnace_level': 'FC5', 'tier': 8}
    assert b['profile']['troops']['infantry'] == {'furnace_level': 'FC8', 'tier': 10}
    assert b['joiner_strength'] is not None  # same as the list rows, so the UI can replace the row in place
    # errors name the field
    r = client.put(f'/api/admin/applications/{aid}', json={'answers': {'gem_spend': 10 ** 12}}, headers=admin)
    assert r.status_code == 400 and r.json['field'] == 'answers.gem_spend'
    r = client.put(f'/api/admin/applications/{aid}', json={'answers': {'availability': ['nope']}}, headers=admin)
    assert r.status_code == 400 and r.json['field'] == 'answers.availability'
    r = client.put(f'/api/admin/applications/{aid}', json={'profile': {'power': -5}}, headers=admin)
    assert r.status_code == 400 and r.json['field'] == 'profile.power'
    # the language the player used is kept by an admin edit (answers merge)
    assert client.get(f'/api/admin/applications/{aid}', headers=admin).json['answers']['language'] is None
