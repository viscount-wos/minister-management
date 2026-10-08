"""Rounds: one occurrence of an event. At most one OPEN round per event (the current round)."""
import json
import sqlite3

from flask import Blueprint, jsonify

from core.auth import require_admin
from core.db import get_db
from core.errors import conflict, get_json_body, not_found, validation_error
from core.validation import is_past, now_iso, validate_closing_time, validate_str
from events import all_events, get_event

bp = Blueprint('rounds', __name__)

STATUSES = ('draft', 'open', 'closed')


def round_to_json(row, public=False):
    if row is None:
        return None
    d = dict(row)
    spec = get_event(d['event'], need_rounds=False)
    settings = spec.default_settings()
    try:
        settings.update(json.loads(d.get('settings') or '{}'))
    except ValueError:
        pass
    out = {
        'id': d['id'],
        'event': d['event'],
        'name': d['name'],
        'status': d['status'],
        'closing_time': d['closing_time'],
        'is_closed_for_new': is_past(d['closing_time']),
        'settings': spec.public_settings(settings) if public else settings,
        'created_at': d['created_at'],
        'updated_at': d['updated_at'],
    }
    return out


def round_settings(row):
    spec = get_event(row['event'], need_rounds=False)
    settings = spec.default_settings()
    settings.update(json.loads(row['settings'] or '{}'))
    return settings


def get_round_row(round_id):
    return get_db().execute('SELECT * FROM rounds WHERE id = ?', (round_id,)).fetchone()


def require_round(round_id):
    row = get_round_row(round_id)
    if not row:
        raise not_found(f'Round {round_id} not found')
    return row


def current_round_row(event):
    return get_db().execute("SELECT * FROM rounds WHERE event = ? AND status = 'open'", (event,)).fetchone()


def require_current_round(event):
    get_event(event)
    row = current_round_row(event)
    if not row:
        raise not_found(f'No open round for {event}', code='NO_CURRENT_ROUND')
    return row


def _insert_round(event, name, status, closing_time, settings):
    db = get_db()
    now = now_iso()
    try:
        cur = db.execute('INSERT INTO rounds (event, name, status, closing_time, settings, created_at, updated_at) '
                         'VALUES (?, ?, ?, ?, ?, ?, ?)',
                         (event, name, status, closing_time, json.dumps(settings), now, now))
    except sqlite3.IntegrityError:
        raise conflict(f'{event} already has an open round; close it first or use start-new-round',
                       code='ROUND_ALREADY_OPEN')
    return cur.lastrowid


def _validate_status(value):
    if value not in STATUSES:
        raise validation_error('status must be one of draft, open, closed', 'status')
    return value


# ---------------------------------------------------------------- public routes

@bp.route('/api/events', methods=['GET'])
def list_events():
    out = []
    for spec in all_events():
        cur = current_round_row(spec.key) if spec.has_rounds else None
        out.append({
            'key': spec.key,
            'has_rounds': spec.has_rounds,
            'current_round': ({'id': cur['id'], 'name': cur['name'], 'status': cur['status'],
                               'closing_time': cur['closing_time'],
                               'is_closed_for_new': is_past(cur['closing_time'])} if cur else None),
        })
    return jsonify({'events': out})


@bp.route('/api/events/<event>/current', methods=['GET'])
def get_current_round(event):
    return jsonify(round_to_json(require_current_round(event), public=True))


# ---------------------------------------------------------------- admin routes

@bp.route('/api/admin/events/<event>/rounds', methods=['GET'])
@require_admin
def admin_list_rounds(event):
    get_event(event)
    rows = get_db().execute(
        'SELECT r.*, (SELECT COUNT(*) FROM applications a WHERE a.round_id = r.id) AS application_count '
        'FROM rounds r WHERE r.event = ? ORDER BY r.id DESC', (event,)).fetchall()
    out = []
    for r in rows:
        j = round_to_json(r)
        j['application_count'] = r['application_count']
        out.append(j)
    return jsonify({'rounds': out})


@bp.route('/api/admin/events/<event>/rounds', methods=['POST'])
@require_admin
def admin_create_round(event):
    spec = get_event(event)
    data = get_json_body()
    name = validate_str(data.get('name'), 'name', 100, required=True)
    status = _validate_status(data.get('status', 'draft'))
    closing = validate_closing_time(data.get('closing_time'))
    settings = spec.validate_settings(data.get('settings') or {}, spec.default_settings())
    rid = _insert_round(event, name, status, closing, settings)
    get_db().commit()
    return jsonify(round_to_json(get_round_row(rid))), 201


@bp.route('/api/admin/rounds/<int:round_id>', methods=['GET'])
@require_admin
def admin_get_round(round_id):
    return jsonify(round_to_json(require_round(round_id)))


@bp.route('/api/admin/rounds/<int:round_id>', methods=['PUT'])
@require_admin
def admin_update_round(round_id):
    db = get_db()
    row = require_round(round_id)
    spec = get_event(row['event'])
    data = get_json_body()
    name = row['name']
    status = row['status']
    closing = row['closing_time']
    old_settings = round_settings(row)
    new_settings = old_settings
    if 'name' in data:
        name = validate_str(data['name'], 'name', 100, required=True)
    if 'status' in data:
        status = _validate_status(data['status'])
    if 'closing_time' in data:
        closing = validate_closing_time(data['closing_time'])
    if 'settings' in data:
        new_settings = spec.validate_settings(data['settings'], old_settings)
    try:
        db.execute('UPDATE rounds SET name=?, status=?, closing_time=?, settings=?, updated_at=? WHERE id=?',
                   (name, status, closing, json.dumps(new_settings), now_iso(), round_id))
    except sqlite3.IntegrityError:
        raise conflict(f'{row["event"]} already has an open round', code='ROUND_ALREADY_OPEN')
    extra = {}
    if new_settings != old_settings:
        extra = spec.on_settings_changed(db, get_round_row(round_id), old_settings, new_settings) or {}
    db.commit()
    out = round_to_json(get_round_row(round_id))
    out.update(extra)
    return jsonify(out)


@bp.route('/api/admin/events/<event>/start-new-round', methods=['POST'])
@require_admin
def admin_start_new_round(event):
    """Close the current round (nothing deleted) and open a new one.

    Settings carry over from the previous round, minus per-occurrence state
    (event specs decide what resets, e.g. ministry clears published_days).
    """
    spec = get_event(event)
    db = get_db()
    data = get_json_body()
    name = validate_str(data.get('name'), 'name', 100, required=True)
    closing = validate_closing_time(data.get('closing_time'))
    current = current_round_row(event)
    if current is None:
        current = db.execute('SELECT * FROM rounds WHERE event = ? ORDER BY id DESC LIMIT 1', (event,)).fetchone()
    base = spec.default_settings()
    if current is not None:
        base = spec.carry_over_settings(round_settings(current))
    settings = spec.validate_settings(data.get('settings') or {}, base)
    closed = None
    now = now_iso()
    if current is not None and current['status'] == 'open':
        db.execute("UPDATE rounds SET status='closed', updated_at=? WHERE id=?", (now, current['id']))
        closed = current['id']
    rid = _insert_round(event, name, 'open', closing, settings)
    db.commit()
    return jsonify({'round': round_to_json(get_round_row(rid)),
                    'closed_round': round_to_json(get_round_row(closed)) if closed else None}), 201

