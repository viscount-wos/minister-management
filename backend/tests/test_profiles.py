from tests.conftest import apply, start_round


def test_profile_created_by_application_and_public_get(client, admin):
    start_round(client, admin, 'R1')
    apply(client, '1001', name='Alice', alliance='abc', expect=201, timezone='Europe/London',
          furnace_level=30, power=123456789, troops={'infantry': 5})
    r = client.get('/api/profile/1001')
    assert r.status_code == 200
    p = r.json
    assert p['game_name'] == 'Alice' and p['alliance'] == 'ABC' and p['timezone'] == 'Europe/London'
    assert p['furnace_level'] == '30' and p['power'] == 123456789 and p['troops'] == {'infantry': 5}


def test_profile_404(client):
    r = client.get('/api/profile/999')
    assert r.status_code == 404 and r.json['code'] == 'NOT_FOUND'


def test_admin_profile_crud(client, admin):
    r = client.put('/api/admin/profiles/2002', json={'game_name': 'Bob', 'alliance': 'xy'}, headers=admin)
    assert r.status_code == 201 and r.json['created'] and r.json['profile']['alliance'] == 'XY'
    r = client.put('/api/admin/profiles/2002', json={'alliance': 'zzz'}, headers=admin)
    assert r.status_code == 200 and not r.json['created']
    assert r.json['profile']['game_name'] == 'Bob' and r.json['profile']['alliance'] == 'ZZZ'
    client.put('/api/admin/profiles/2003', json={'game_name': 'Carl', 'alliance': 'QQ'}, headers=admin)
    r = client.get('/api/admin/profiles?alliance=zzz', headers=admin)
    assert [p['fid'] for p in r.json['profiles']] == ['2002']
    r = client.get('/api/admin/profiles?q=car', headers=admin)
    assert [p['fid'] for p in r.json['profiles']] == ['2003']
    assert client.delete('/api/admin/profiles/2002', headers=admin).json['deleted'] is True
    assert client.get('/api/profile/2002').status_code == 404
    assert client.delete('/api/admin/profiles/2002', headers=admin).status_code == 404


def test_profile_validation(client, admin):
    r = client.put('/api/admin/profiles/12ab', json={'game_name': 'X'}, headers=admin)
    assert r.status_code == 400 and r.json['code'] == 'VALIDATION_ERROR' and r.json['field'] == 'fid'
    r = client.put('/api/admin/profiles/1', json={'game_name': 'X', 'alliance': 'ABCD'}, headers=admin)
    assert r.status_code == 400 and r.json['field'] == 'alliance'
    r = client.put('/api/admin/profiles/1', json={'alliance': 'AB'}, headers=admin)
    assert r.status_code == 400 and r.json['field'] == 'game_name'
    r = client.put('/api/admin/profiles/1', json={'game_name': 'X', 'furnace_level': 'high'}, headers=admin)
    assert r.status_code == 400 and r.json['field'] == 'furnace_level'
    r = client.put('/api/admin/profiles/1', json={'game_name': 'X', 'troops': 'lots'}, headers=admin)
    assert r.status_code == 400 and r.json['field'] == 'troops'


def test_delete_profile_cascades_applications_and_assignments(client, admin):
    rnd = start_round(client, admin, 'R1')
    apply(client, '5', answers={'construction_speedups_days': 1,
                                'time_slots_by_day': {'construction': ['10:00']}}, expect=201)
    client.post('/api/admin/ministry/rounds/current/auto-assign', json={'day': 'monday'}, headers=admin)
    r = client.delete('/api/admin/profiles/5', headers=admin)
    assert r.json['applications_deleted'] == 1
    r = client.get(f'/api/admin/ministry/rounds/{rnd["id"]}/assignments/monday', headers=admin)
    assert r.json['assignments'] == {} and r.json['unassigned'] == []


def test_global_settings(client, admin):
    assert client.get('/api/settings/public').json == {'state_number': None}  # unset until an admin sets it
    r = client.put('/api/admin/settings', json={'state_number': '2807'}, headers=admin)
    assert r.json == {'state_number': '2807'}
    assert client.get('/api/settings/public').json == {'state_number': '2807'}
    r = client.put('/api/admin/settings', json={'state_number': ''}, headers=admin)
    assert r.status_code == 400 and r.json['field'] == 'state_number'


def test_public_profile_put(client):
    r = client.put('/api/profile/3003', json={'game_name': 'Dee', 'alliance': 'dd', 'power': 5})
    assert r.status_code == 201 and r.json['created'] and r.json['profile']['alliance'] == 'DD'
    r = client.put('/api/profile/3003', json={'timezone': 'UTC'})
    assert r.status_code == 200 and r.json['profile']['game_name'] == 'Dee' and r.json['profile']['power'] == 5
    r = client.put('/api/profile/3004', json={'alliance': 'X'})
    assert r.status_code == 400 and r.json['field'] == 'game_name'
    r = client.put('/api/profile/3003', json={'fid': '1', 'game_name': 'X'})
    assert r.status_code == 400 and r.json['field'] == 'fid'
    r = client.put('/api/profile/abc', json={'game_name': 'X'})
    assert r.status_code == 400 and r.json['field'] == 'fid'
