"""Global settings (not per round). Currently: state_number."""
from flask import Blueprint, jsonify

from core.auth import require_admin
from core.db import get_db
from core.errors import get_json_body
from core.validation import validate_str

bp = Blueprint('settings', __name__)

DEFAULTS = {'state_number': '2694'}
PUBLIC_KEYS = ('state_number',)


def get_setting(key, default=None):
    row = get_db().execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    if row:
        return row['value']
    return DEFAULTS.get(key, default) if default is None else default


def set_setting(key, value):
    db = get_db()
    db.execute('INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value',
               (key, value))
    db.commit()


def public_settings():
    return {k: get_setting(k) for k in PUBLIC_KEYS}


@bp.route('/api/settings/public', methods=['GET'])
def get_public_settings():
    return jsonify(public_settings())


@bp.route('/api/admin/settings', methods=['GET'])
@require_admin
def admin_get_settings():
    return jsonify(public_settings())


@bp.route('/api/admin/settings', methods=['PUT'])
@require_admin
def admin_put_settings():
    data = get_json_body()
    if 'state_number' in data:
        set_setting('state_number', validate_str(data['state_number'], 'state_number', 10, required=True))
    return jsonify(public_settings())
