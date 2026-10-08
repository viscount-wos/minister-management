from tests.conftest import application_id, apply, prefs, start_round

PAST = '2020-01-01T00:00:00Z'
FUTURE = '2099-01-01T00:00:00Z'


def test_new_vs_edit(client, admin):
    start_round(client, admin, 'R1')
    r = client.get('/api/events/ministry/current/application/42')
    assert r.status_code == 404 and r.json['code'] == 'NOT_FOUND'  # -> "New application"
    r = apply(client, '42', answers={'research_speedups_days': 3}, expect=201)
    assert r.json['created'] is True and r.json['profile_created'] is True
    app_id = application_id(client, admin, '42')
    assert 'id' not in r.json['application'] and 'player_id' not in r.json['application']  # M6
    r = client.get('/api/events/ministry/current/application/42')
    assert r.status_code == 200 and r.json['answers']['research_speedups_days'] == 3  # -> "Edit"
    r = apply(client, '42', answers={'research_speedups_days': 4}, expect=200)
    assert r.json['created'] is False and application_id(client, admin, '42') == app_id
    assert client.get('/api/events/ministry/current/application/42').json['answers']['research_speedups_days'] == 4


def test_upsert_is_one_application_per_round_and_player(client, admin):
    rnd = start_round(client, admin, 'R1')
    for i in range(3):
        apply(client, '7', answers={'troop_training_speedups_days': i})
    apps = client.get(f'/api/admin/rounds/{rnd["id"]}/applications', headers=admin).json['applications']
    assert len(apps) == 1 and apps[0]['answers']['troop_training_speedups_days'] == 2


def test_new_round_means_new_application_and_previous_lookup(client, admin):
    start_round(client, admin, 'R1')
    apply(client, '42', answers={'construction_speedups_days': 1}, expect=201)
    start_round(client, admin, 'R2')
    # profile still pre-fills, but no application in the new round
    assert client.get('/api/profile/42').status_code == 200
    assert client.get('/api/events/ministry/current/application/42').status_code == 404
    r = client.get('/api/events/ministry/previous-application/42')
    assert r.status_code == 200 and r.json['round_name'] == 'R1'
    assert r.json['answers']['construction_speedups_days'] == 1
    apply(client, '42', answers={'construction_speedups_days': 2}, expect=201)
    # previous is still R1 (current round is excluded)
    r = client.get('/api/events/ministry/previous-application/42')
    assert r.json['round_name'] == 'R1'
    start_round(client, admin, 'R3')
    r = client.get('/api/events/ministry/previous-application/42')
    assert r.json['round_name'] == 'R2' and r.json['answers']['construction_speedups_days'] == 2


def test_previous_ignores_later_rounds_and_other_events(client, admin):
    r1 = start_round(client, admin, 'R1')
    apply(client, '9', expect=201)
    r2 = start_round(client, admin, 'R2')
    apply(client, '9', answers={'fire_crystals': 5}, expect=201)
    # reopen R1 as current: R2 is LATER, so it must not be returned
    client.put(f'/api/admin/rounds/{r2["id"]}', json={'status': 'closed'}, headers=admin)
    client.put(f'/api/admin/rounds/{r1["id"]}', json={'status': 'open'}, headers=admin)
    assert client.get('/api/events/ministry/previous-application/9').status_code == 404
    # other events don't leak in
    start_round(client, admin, 'T1', event='tyrant')
    apply(client, '9', event='tyrant', answers={'x': 1}, expect=201)
    assert client.get('/api/events/tyrant/previous-application/9').status_code == 404


def test_previous_unknown_player(client, admin):
    start_round(client, admin, 'R1')
    assert client.get('/api/events/ministry/previous-application/123').status_code == 404


def test_closing_time_blocks_new_allows_edit(client, admin):
    rnd = start_round(client, admin, 'R1')
    apply(client, '1', expect=201)
    client.put(f'/api/admin/rounds/{rnd["id"]}', json={'closing_time': PAST}, headers=admin)
    assert client.get('/api/events/ministry/current').json['is_closed_for_new'] is True
    r = apply(client, '2')
    assert r.status_code == 403 and r.json['code'] == 'APPLICATIONS_CLOSED'
    assert client.get('/api/profile/2').status_code == 404  # nothing written
    r = apply(client, '1', answers={'fire_crystals': 3})
    assert r.status_code == 200 and r.json['created'] is False
    # a profile that exists from an earlier round still counts as NEW in this round
    client.put('/api/admin/profiles/3', json={'game_name': 'Old'}, headers=admin)
    assert apply(client, '3').status_code == 403


def test_future_closing_time_allows_new(client, admin):
    start_round(client, admin, 'R1', closing_time=FUTURE)
    assert apply(client, '1').status_code == 201


def test_closed_round_blocks_edits(client, admin):
    rnd = start_round(client, admin, 'R1')
    apply(client, '1', expect=201)
    client.put(f'/api/admin/rounds/{rnd["id"]}', json={'status': 'closed'}, headers=admin)
    r = apply(client, '1')
    assert r.status_code == 404 and r.json['code'] == 'NO_CURRENT_ROUND'


def test_application_validation(client, admin):
    start_round(client, admin, 'R1')
    cases = [
        ('12a', {}, {}, 'fid'),
        ('1', {'alliance': 'ABCD'}, {}, 'profile.alliance'),
        ('1', {'alliance': ''}, {}, 'profile.alliance'),       # ministry requires alliance (as v1.4)
        ('1', {'game_name': ''}, {}, 'profile.game_name'),
        ('1', {}, {'construction_speedups_days': -1}, 'answers.construction_speedups_days'),
        ('1', {}, {'fire_crystals': 100000}, 'answers.fire_crystals'),
        ('1', {}, {'fire_crystals': 1.5}, 'answers.fire_crystals'),
        ('1', {}, {'general_speedups_days': 'lots'}, 'answers.general_speedups_days'),
        ('1', {}, {'time_slots_by_day': {'construction': ['25:00']}}, 'answers.time_slots_by_day.construction'),
        ('1', {}, {'time_slots_by_day': {'weekend': []}}, 'answers.time_slots_by_day'),
    ]
    for fid, prof, answers, field in cases:
        body_prof = {'game_name': 'P', 'alliance': 'AB'}
        body_prof.update(prof)
        r = client.put(f'/api/events/ministry/current/application/{fid}',
                       json={'profile': body_prof, 'answers': answers})
        assert r.status_code == 400, (fid, prof, answers, r.json)
        assert r.json['code'] == 'VALIDATION_ERROR' and r.json['field'] == field, r.json
    r = client.put('/api/events/ministry/current/application/1',
                   json={'profile': {'fid': '2', 'game_name': 'P', 'alliance': 'AB'}, 'answers': {}})
    assert r.status_code == 400 and r.json['field'] == 'profile.fid'


def test_answers_normalised(client, admin):
    start_round(client, admin, 'R1')
    r = apply(client, '1', answers={'construction_speedups_days': '2.5', 'fire_crystals': '10',
                                    'time_slots': ['10:00', '10:00', '11:00']}, expect=201)
    a = r.json['application']['answers']
    assert a['construction_speedups_days'] == 2.5 and a['fire_crystals'] == 10 and a['research_speedups_days'] == 0
    assert a['time_slots_by_day'] == prefs(['10:00', '11:00'], ['10:00', '11:00'], ['10:00', '11:00'])


def test_partial_profile_update_keeps_fields(client, admin):
    start_round(client, admin, 'R1')
    apply(client, '1', name='Alice', alliance='AAA', timezone='UTC', expect=201)
    r = client.put('/api/events/ministry/current/application/1', json={'profile': {}, 'answers': {}})
    assert r.status_code == 200 and r.json['profile']['game_name'] == 'Alice' and r.json['profile']['timezone'] == 'UTC'


def test_profile_snapshot_frozen_per_application(client, admin):
    rnd1 = start_round(client, admin, 'R1')
    apply(client, '1', name='OldName', expect=201)
    start_round(client, admin, 'R2')
    apply(client, '1', name='NewName', expect=201)
    apps = client.get(f'/api/admin/rounds/{rnd1["id"]}/applications', headers=admin).json['applications']
    assert apps[0]['profile_snapshot']['game_name'] == 'OldName'
    assert apps[0]['profile']['game_name'] == 'NewName'


def test_admin_list_edit_delete_application(client, admin):
    rnd = start_round(client, admin, 'R1')
    apply(client, '1', alliance='AAA', answers={'construction_speedups_days': 1, 'refined_fire_crystals': 1,
                                                'time_slots_by_day': {'construction': ['10:00']}}, expect=201)
    apply(client, '2', alliance='BBB', expect=201)
    r = client.get(f'/api/admin/rounds/{rnd["id"]}/applications?alliance=aaa', headers=admin)
    apps = r.json['applications']
    assert len(apps) == 1 and apps[0]['fid'] == '1'
    assert apps[0]['monday_points'] == 1440 + 30000 and apps[0]['research_day'] == 'tuesday'
    app_id = apps[0]['id']
    r = client.put(f'/api/admin/applications/{app_id}', json={'answers': {'fire_crystals': 2},
                                                             'profile': {'alliance': 'CCC'}}, headers=admin)
    assert r.status_code == 200
    assert r.json['answers']['fire_crystals'] == 2 and r.json['answers']['construction_speedups_days'] == 1
    assert r.json['profile']['alliance'] == 'CCC'
    r = client.put(f'/api/admin/applications/{app_id}', json={'answers': {'fire_crystals': -2}}, headers=admin)
    assert r.status_code == 400 and r.json['field'] == 'answers.fire_crystals'
    client.post('/api/admin/ministry/rounds/current/auto-assign', json={'day': 'monday'}, headers=admin)
    assert client.delete(f'/api/admin/applications/{app_id}', headers=admin).json['deleted'] is True
    a = client.get('/api/admin/ministry/rounds/current/assignments/monday', headers=admin).json
    assert a['assignments'] == {} and [u['fid'] for u in a['unassigned']] == ['2']
    assert client.get('/api/profile/1').status_code == 200  # profile survives
    assert client.delete(f'/api/admin/applications/{app_id}', headers=admin).status_code == 404


def test_admin_edit_allowed_after_closing(client, admin):
    rnd = start_round(client, admin, 'R1')
    apply(client, '1', expect=201)
    app_id = application_id(client, admin, '1')
    client.put(f'/api/admin/rounds/{rnd["id"]}', json={'closing_time': PAST}, headers=admin)
    r = client.put(f'/api/admin/applications/{app_id}', json={'answers': {'fire_crystals': 9}}, headers=admin)
    assert r.status_code == 200
