"""Security headers, CSP, compression, caching, rate limits and round renaming (v2.1.0 polish)."""
import gzip
import re

import brotli
import pytest

from app import create_app
from core.ratelimit import SlidingWindowLimiter
from core.security import build_csp, inline_script_hashes
from tests.conftest import ADMIN_PW, apply, start_round

INDEX_HTML = """<!doctype html><html><head><script>
  (function () { document.documentElement.lang = 'en'; })();
</script><script type="module" crossorigin src="/assets/index-abc.js"></script>
<link rel="stylesheet" href="/assets/index-abc.css"></head><body><div id="root"></div></body></html>"""
BIG_JS = 'console.log("hello world");\n' * 2000


@pytest.fixture
def static_dir(tmp_path):
    d = tmp_path / 'static'
    (d / 'assets').mkdir(parents=True)
    (d / 'index.html').write_text(INDEX_HTML)
    (d / 'assets' / 'index-abc.js').write_text(BIG_JS)
    (d / 'assets' / 'index-abc.css').write_text('body{color:red}\n' * 200)
    return d


def make_app(db_path, static_dir='/nonexistent', **cfg):
    base = {'TESTING': True, 'DATABASE_PATH': db_path, 'SECRET_KEY': 'test-secret-key-not-a-placeholder',
            'ADMIN_PASSWORD': ADMIN_PW, 'MINISTER_PASSWORD': 'test-minister-pw', 'STATIC_DIR': str(static_dir),
            'RATE_LIMIT_LOOKUPS_PER_MIN': 0, 'RATE_LIMIT_SUBMITS_PER_MIN': 0}
    base.update(cfg)
    return create_app(base)


# ------------------------------------------------------------------ headers

COMMON = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
}


@pytest.mark.parametrize('path', ['/', '/tyrant', '/assets/index-abc.js', '/assets/index-abc.css', '/health',
                                  '/api/events', '/api/profile/123', '/api/nope'])
def test_security_headers_on_every_response(db_path, static_dir, path):
    client = make_app(db_path, static_dir).test_client()
    r = client.get(path)
    for k, v in COMMON.items():
        assert r.headers.get(k) == v, (path, k, r.headers.get(k))
    pp = r.headers['Permissions-Policy']
    for feature in ('camera=()', 'microphone=()', 'geolocation=()'):
        assert feature in pp
    csp = r.headers['Content-Security-Policy']
    for directive in ("default-src 'self'", "img-src 'self' data:", "connect-src 'self'", "object-src 'none'",
                      "base-uri 'self'", "frame-ancestors 'none'"):
        assert directive in csp, (path, directive)
    assert 'unsafe-eval' not in csp
    script_src = re.search(r'script-src ([^;]+)', csp).group(1)
    assert "'unsafe-inline'" not in script_src


def test_csp_hashes_the_inline_prepaint_script(db_path, static_dir):
    hashes = inline_script_hashes(str(static_dir / 'index.html'))
    assert len(hashes) == 1 and hashes[0].startswith("'sha256-")   # the module <script src> is not hashed
    client = make_app(db_path, static_dir).test_client()
    assert hashes[0] in client.get('/').headers['Content-Security-Policy']
    assert build_csp([]).count('sha256') == 0


def test_hsts_only_in_production_or_https(db_path, static_dir):
    dev = make_app(db_path, static_dir, DEV_MODE=True).test_client()
    assert 'Strict-Transport-Security' not in dev.get('/').headers
    r = dev.get('/', headers={'X-Forwarded-Proto': 'https'})
    assert r.headers['Strict-Transport-Security'] == 'max-age=31536000; includeSubDomains'
    assert dev.get('/', base_url='https://localhost').headers.get('Strict-Transport-Security')
    prod = make_app(db_path, static_dir, DEV_MODE=False).test_client()
    assert prod.get('/health').headers['Strict-Transport-Security'] == 'max-age=31536000; includeSubDomains'


# ------------------------------------------------------------------ caching + compression

def test_assets_are_immutable_and_html_api_are_not_cached(db_path, static_dir):
    client = make_app(db_path, static_dir).test_client()
    for p in ('/assets/index-abc.js', '/assets/index-abc.css'):
        assert client.get(p).headers['Cache-Control'] == 'public, max-age=31536000, immutable'
    for p in ('/', '/minister', '/index.html'):
        assert client.get(p).headers['Cache-Control'] == 'no-cache', p
    assert client.get('/api/events').headers['Cache-Control'] == 'no-cache'
    assert client.get('/api/admin/me').headers['Cache-Control'] == 'no-store'


def test_missing_asset_is_404_not_the_spa(db_path, static_dir):
    client = make_app(db_path, static_dir).test_client()
    r = client.get('/assets/index-OLD.js')
    assert r.status_code == 404
    assert 'immutable' not in r.headers.get('Cache-Control', '')


@pytest.mark.parametrize('encoding,decode', [('gzip', gzip.decompress), ('br', brotli.decompress)])
def test_text_responses_are_compressed(db_path, static_dir, encoding, decode):
    client = make_app(db_path, static_dir).test_client()
    for _ in range(2):  # second time comes from the compressed-asset cache
        r = client.get('/assets/index-abc.js', headers={'Accept-Encoding': encoding})
        assert r.headers['Content-Encoding'] == encoding
        assert 'Accept-Encoding' in r.headers['Vary']
        assert int(r.headers['Content-Length']) < len(BIG_JS) / 5
        assert decode(r.get_data()).decode() == BIG_JS
        assert r.headers['Cache-Control'] == 'public, max-age=31536000, immutable'
    r = client.get('/', headers={'Accept-Encoding': encoding})
    assert r.headers.get('Content-Encoding') in (None, encoding)   # tiny html may stay below the minimum size
    plain = client.get('/assets/index-abc.js')
    assert 'Content-Encoding' not in plain.headers and plain.get_data().decode() == BIG_JS


def test_api_json_compressed_but_never_served_from_cache(db_path, static_dir):
    app = make_app(db_path, static_dir)
    client = app.test_client()
    login = client.post('/api/admin/login', json={'password': ADMIN_PW}).json
    admin = {'Authorization': f'Bearer {login["token"]}'}
    start_round(client, admin, name='A' * 90)
    names = []
    for n in ('First name ' * 8, 'Second name ' * 8):
        client.patch('/api/admin/rounds/current', json={'name': n[:100]}, headers=admin)
        r = client.get('/api/events/ministry/current', headers={'Accept-Encoding': 'gzip'})
        body = gzip.decompress(r.get_data()) if r.headers.get('Content-Encoding') == 'gzip' else r.get_data()
        names.append(body)
    assert names[0] != names[1]


# ------------------------------------------------------------------ rate limits

def test_sliding_window_unit():
    now = [0.0]
    lim = SlidingWindowLimiter(3, window=60, clock=lambda: now[0])
    assert [lim.hit('a') for _ in range(3)] == [0, 0, 0]
    wait = lim.hit('a')
    assert 59 < wait <= 60
    assert lim.hit('b') == 0           # per key
    now[0] = 60.5
    assert lim.hit('a') == 0           # window slid
    assert SlidingWindowLimiter(0).hit('x') == 0   # 0 disables


def test_lookup_limit_429_with_retry_after(db_path):
    client = make_app(db_path, RATE_LIMIT_LOOKUPS_PER_MIN=5).test_client()
    codes = [client.get(f'/api/profile/{100 + i}').status_code for i in range(5)]
    assert codes == [404] * 5
    r = client.get('/api/profile/999')
    assert r.status_code == 429
    assert r.json['code'] == 'RATE_LIMITED'
    assert 1 <= int(r.headers['Retry-After']) <= 60
    assert r.json['details']['retry_after'] == int(r.headers['Retry-After'])
    # every lookup route shares the bucket
    for path in ('/api/events/ministry/current/application/1', '/api/events/tyrant/previous-application/1',
                 '/api/events/ministry/current/assignments/1'):
        assert client.get(path).status_code == 429, path
    # another client IP has its own budget (TRUSTED_PROXY_HOPS=1: the right-most X-Forwarded-For entry)
    assert client.get('/api/profile/1', headers={'X-Forwarded-For': '203.0.113.9'}).status_code == 404


def test_submit_limit_and_separate_buckets(db_path):
    app = make_app(db_path, RATE_LIMIT_SUBMITS_PER_MIN=3, RATE_LIMIT_LOOKUPS_PER_MIN=100)
    client = app.test_client()
    login = client.post('/api/admin/login', json={'password': ADMIN_PW}).json
    admin = {'Authorization': f'Bearer {login["token"]}'}
    start_round(client, admin)
    for i in range(2):
        apply(client, f'{500 + i}', expect=201)
    assert client.put('/api/profile/777', json={'game_name': 'X'}).status_code == 201
    r = apply(client, '600')
    assert r.status_code == 429 and r.json['code'] == 'RATE_LIMITED' and 'Retry-After' in r.headers
    assert client.put('/api/profile/778', json={'game_name': 'Y'}).status_code == 429
    # lookups are a separate bucket, and admin calls are never limited
    assert client.get('/api/profile/500').status_code == 200
    r = client.put('/api/events/ministry/current/application/601', headers=admin,
                   json={'profile': {'game_name': 'Adm', 'alliance': 'ABC'}, 'answers': {}})
    assert r.status_code == 201
    # a forged token does not buy an exemption
    r = client.put('/api/profile/779', json={'game_name': 'Z'}, headers={'Authorization': 'Bearer forged'})
    assert r.status_code == 429


def test_rate_limits_from_env(monkeypatch, db_path):
    monkeypatch.setenv('RATE_LIMIT_LOOKUPS_PER_MIN', '2')
    monkeypatch.setenv('RATE_LIMIT_SUBMITS_PER_MIN', '0')
    app = create_app({'TESTING': True, 'DATABASE_PATH': db_path, 'SECRET_KEY': 'test-secret-key-not-a-placeholder',
                      'ADMIN_PASSWORD': ADMIN_PW, 'STATIC_DIR': '/nonexistent'})
    assert app.config['RATE_LIMIT_LOOKUPS_PER_MIN'] == 2 and app.config['RATE_LIMIT_SUBMITS_PER_MIN'] == 0
    client = app.test_client()
    assert [client.get('/api/profile/1').status_code for _ in range(3)] == [404, 404, 429]
    assert all(client.put(f'/api/profile/{i}', json={'game_name': 'N'}).status_code == 201 for i in range(20))


def test_public_reads_without_fid_are_not_limited(db_path):
    client = make_app(db_path, RATE_LIMIT_LOOKUPS_PER_MIN=1).test_client()
    assert all(client.get('/api/events').status_code == 200 for _ in range(5))
    assert all(client.get('/api/settings/public').status_code == 200 for _ in range(5))


# ------------------------------------------------------------------ round renaming

def test_rename_round_any_status(client, admin):
    first = start_round(client, admin, name='Imported from previous system')
    second = start_round(client, admin, name='October')     # closes the first one
    assert client.get(f'/api/admin/rounds/{first["id"]}', headers=admin).json['status'] == 'closed'
    r = client.patch(f'/api/admin/rounds/{first["id"]}', json={'name': '  September 2026  '}, headers=admin)
    assert r.status_code == 200, r.json
    assert r.json['name'] == 'September 2026' and r.json['status'] == 'closed'
    # PUT still refuses other changes to a closed round
    assert client.put(f'/api/admin/rounds/{first["id"]}', json={'closing_time': None},
                      headers=admin).status_code in (403, 409)
    r = client.patch(f'/api/admin/rounds/{second["id"]}', json={'name': 'Oct'}, headers=admin)
    assert r.json['name'] == 'Oct' and r.json['status'] == 'open'
    assert client.get('/api/events/ministry/current').json['name'] == 'Oct'


def test_rename_round_validation_and_auth(client, admin):
    rnd = start_round(client, admin)
    assert client.patch(f'/api/admin/rounds/{rnd["id"]}', json={'name': 'x'}).status_code == 401
    r = client.patch(f'/api/admin/rounds/{rnd["id"]}', json={'name': '  '}, headers=admin)
    assert r.status_code == 400 and r.json['field'] == 'name'
    r = client.patch(f'/api/admin/rounds/{rnd["id"]}', json={'name': 'y' * 101}, headers=admin)
    assert r.status_code == 400
    r = client.patch(f'/api/admin/rounds/{rnd["id"]}', json={'name': 'ok', 'status': 'closed'}, headers=admin)
    assert r.status_code == 400 and r.json['field'] == 'status'
    assert client.patch('/api/admin/rounds/99999', json={'name': 'z'}, headers=admin).status_code == 404
