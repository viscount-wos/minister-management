import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402

ADMIN_PW = 'test-admin-pw'
MINISTER_PW = 'test-minister-pw'


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / 'data' / 'test.db')


@pytest.fixture
def app(db_path):
    return create_app({
        'TESTING': True,
        'DATABASE_PATH': db_path,
        'SECRET_KEY': 'test-secret-key-not-a-placeholder',
        'ADMIN_PASSWORD': ADMIN_PW,
        'MINISTER_PASSWORD': MINISTER_PW,
        'STATIC_DIR': '/nonexistent',
    })


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin(client):
    r = client.post('/api/admin/login', json={'password': ADMIN_PW})
    assert r.status_code == 200, r.json
    return {'Authorization': f'Bearer {r.json["token"]}'}


def start_round(client, admin, name='Round', event='ministry', settings=None, closing_time=None):
    body = {'name': name}
    if settings is not None:
        body['settings'] = settings
    if closing_time is not None:
        body['closing_time'] = closing_time
    r = client.post(f'/api/admin/events/{event}/start-new-round', json=body, headers=admin)
    assert r.status_code == 201, r.json
    return r.json['round']


def apply(client, fid, name=None, alliance='ABC', answers=None, event='ministry', expect=None, **profile):
    prof = {'game_name': name or f'Player{fid}', 'alliance': alliance}
    prof.update(profile)
    r = client.put(f'/api/events/{event}/current/application/{fid}', json={'profile': prof, 'answers': answers or {}})
    if expect is not None:
        assert r.status_code == expect, r.json
    return r


def prefs(construction=(), research=(), troop=()):
    return {'construction': list(construction), 'research': list(research), 'troop': list(troop)}


def profile_id(client, admin, fid):
    """Internal profile id (= player_id) via the admin API; public responses no longer carry it."""
    r = client.get(f'/api/admin/profiles/{fid}', headers=admin)
    assert r.status_code == 200, r.json
    return r.json['id']


def application_id(client, admin, fid, round_id=None):
    if round_id is None:
        round_id = client.get('/api/events/ministry/current').json['id']
    apps = client.get(f'/api/admin/rounds/{round_id}/applications', headers=admin).json['applications']
    return next(a['id'] for a in apps if a['fid'] == fid)
