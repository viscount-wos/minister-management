"""wos-events Flask app factory.

Run locally: ``python app.py``. Gunicorn (Dockerfile) loads ``app:app``; the
module-level ``app`` is created lazily on first access so importing this module
(e.g. from tests) does not touch the production database path.
"""
import logging
import os
import secrets

from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
INSECURE_DEFAULT_KEYS = {'', 'dev-secret-key', 'dev-secret-key-change-in-production', 'your-secret-key-here-change-this',
                         'change-me', 'changeme', 'secret'}
INSECURE_PASSWORDS = {'admin123', 'minister123', 'your-admin-password-here', 'your-minister-password-here',
                      'changeme', 'change-me', 'password', 'admin', 'minister'}
MIN_SECRET_KEY_LEN = 16
MIN_PASSWORD_LEN = 12


class ConfigError(RuntimeError):
    """Unsafe configuration: the app refuses to start."""


def _env_flag(name):
    return os.getenv(name, '').strip().lower() in ('1', 'true', 'yes')


def _config_from_env():
    dev = os.getenv('FLASK_ENV') == 'development'
    insecure_dev = dev and _env_flag('ALLOW_INSECURE_DEV')
    cfg = {
        'DEV_MODE': dev,
        # Placeholder secrets/passwords are accepted ONLY with FLASK_ENV=development AND ALLOW_INSECURE_DEV=1.
        'ALLOW_INSECURE_DEV': insecure_dev,
        'SECRET_KEY': os.getenv('SECRET_KEY', ''),
        'DATABASE_PATH': os.getenv('DATABASE_PATH', '/data/minister.db'),
        'ADMIN_PASSWORD': os.getenv('ADMIN_PASSWORD') or ('admin123' if insecure_dev else None),
        'MINISTER_PASSWORD': os.getenv('MINISTER_PASSWORD') or ('minister123' if insecure_dev else None),
        # Explicit, one-off v1.4 import (H1). Prefer `python -m core.migrate`.
        'MIGRATE_V14': _env_flag('MIGRATE_V14'),
        'TRUSTED_PROXY_HOPS': int(os.getenv('TRUSTED_PROXY_HOPS', '1') or 0),
        # Public player endpoints, requests per minute per client IP (0 = off). See core/ratelimit.py.
        'RATE_LIMIT_LOOKUPS_PER_MIN': int(os.getenv('RATE_LIMIT_LOOKUPS_PER_MIN', '30') or 0),
        'RATE_LIMIT_SUBMITS_PER_MIN': int(os.getenv('RATE_LIMIT_SUBMITS_PER_MIN', '10') or 0),
        'CORS_ORIGINS': [o.strip() for o in os.getenv('CORS_ORIGINS', '').split(',') if o.strip()],
        'STATIC_DIR': STATIC_DIR,
        'JSON_SORT_KEYS': False,
        'MAX_CONTENT_LENGTH': 5 * 1024 * 1024,
    }
    return cfg


def _harden_config(cfg):
    """Refuse to start with guessable secrets (H2/M4).

    - SECRET_KEY missing: production refuses (every instance/restart would invent its own key, so
      admin tokens would randomly 401); development uses a random per-process key.
    - SECRET_KEY a known placeholder or < 16 chars, or a known placeholder password: refused unless
      FLASK_ENV=development AND ALLOW_INSECURE_DEV=1 (then logged loudly).
    """
    dev = bool(cfg.get('DEV_MODE'))
    insecure_ok = dev and bool(cfg.get('ALLOW_INSECURE_DEV'))
    key = cfg.get('SECRET_KEY') or ''
    if not key:
        if dev:
            logger.warning('SECRET_KEY not set (development): using a random key for this process')
            cfg['SECRET_KEY'] = secrets.token_urlsafe(48)
        else:
            raise ConfigError('SECRET_KEY is not set. Refusing to start outside development: set a long random '
                              'SECRET_KEY (e.g. python -c "import secrets; print(secrets.token_urlsafe(48))").')
    elif key in INSECURE_DEFAULT_KEYS or len(key) < MIN_SECRET_KEY_LEN:
        if insecure_ok:
            logger.warning('INSECURE: placeholder SECRET_KEY accepted (FLASK_ENV=development, ALLOW_INSECURE_DEV=1). '
                           'Anyone who knows it can mint admin tokens; never expose this instance.')
        else:
            raise ConfigError('SECRET_KEY is a known placeholder or shorter than 16 characters. Refusing to start '
                              '(allowed only with FLASK_ENV=development and ALLOW_INSECURE_DEV=1).')
    for key_name in ('ADMIN_PASSWORD', 'MINISTER_PASSWORD'):
        pw = cfg.get(key_name)
        if not pw:
            logger.warning('%s not set: that login is disabled', key_name)
            continue
        if pw in INSECURE_PASSWORDS:
            if insecure_ok:
                logger.warning('INSECURE: %s is a well-known default (development only)', key_name)
            else:
                raise ConfigError(f'{key_name} is a well-known default password. Refusing to start (allowed only '
                                  f'with FLASK_ENV=development and ALLOW_INSECURE_DEV=1).')
        elif len(pw) < MIN_PASSWORD_LEN and not dev:
            logger.warning('%s is shorter than %d characters; use a long random password in production',
                           key_name, MIN_PASSWORD_LEN)


def create_app(config=None):
    from core import applications, auth, db, profiles, rounds, security, settings
    from core.errors import ApiError, register_error_handlers
    from events import register_defaults
    from events.ministry import routes as ministry_routes
    from events.tyrant import routes as tyrant_routes

    app = Flask(__name__, static_folder=None)
    app.config.update(_config_from_env())
    if config:
        app.config.update(config)
    _harden_config(app.config)
    app.json.sort_keys = False
    if app.config.get('CORS_ORIGINS'):
        # The SPA and API are same-origin (Vite proxies /api in dev), so CORS is off unless asked for.
        CORS(app, resources={r'/api/*': {'origins': app.config['CORS_ORIGINS']}})

    register_defaults()
    register_error_handlers(app)
    db.init_app(app)

    for module in (auth, settings, profiles, rounds, applications):
        app.register_blueprint(module.bp)
    app.register_blueprint(ministry_routes.bp)
    app.register_blueprint(tyrant_routes.bp)

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({'status': 'healthy'})

    any_method = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']

    @app.route('/api/', defaults={'path': ''}, methods=any_method)
    @app.route('/api/<path:path>', methods=any_method)
    def api_not_found(path):
        raise ApiError(404, 'NOT_FOUND', 'Unknown API endpoint')

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_spa(path):
        static_dir = app.config['STATIC_DIR']
        if path and os.path.isfile(os.path.join(static_dir, path)):
            return send_from_directory(static_dir, path)
        if path.startswith('assets/'):
            # A missing hashed asset (e.g. an old chunk after a deploy) must 404, never get index.html
            # cached as an immutable script.
            return jsonify({'error': 'Not found', 'code': 'NOT_FOUND', 'field': None}), 404
        if not os.path.isfile(os.path.join(static_dir, 'index.html')):
            return jsonify({'error': 'Frontend not built', 'code': 'NOT_FOUND', 'field': None}), 404
        return send_from_directory(static_dir, 'index.html')

    security.init_app(app)
    return app


_app = None


def __getattr__(name):
    # Lazy ``app`` for gunicorn's ``app:app`` (PEP 562).
    global _app
    if name == 'app':
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(name)


if __name__ == '__main__':
    application = create_app()
    application.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)),
                    debug=os.getenv('FLASK_ENV') == 'development')
