"""Global settings (not per round): state_number, state_generation.

state_generation (1..the newest hero generation in gamedata/heroes.json, 17 today; default = that newest one) is the
state's current hero generation. GET /api/heroes defaults its ``max_gen`` to it, so planners never offer a hero the
state cannot have yet.
"""
import re

from flask import Blueprint, jsonify

from core.auth import require_admin
from core.db import get_db
from core.errors import get_json_body, validation_error
from core.validation import validate_str

bp = Blueprint('settings', __name__)

# No default state: the UI hides its welcome line until an admin sets one (v1.4 showed a hardcoded 2694).
DEFAULTS = {'state_number': None}
PUBLIC_KEYS = ('state_number', 'state_generation')


def get_setting(key, default=None):
    row = get_db().execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    if row:
        return row['value']
    return DEFAULTS.get(key, default) if default is None else default


def set_setting(key, value, commit=True):
    db = get_db()
    db.execute('INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value',
               (key, value))
    if commit:
        db.commit()


def max_generation():
    from core.heroes import library
    return library()['max_generation']


def state_generation():
    """The state's hero generation as an int (default and fallback: the newest generation in the hero library)."""
    top = max_generation()
    raw = get_setting('state_generation')
    if isinstance(raw, str) and raw.isdigit() and 1 <= int(raw) <= top:
        return int(raw)
    return top


def validate_generation(value, field='state_generation'):
    """A whole number 1..max generation (int or digit string) or VALIDATION_ERROR naming ``field``."""
    top = max_generation()
    if isinstance(value, int) and not isinstance(value, bool):
        n = value
    elif isinstance(value, str) and re.fullmatch(r'\s*\d{1,3}\s*', value):
        n = int(value)
    else:
        n = None
    if n is None or not 1 <= n <= top:
        raise validation_error(f'{field} must be a whole number 1-{top}', field)
    return n


def public_settings():
    return {'state_number': get_setting('state_number'), 'state_generation': state_generation()}


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
    """Body: any of {state_number, state_generation}. Everything is validated before anything is written."""
    data = get_json_body()
    updates = {}
    if 'state_number' in data:
        updates['state_number'] = validate_str(data['state_number'], 'state_number', 10, required=True)
    if 'state_generation' in data:
        updates['state_generation'] = str(validate_generation(data['state_generation']))
    for key, value in updates.items():
        set_setting(key, value, commit=False)
    get_db().commit()
    return jsonify(public_settings())
