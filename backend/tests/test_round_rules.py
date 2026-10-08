"""Backend issues logged by the frontend-wiring and MCP workers (milestone 1c): closed rounds are
read-only, research-day switch prunes published days, `current` on generic admin round routes,
paging on admin lists, unknown public schedule day -> 400, own assignments = published days only."""
import pytest

from tests.conftest import apply, prefs, profile_id, start_round


def _closed_round(client, admin):
    r1 = start_round(client, admin, 'Old')
    apply(client, '1', answers={'construction_speedups_days': 2, 'time_slots_by_day': prefs(['10:00'])})
    start_round(client, admin, 'New')  # closes Old
    assert client.get(f'/api/admin/rounds/{r1["id"]}', headers=admin).json['status'] == 'closed'
    return r1


def test_closed_round_is_read_only(client, admin):
    r1 = _closed_round(client, admin)
    rid = r1['id']
    app_id = client.get(f'/api/admin/rounds/{rid}/applications', headers=admin).json['applications'][0]['id']
    pid = profile_id(client, admin, '1')
    writes = [
        ('put', f'/api/admin/rounds/{rid}', {'settings': {'show_fire_crystals': True}}),
        ('put', f'/api/admin/rounds/{rid}', {'closing_time': '2030-01-01T00:00:00Z'}),
        ('put', f'/api/admin/rounds/{rid}', {'name': 'renamed'}),
        ('put', f'/api/admin/applications/{app_id}', {'answers': {'fire_crystals': 3}}),
        ('delete', f'/api/admin/applications/{app_id}', None),
        ('post', f'/api/admin/ministry/rounds/{rid}/auto-assign', {'day': 'monday'}),
        ('put', f'/api/admin/ministry/rounds/{rid}/assignments/monday',
         {'assignments': {'10:00': [{'player_id': pid}]}}),
        ('post', f'/api/admin/ministry/rounds/{rid}/publish', {'day': 'monday'}),
        ('post', f'/api/admin/ministry/rounds/{rid}/unpublish', {'day': 'monday'}),
        ('post', f'/api/admin/ministry/rounds/{rid}/import', {'players': []}),
    ]
    for method, url, body in writes:
        kw = {'headers': admin}
        if body is not None:
            kw['json'] = body
        r = getattr(client, method)(url, **kw)
        assert r.status_code == 409 and r.json['code'] == 'ROUND_CLOSED', (method, url, r.status_code, r.json)
    # reads and exports still work
    for url in (f'/api/admin/rounds/{rid}', f'/api/admin/rounds/{rid}/applications',
                f'/api/admin/ministry/rounds/{rid}/assignments/monday', f'/api/admin/rounds/{rid}/export',
                f'/api/admin/ministry/rounds/{rid}/export-json'):
        assert client.get(url, headers=admin).status_code == 200, url


def test_closed_round_can_be_reopened(client, admin):
    r1 = _closed_round(client, admin)
    # the new round is open: reopening Old collides with the one-open-round rule
    r = client.put(f'/api/admin/rounds/{r1["id"]}', json={'status': 'open'}, headers=admin)
    assert r.status_code == 409 and r.json['code'] == 'ROUND_ALREADY_OPEN'
    # to draft works (and may change other fields in the same request), then it is writable again
    r = client.put(f'/api/admin/rounds/{r1["id"]}', json={'status': 'draft', 'name': 'Old (fixing)'}, headers=admin)
    assert r.status_code == 200 and r.json['status'] == 'draft' and r.json['name'] == 'Old (fixing)'
    r = client.post(f'/api/admin/ministry/rounds/{r1["id"]}/auto-assign', json={'day': 'monday'}, headers=admin)
    assert r.status_code == 200


def test_research_day_switch_prunes_published_days(client, admin):
    rnd = start_round(client, admin, settings={'research_day': 'tuesday'})
    for d in ('tuesday', 'monday'):
        client.post('/api/admin/ministry/rounds/current/publish', json={'day': d}, headers=admin)
    r = client.put(f'/api/admin/rounds/{rnd["id"]}', json={'settings': {'research_day': 'friday'}}, headers=admin)
    assert r.json['settings']['published_days'] == ['monday']
    assert client.get('/api/events/ministry/current/schedule').json['published_days'] == ['monday']
    assert client.get('/api/events/ministry/current/schedule/tuesday').json['published'] is False
    assert client.get('/api/events/ministry/current').json['settings']['published_days'] == ['monday']


def test_public_endpoints_ignore_stale_published_days(client, admin, app):
    """Rows stored before the prune (or by hand) never leak an inactive day."""
    rnd = start_round(client, admin, settings={'research_day': 'friday'})
    from core.db import connect
    import json
    con = connect(app.config['DATABASE_PATH'])
    s = json.loads(con.execute('SELECT settings FROM rounds WHERE id = ?', (rnd['id'],)).fetchone()[0])
    s['published_days'] = ['tuesday', 'thursday']
    con.execute('UPDATE rounds SET settings = ? WHERE id = ?', (json.dumps(s), rnd['id']))
    con.commit()
    con.close()
    assert client.get('/api/events/ministry/current/schedule').json['published_days'] == ['thursday']
    assert client.get('/api/events/ministry/current/schedule/tuesday').json['published'] is False
    assert client.get('/api/events/ministry/current').json['settings']['published_days'] == ['thursday']


def test_current_accepted_on_generic_admin_round_routes(client, admin):
    rnd = start_round(client, admin)
    apply(client, '1')
    assert client.get('/api/admin/rounds/current', headers=admin).json['id'] == rnd['id']
    assert client.get('/api/admin/rounds/current?event=ministry', headers=admin).json['id'] == rnd['id']
    r = client.get('/api/admin/rounds/current/applications', headers=admin)
    assert r.status_code == 200 and r.json['round_id'] == rnd['id'] and r.json['total'] == 1
    assert client.get('/api/admin/rounds/current/export', headers=admin).status_code == 200
    r = client.put('/api/admin/rounds/current', json={'name': 'Renamed'}, headers=admin)
    assert r.status_code == 200 and r.json['name'] == 'Renamed'
    r = client.get('/api/admin/rounds/current?event=tyrant', headers=admin)
    assert r.status_code == 404 and r.json['code'] == 'NO_CURRENT_ROUND'
    assert client.get('/api/admin/rounds/nope', headers=admin).status_code == 404


def test_admin_list_paging(client, admin):
    rnd = start_round(client, admin)
    for i in range(1, 8):
        apply(client, str(i))
    full = client.get(f'/api/admin/rounds/{rnd["id"]}/applications', headers=admin).json
    assert full['total'] == 7 and len(full['applications']) == 7 and 'limit' not in full
    page = client.get(f'/api/admin/rounds/{rnd["id"]}/applications?limit=3&offset=2', headers=admin).json
    assert page['total'] == 7 and page['limit'] == 3 and page['offset'] == 2
    assert [a['id'] for a in page['applications']] == [a['id'] for a in full['applications'][2:5]]
    p = client.get('/api/admin/profiles?limit=2', headers=admin).json
    assert p['total'] == 7 and len(p['profiles']) == 2
    r = client.get('/api/admin/events/ministry/rounds?limit=1', headers=admin).json
    assert r['total'] == 1 and len(r['rounds']) == 1
    for bad in ('limit=0', 'limit=1001', 'offset=-1', 'limit=x'):
        r = client.get(f'/api/admin/profiles?{bad}', headers=admin)
        assert r.status_code == 400 and r.json['code'] == 'VALIDATION_ERROR', bad


@pytest.mark.parametrize('day,status', [('funday', 400), ('wednesday', 400), ('MONDAY', 200), ('friday', 200)])
def test_public_schedule_day_validation(client, admin, day, status):
    start_round(client, admin, settings={'research_day': 'tuesday'})
    r = client.get(f'/api/events/ministry/current/schedule/{day}')
    assert r.status_code == status
    if status == 400:
        assert r.json['code'] == 'VALIDATION_ERROR' and r.json['field'] == 'day'
    else:
        assert r.json['published'] is False  # friday: a possible ministry day, just not active this round


def test_own_assignments_only_published_days(client, admin):
    start_round(client, admin)
    apply(client, '1', answers={'construction_speedups_days': 1, 'troop_training_speedups_days': 1,
                                'time_slots_by_day': prefs(['10:00'], troop=['11:00'])})
    for d in ('monday', 'thursday'):
        client.post('/api/admin/ministry/rounds/current/auto-assign', json={'day': d}, headers=admin)
    r = client.get('/api/events/ministry/current/assignments/1').json
    assert r['published_days'] == [] and r['assignments'] == {}
    client.post('/api/admin/ministry/rounds/current/publish', json={'day': 'thursday'}, headers=admin)
    r = client.get('/api/events/ministry/current/assignments/1').json
    assert r['published_days'] == ['thursday'] and r['assignments'] == {'thursday': [{'time_slot': '11:00'}]}
