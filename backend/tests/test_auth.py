import time

import pytest
from itsdangerous import URLSafeTimedSerializer

from core.auth import TOKEN_SALT
from tests.conftest import ADMIN_PW, MINISTER_PW


def test_login_admin_and_minister(client):
    r = client.post('/api/admin/login', json={'password': ADMIN_PW})
    assert r.status_code == 200 and r.json['role'] == 'admin' and r.json['expires_in'] == 12 * 3600
    assert r.json['token'] not in ('admin-token', 'minister-token')
    r = client.post('/api/admin/login', json={'password': MINISTER_PW})
    assert r.status_code == 200 and r.json['role'] == 'minister'


def test_wrong_and_missing_password(client):
    r = client.post('/api/admin/login', json={'password': 'nope'})
    assert r.status_code == 401 and r.json['code'] == 'INVALID_PASSWORD'
    r = client.post('/api/admin/login', json={})
    assert r.status_code == 400 and r.json['code'] == 'VALIDATION_ERROR' and r.json['field'] == 'password'
    r = client.post('/api/admin/login', data='not json', content_type='application/json')
    assert r.status_code == 400 and r.json['code'] == 'INVALID_JSON'


def test_valid_token_accepted_bearer_and_bare(client, admin):
    assert client.get('/api/admin/me', headers=admin).json == {'role': 'admin'}
    bare = admin['Authorization'].split(' ', 1)[1]
    assert client.get('/api/admin/me', headers={'Authorization': bare}).status_code == 200


@pytest.mark.parametrize('token', ['admin-token', 'minister-token', 'Bearer admin-token', 'garbage', ''])
def test_literal_v14_tokens_rejected(client, token):
    r = client.get('/api/admin/me', headers={'Authorization': token})
    assert r.status_code == 401
    assert r.json['code'] in ('INVALID_TOKEN', 'UNAUTHORIZED')


def test_missing_header_rejected(client):
    r = client.get('/api/admin/profiles')
    assert r.status_code == 401 and r.json['code'] == 'UNAUTHORIZED'


def test_forged_token_with_other_key_rejected(client):
    forged = URLSafeTimedSerializer('some-other-key', salt=TOKEN_SALT).dumps({'role': 'admin'})
    r = client.get('/api/admin/me', headers={'Authorization': f'Bearer {forged}'})
    assert r.status_code == 401 and r.json['code'] == 'INVALID_TOKEN'


def test_tampered_token_rejected(client, admin):
    token = admin['Authorization'].split(' ', 1)[1]
    payload, rest = token.split('.', 1)
    tampered = ('A' if payload[0] != 'A' else 'B') + payload[1:] + '.' + rest
    r = client.get('/api/admin/me', headers={'Authorization': f'Bearer {tampered}'})
    assert r.status_code == 401


def test_unknown_role_rejected_even_if_signed(app, client):
    tok = URLSafeTimedSerializer(app.config['SECRET_KEY'], salt=TOKEN_SALT).dumps({'role': 'superuser'})
    r = client.get('/api/admin/me', headers={'Authorization': f'Bearer {tok}'})
    assert r.status_code == 401 and r.json['code'] == 'INVALID_TOKEN'


def test_expired_token_rejected(client, admin, monkeypatch):
    real = time.time
    monkeypatch.setattr(time, 'time', lambda: real() + 12 * 3600 + 5)
    r = client.get('/api/admin/me', headers=admin)
    assert r.status_code == 401 and r.json['code'] == 'TOKEN_EXPIRED'


def test_token_just_under_12h_still_valid(client, admin, monkeypatch):
    real = time.time
    monkeypatch.setattr(time, 'time', lambda: real() + 11 * 3600)
    assert client.get('/api/admin/me', headers=admin).status_code == 200


def test_every_admin_route_rejects_literal_token(app, client):
    """Walk the URL map: no admin endpoint may accept the old fixed token."""
    checked = 0
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith('/api/admin') or rule.rule == '/api/admin/login':
            continue
        url = rule.rule
        for arg in rule.arguments:
            url = url.replace(f'<int:{arg}>', '1').replace(f'<{arg}>', 'monday' if arg == 'day' else '1')
        for method in rule.methods - {'HEAD', 'OPTIONS'}:
            r = client.open(url, method=method, json={}, headers={'Authorization': 'Bearer admin-token'})
            assert r.status_code == 401, (method, url, r.status_code)
            checked += 1
    assert checked > 20


def test_role_disabled_when_password_unset(db_path):
    from app import create_app
    app = create_app({'DATABASE_PATH': db_path, 'SECRET_KEY': 'k' * 20, 'ADMIN_PASSWORD': 'x',
                      'MINISTER_PASSWORD': None})
    c = app.test_client()
    assert c.post('/api/admin/login', json={'password': 'minister123'}).status_code == 401


def test_placeholder_secret_key_replaced(db_path):
    from app import create_app
    app = create_app({'DATABASE_PATH': db_path, 'SECRET_KEY': 'dev-secret-key', 'DEV_MODE': False})
    assert app.config['SECRET_KEY'] != 'dev-secret-key'
