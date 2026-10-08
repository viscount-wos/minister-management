from tests.conftest import apply, start_round


def test_no_current_round(client):
    r = client.get('/api/events/ministry/current')
    assert r.status_code == 404 and r.json['code'] == 'NO_CURRENT_ROUND'
    r = apply(client, '1')
    assert r.status_code == 404 and r.json['code'] == 'NO_CURRENT_ROUND'


def test_unknown_event_and_tal(client, admin):
    r = client.get('/api/events/foo/current')
    assert r.status_code == 404 and r.json['code'] == 'UNKNOWN_EVENT'
    r = client.post('/api/admin/events/tal/rounds', json={'name': 'x'}, headers=admin)
    assert r.status_code == 400 and r.json['code'] == 'EVENT_HAS_NO_ROUNDS'
    events = {e['key']: e for e in client.get('/api/events').json['events']}
    assert set(events) == {'ministry', 'tyrant', 'svs', 'tal'}
    assert events['tal']['has_rounds'] is False


def test_only_one_open_round_per_event(client, admin):
    r = client.post('/api/admin/events/ministry/rounds', json={'name': 'A', 'status': 'open'}, headers=admin)
    assert r.status_code == 201
    r = client.post('/api/admin/events/ministry/rounds', json={'name': 'B', 'status': 'open'}, headers=admin)
    assert r.status_code == 409 and r.json['code'] == 'ROUND_ALREADY_OPEN'
    r = client.post('/api/admin/events/ministry/rounds', json={'name': 'B'}, headers=admin)
    assert r.status_code == 201 and r.json['status'] == 'draft'
    draft_id = r.json['id']
    r = client.put(f'/api/admin/rounds/{draft_id}', json={'status': 'open'}, headers=admin)
    assert r.status_code == 409 and r.json['code'] == 'ROUND_ALREADY_OPEN'
    # another event may have its own open round
    r = client.post('/api/admin/events/tyrant/rounds', json={'name': 'T', 'status': 'open'}, headers=admin)
    assert r.status_code == 201


def test_start_new_round_closes_old_and_keeps_data(client, admin):
    r1 = start_round(client, admin, 'Week 1', settings={'research_day': 'friday', 'time_slot_scheme': 'max_slots'})
    apply(client, '1', expect=201)
    client.post('/api/admin/ministry/rounds/current/publish', json={'day': 'monday'}, headers=admin)
    r = client.post('/api/admin/events/ministry/start-new-round', json={'name': 'Week 2'}, headers=admin)
    assert r.status_code == 201
    assert r.json['closed_round']['id'] == r1['id'] and r.json['closed_round']['status'] == 'closed'
    r2 = r.json['round']
    assert r2['status'] == 'open' and r2['name'] == 'Week 2'
    # settings carried over, published days reset
    assert r2['settings']['research_day'] == 'friday' and r2['settings']['time_slot_scheme'] == 'max_slots'
    assert r2['settings']['published_days'] == []
    assert client.get('/api/events/ministry/current').json['id'] == r2['id']
    rounds = client.get('/api/admin/events/ministry/rounds', headers=admin).json['rounds']
    assert [(x['name'], x['status'], x['application_count']) for x in rounds] == \
        [('Week 2', 'open', 0), ('Week 1', 'closed', 1)]
    # nothing deleted
    apps = client.get(f'/api/admin/rounds/{r1["id"]}/applications', headers=admin).json['applications']
    assert len(apps) == 1


def test_update_round_fields_and_validation(client, admin):
    rnd = start_round(client, admin, 'R')
    r = client.put(f'/api/admin/rounds/{rnd["id"]}', json={'name': 'Renamed', 'closing_time': '2030-01-01T10:00:00Z',
                                                          'settings': {'show_fire_crystals': True}}, headers=admin)
    assert r.status_code == 200
    assert r.json['name'] == 'Renamed' and r.json['closing_time'] == '2030-01-01T10:00:00Z'
    assert r.json['settings']['show_fire_crystals'] is True
    assert r.json['settings']['research_day'] == 'tuesday'
    for body, field in [({'status': 'paused'}, 'status'), ({'closing_time': 'tomorrow'}, 'closing_time'),
                        ({'settings': {'research_day': 'monday'}}, 'settings.research_day'),
                        ({'settings': {'time_slot_scheme': 'x'}}, 'settings.time_slot_scheme'),
                        ({'settings': {'bogus': 1}}, 'settings'), ({'name': ''}, 'name')]:
        r = client.put(f'/api/admin/rounds/{rnd["id"]}', json=body, headers=admin)
        assert r.status_code == 400 and r.json['code'] == 'VALIDATION_ERROR' and r.json['field'] == field, body
    r = client.put('/api/admin/rounds/999', json={'name': 'x'}, headers=admin)
    assert r.status_code == 404
    # closing the round removes the current round
    client.put(f'/api/admin/rounds/{rnd["id"]}', json={'status': 'closed'}, headers=admin)
    assert client.get('/api/events/ministry/current').status_code == 404


def test_closing_time_cleared_with_null(client, admin):
    rnd = start_round(client, admin, 'R', closing_time='2030-01-01T10:00:00+02:00')
    assert rnd['closing_time'] == '2030-01-01T08:00:00Z'
    r = client.put(f'/api/admin/rounds/{rnd["id"]}', json={'closing_time': None}, headers=admin)
    assert r.json['closing_time'] is None
