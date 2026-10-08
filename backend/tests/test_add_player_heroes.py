"""Admin "add player" (every event) and the hero library + state hero generation setting (v2.2.0)."""
import pytest

from tests.conftest import start_round

SVS_TROOPS = {k: {'furnace_level': 'FC10', 'tier': 11} for k in ('infantry', 'lancer', 'marksman')}


def add(client, admin, ref, body, event=None):
    q = f'?event={event}' if event else ''
    return client.post(f'/api/admin/rounds/{ref}/applications{q}', json=body, headers=admin)


@pytest.mark.parametrize('event', ['ministry', 'tyrant', 'svs'])
def test_add_player_minimal_and_conflict(client, admin, event):
    rnd = start_round(client, admin, 'R', event=event)
    r = add(client, admin, rnd['id'], {'fid': '9001', 'profile': {'game_name': 'Added'}})
    assert r.status_code == 201, r.json
    assert r.json['fid'] == '9001' and r.json['profile']['game_name'] == 'Added' and r.json['profile_created']
    assert r.json['event'] == event and 'id' in r.json
    # visible to the player too (their sign-up exists; they can edit it with their FID)
    assert client.get(f'/api/events/{event}/current/application/9001').status_code == 200
    r = add(client, admin, rnd['id'], {'fid': '9001', 'profile': {'game_name': 'Again'}})
    assert r.status_code == 409 and r.json['code'] == 'APPLICATION_EXISTS' and '9001' in r.json['error']
    # "current" + ?event= works too
    r = add(client, admin, 'current', {'fid': '9002', 'profile': {'game_name': 'Cur'}}, event=event)
    assert r.status_code == 201 and r.json['round_id'] == rnd['id']


@pytest.mark.parametrize('event', ['ministry', 'tyrant', 'svs'])
def test_add_player_validation(client, admin, event):
    rnd = start_round(client, admin, 'R', event=event)
    r = add(client, admin, rnd['id'], {'profile': {'game_name': 'NoFid'}})
    assert r.status_code == 400 and r.json['field'] == 'fid'
    r = add(client, admin, rnd['id'], {'fid': 'abc', 'profile': {'game_name': 'X'}})
    assert r.status_code == 400 and r.json['field'] == 'fid'
    r = add(client, admin, rnd['id'], {'fid': '9003'})  # new FID: name needed
    assert r.status_code == 400 and r.json['field'] == 'profile.game_name'
    r = add(client, admin, rnd['id'], {'fid': '9003', 'profile': {'game_name': 'X', 'alliance': 'TOOLONG'}})
    assert r.status_code == 400 and r.json['field'] == 'profile.alliance'
    # an existing profile needs nothing else
    client.put('/api/profile/9004', json={'game_name': 'Known', 'alliance': 'KKK'})
    r = add(client, admin, rnd['id'], {'fid': '9004'})
    assert r.status_code == 201 and r.json['profile']['alliance'] == 'KKK' and not r.json['profile_created']


def test_add_player_event_fields(client, admin):
    s = start_round(client, admin, 'S', event='svs')
    r = add(client, admin, s['id'], {'fid': '9101', 'profile': {'game_name': 'Svs', 'alliance': 'svs',
                                                               'troops': {'infantry': {'furnace_level': 'FC9'}}},
                                     'answers': {'hours': ['12:00'], 'role': 'call'}})
    assert r.status_code == 201, r.json
    assert r.json['answers'] == {'hours': ['12:00'], 'role': 'call', 'discord_vc': None, 'language': None}
    assert r.json['profile']['troops']['infantry'] == {'furnace_level': 'FC9', 'tier': None}
    # what IS sent is still validated with the event's rules
    for body, field in [({'answers': {'hours': ['09:00']}}, 'answers.hours'), ({'answers': {'role': 'x'}}, 'answers.role'),
                        ({'profile': {'game_name': 'A', 'troops': {'lancer': {'tier': 9}}}}, 'profile.troops.lancer.tier')]:
        body = {'fid': '9102', **body}
        body.setdefault('profile', {'game_name': 'A'})
        r = add(client, admin, s['id'], body)
        assert r.status_code == 400 and r.json['field'] == field, (body, r.json)
    t = start_round(client, admin, 'T', event='tyrant')
    r = add(client, admin, t['id'], {'fid': '9103', 'profile': {'game_name': 'Tyr', 'troops': {
        'lancer': {'furnace_level': 'FC7', 'tier': 9}}}, 'answers': {'availability': ['w2'], 'roles': ['joiner']}})
    assert r.status_code == 201 and r.json['answers']['availability'] == ['w2']
    r = add(client, admin, t['id'], {'fid': '9104', 'profile': {'game_name': 'Tyr'}, 'answers': {'availability': ['w9']}})
    assert r.status_code == 400 and r.json['field'] == 'answers.availability'
    m = start_round(client, admin, 'M')
    r = add(client, admin, m['id'], {'fid': '9105', 'profile': {'game_name': 'Min', 'furnace_level': 'FC5'},
                                     'answers': {'construction_speedups_days': 12}})
    assert r.status_code == 201 and r.json['monday_points'] == 12 * 1440
    assert r.json['answers']['research_speedups_days'] == 0


def test_add_player_keeps_richer_profile_troops(client, admin):
    """An admin adding a player to SVS with blank troops never wipes what Tyrant stored."""
    start_round(client, admin, 'T', event='tyrant')
    tyr = {'infantry': {'furnace_level': 'FC8', 'tier': 9}, 'lancer': {'furnace_level': 'FC9', 'tier': 11},
           'marksman': {'furnace_level': 'FC7', 'tier': 10}}
    client.put('/api/events/tyrant/current/application/9201', json={
        'profile': {'game_name': 'Ty', 'alliance': 'TTT', 'troops': tyr}, 'answers': {}})
    s = start_round(client, admin, 'S', event='svs')
    r = add(client, admin, s['id'], {'fid': '9201', 'profile': {'troops': {'marksman': {'tier': 11}}}})
    assert r.status_code == 201, r.json
    t = client.get('/api/profile/9201').json['troops']
    assert t['infantry'] == tyr['infantry'] and t['lancer'] == tyr['lancer']
    assert t['marksman'] == {'furnace_level': 'FC7', 'tier': 11}


def test_add_player_closed_round_and_after_closing_time(client, admin):
    r1 = start_round(client, admin, 'S1', event='svs', closing_time='2020-01-01T00:00:00Z')
    assert add(client, admin, r1['id'], {'fid': '9301', 'profile': {'game_name': 'Late'}}).status_code == 201
    start_round(client, admin, 'S2', event='svs')  # closes S1
    r = add(client, admin, r1['id'], {'fid': '9302', 'profile': {'game_name': 'Closed'}})
    assert r.status_code == 409 and r.json['code'] == 'ROUND_CLOSED'


def test_add_player_needs_admin(client, admin):
    rnd = start_round(client, admin, 'S', event='svs')
    r = client.post(f'/api/admin/rounds/{rnd["id"]}/applications', json={'fid': '1', 'profile': {'game_name': 'x'}})
    assert r.status_code == 401


# ------------------------------------------------------------------ heroes

def test_heroes_library_and_generation_setting(client, admin):
    r = client.get('/api/heroes')
    assert r.status_code == 200
    body = r.json
    assert body['state_generation'] == 17 and body['max_gen'] == 17 and body['total'] == 65
    assert 'Century Games' in body['attribution'] and body['version'] == 1
    h = {x['slug']: x for x in body['heroes']}
    assert h['jeronimo'] == {'slug': 'jeronimo', 'name': 'Jeronimo', 'troop': 'infantry', 'generation': 1,
                             'rarity': 'mythic', 'image': '/heroes/jeronimo.webp', 'has_generation': True}
    assert h['smith']['generation'] is None and h['smith']['has_generation'] is False
    assert h['lumak-bokan']['rarity'] == 'epic'
    # explicit max_gen: rare/epic (no generation) are always included
    r = client.get('/api/heroes?max_gen=2')
    gens = {x['generation'] for x in r.json['heroes']}
    assert gens == {None, 1, 2} and r.json['total'] == 13 + 7  # 13 rare/epic + gen 1 (4) + gen 2 (3)
    r = client.get('/api/heroes?max_gen=3&troop=marksman')
    assert {x['troop'] for x in r.json['heroes']} == {'marksman'} and len(r.json['heroes']) == 5 + 3
    for q, field in [('max_gen=0', 'max_gen'), ('max_gen=18', 'max_gen'), ('max_gen=x', 'max_gen'),
                     ('troop=dragon', 'troop')]:
        r = client.get(f'/api/heroes?{q}')
        assert r.status_code == 400 and r.json['field'] == field
    # the state generation setting is the default max_gen
    r = client.put('/api/admin/settings', json={'state_generation': 8}, headers=admin)
    assert r.status_code == 200 and r.json['state_generation'] == 8
    body = client.get('/api/heroes').json
    assert body['max_gen'] == 8 and max(x['generation'] or 0 for x in body['heroes']) == 8
    assert client.get('/api/settings/public').json['state_generation'] == 8
    assert client.get('/api/heroes?max_gen=17').json['total'] == 65  # an explicit max_gen still wins
    for bad in (0, 18, 'abc', True, None, 2.5):
        r = client.put('/api/admin/settings', json={'state_generation': bad}, headers=admin)
        assert r.status_code == 400 and r.json['field'] == 'state_generation', bad
    # a bad value next to a good one changes nothing
    r = client.put('/api/admin/settings', json={'state_number': '1234', 'state_generation': 99}, headers=admin)
    assert r.status_code == 400 and client.get('/api/settings/public').json['state_number'] is None
    assert client.put('/api/admin/settings', json={'state_generation': 17}).status_code == 401


def test_hero_images_exist():
    import json
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(here))
    doc = json.load(open(os.path.join(repo, 'backend', 'gamedata', 'heroes.json'), encoding='utf-8'))
    public = os.path.join(repo, 'frontend', 'public')
    if not os.path.isdir(public):  # backend-only checkout (e.g. the 3.11 container copies backend/ alone)
        pytest.skip('frontend/public not present')
    for h in doc['heroes']:
        assert os.path.isfile(os.path.join(public, h['image'].lstrip('/'))), h['slug']
