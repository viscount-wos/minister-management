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
INSECURE_DEFAULT_KEYS = {'', 'dev-secret-key', 'dev-secret-key-change-in-production', 'your-secret-key-here-change-this'}


def _config_from_env():
    dev = os.getenv('FLASK_ENV') == 'development'
    cfg = {
        'DEV_MODE': dev,
        'SECRET_KEY': os.getenv('SECRET_KEY', ''),
        'DATABASE_PATH': os.getenv('DATABASE_PATH', '/data/minister.db'),
        'ADMIN_PASSWORD': os.getenv('ADMIN_PASSWORD') or ('admin123' if dev else None),
        'MINISTER_PASSWORD': os.getenv('MINISTER_PASSWORD') or ('minister123' if dev else None),
        'STATIC_DIR': STATIC_DIR,
        'JSON_SORT_KEYS': False,
        'MAX_CONTENT_LENGTH': 5 * 1024 * 1024,
    }
    return cfg


def _harden_config(cfg):
    if cfg.get('SECRET_KEY', '') in INSECURE_DEFAULT_KEYS:
        if cfg.get('DEV_MODE') and cfg.get('SECRET_KEY'):
            logger.warning('Using a placeholder SECRET_KEY (development mode only)')
        else:
            # A random per-process key is safe (tokens just stop working on restart);
            # a guessable key would let anyone mint admin tokens.
            logger.warning('SECRET_KEY missing or a known placeholder; using a random key for this process')
            cfg['SECRET_KEY'] = secrets.token_urlsafe(48)
    for key in ('ADMIN_PASSWORD', 'MINISTER_PASSWORD'):
        if not cfg.get(key):
            logger.warning('%s not set: that login is disabled', key)


def create_app(config=None):
    from core import applications, auth, db, profiles, rounds, settings
    from core.errors import ApiError, register_error_handlers
    from events import register_defaults
    from events.ministry import routes as ministry_routes

    app = Flask(__name__, static_folder=None)
    app.config.update(_config_from_env())
    if config:
        app.config.update(config)
    _harden_config(app.config)
    app.json.sort_keys = False
    CORS(app)

    register_defaults()
    register_error_handlers(app)
    db.init_app(app)

    for module in (auth, settings, profiles, rounds, applications):
        app.register_blueprint(module.bp)
    app.register_blueprint(ministry_routes.bp)

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
        if not os.path.isfile(os.path.join(static_dir, 'index.html')):
            return jsonify({'error': 'Frontend not built', 'code': 'NOT_FOUND', 'field': None}), 404
        return send_from_directory(static_dir, 'index.html')

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
