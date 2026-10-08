"""Applications: one per (round, player). Generic across events; answers are validated by the event spec."""
import json

from flask import Blueprint, jsonify, request

from core.auth import require_admin
from core.db import get_db
from core.errors import ApiError, get_json_body, not_found, validation_error
from core.profiles import (get_profile_by_id, get_profile_row, profile_to_json, snapshot, upsert_profile,
                           validate_profile_fields)
from core.rounds import current_round_row, get_round_row, require_current_round, require_round
from core.validation import is_past, now_iso, validate_fid
from events import get_event

bp = Blueprint('applications', __name__)


def application_to_json(row, round_row=None):
    if row is None:
        return None
    d = dict(row)
    out = {
        'id': d['id'],
        'round_id': d['round_id'],
        'player_id': d['player_id'],
        'fid': d.get('fid'),
        'answers': json.loads(d['answers'] or '{}'),
        'profile_snapshot': json.loads(d['profile_snapshot'] or '{}'),
        'created_at': d['created_at'],
        'updated_at': d['updated_at'],
    }
    if round_row is not None:
        out['event'] = round_row['event']
        out['round_name'] = round_row['name']
    elif 'event' in d:
        out['event'] = d['event']
        out['round_name'] = d.get('round_name')
    return out


_APP_SELECT = ('SELECT a.*, p.fid, r.event, r.name AS round_name FROM applications a '
               'JOIN profiles p ON p.id = a.player_id JOIN rounds r ON r.id = a.round_id ')


def get_application(round_id, player_id):
    return get_db().execute(_APP_SELECT + 'WHERE a.round_id = ? AND a.player_id = ?',
                            (round_id, player_id)).fetchone()


def get_application_by_id(app_id):
    return get_db().execute(_APP_SELECT + 'WHERE a.id = ?', (app_id,)).fetchone()


def previous_application(event, player_id, before_round_id=None):
    """Latest application by this player for ``event`` in a round EARLIER than ``before_round_id``.

    Rounds are ordered by id (autoincrement = creation order). With no current
    round, the player's latest application for the event is returned.
    """
    sql = _APP_SELECT + 'WHERE r.event = ? AND a.player_id = ?'
    params = [event, player_id]
    if before_round_id is not None:
        sql += ' AND a.round_id < ?'
        params.append(before_round_id)
    sql += ' ORDER BY a.round_id DESC LIMIT 1'
    return get_db().execute(sql, params).fetchone()


def save_application(round_row, profile_json, answers, commit=True):
    """Insert or update the application for (round, profile). Returns (row, created)."""
    db = get_db()
    now = now_iso()
    existing = get_application(round_row['id'], profile_json['id'])
    snap = json.dumps(snapshot(profile_json))
    if existing:
        db.execute('UPDATE applications SET answers=?, profile_snapshot=?, updated_at=? WHERE id=?',
                   (json.dumps(answers), snap, now, existing['id']))
        created = False
    else:
        db.execute('INSERT INTO applications (round_id, player_id, answers, profile_snapshot, created_at, updated_at) '
                   'VALUES (?, ?, ?, ?, ?, ?)', (round_row['id'], profile_json['id'], json.dumps(answers), snap,
                                                 now, now))
        created = True
    if commit:
        db.commit()
    return get_application(round_row['id'], profile_json['id']), created


def delete_application_row(app_row):
    db = get_db()
    spec = get_event(app_row['event'], need_rounds=False)
    spec.on_application_deleted(db, app_row['round_id'], app_row['player_id'])
    db.execute('DELETE FROM applications WHERE id = ?', (app_row['id'],))
    db.commit()


# ---------------------------------------------------------------- public routes

@bp.route('/api/events/<event>/current/application/<fid>', methods=['GET'])
def get_current_application(event, fid):
    rnd = require_current_round(event)
    prof = get_profile_row(fid)
    app_row = get_application(rnd['id'], prof['id']) if prof else None
    if not app_row:
        raise not_found('No application in the current round', code='NOT_FOUND')
    return jsonify(application_to_json(app_row, rnd))


@bp.route('/api/events/<event>/previous-application/<fid>', methods=['GET'])
def get_previous_application(event, fid):
    get_event(event)
    prof = get_profile_row(fid)
    cur = current_round_row(event)
    row = previous_application(event, prof['id'], cur['id'] if cur else None) if prof else None
    if not row:
        raise not_found('No earlier application found')
    return jsonify(application_to_json(row))


@bp.route('/api/events/<event>/current/application/<fid>', methods=['PUT'])
def put_current_application(event, fid):
    """Upsert profile + application in the current round.

    New applications are blocked after the round's closing_time
    (403 APPLICATIONS_CLOSED); existing ones stay editable until an admin
    closes the round.
    """
    spec = get_event(event)
    rnd = require_current_round(event)
    data = get_json_body()
    fid = validate_fid(fid)
    body_fid = (data.get('profile') or {}).get('fid') if isinstance(data.get('profile'), dict) else None
    if body_fid is not None and str(body_fid).strip() != fid:
        raise validation_error('profile.fid does not match the FID in the URL', 'profile.fid')

    existing_profile = get_profile_row(fid)
    existing_app = get_application(rnd['id'], existing_profile['id']) if existing_profile else None
    if existing_app is None and is_past(rnd['closing_time']):
        raise ApiError(403, 'APPLICATIONS_CLOSED', 'Applications are closed')

    fields = validate_profile_fields(data.get('profile'))
    answers = spec.validate_answers(data.get('answers'), rnd)
    profile, profile_created = upsert_profile(fid, fields, required=spec.required_profile_fields, commit=False)
    app_row, created = save_application(rnd, profile, answers, commit=False)
    get_db().commit()
    return jsonify({
        'created': created,
        'profile_created': profile_created,
        'application': application_to_json(app_row, rnd),
        'profile': profile,
    }), (201 if created else 200)


# ---------------------------------------------------------------- admin routes

@bp.route('/api/admin/rounds/<int:round_id>/applications', methods=['GET'])
@require_admin
def admin_list_applications(round_id):
    rnd = require_round(round_id)
    spec = get_event(rnd['event'], need_rounds=False)
    sql = 'SELECT a.*, p.fid FROM applications a JOIN profiles p ON p.id = a.player_id WHERE a.round_id = ?'
    params = [round_id]
    alliance = request.args.get('alliance', '').strip()
    if alliance:
        sql += ' AND UPPER(p.alliance) = ?'
        params.append(alliance.upper())
    sql += ' ORDER BY a.created_at DESC, a.id DESC'
    out = []
    for row in get_db().execute(sql, params).fetchall():
        app_json = application_to_json(row, rnd)
        app_json['profile'] = profile_to_json(get_profile_by_id(row['player_id']))
        out.append(spec.decorate_application(app_json, rnd))
    return jsonify({'round_id': round_id, 'applications': out})


@bp.route('/api/admin/applications/<int:app_id>', methods=['GET'])
@require_admin
def admin_get_application(app_id):
    row = get_application_by_id(app_id)
    if not row:
        raise not_found('Application not found')
    rnd = get_round_row(row['round_id'])
    out = application_to_json(row, rnd)
    out['profile'] = profile_to_json(get_profile_by_id(row['player_id']))
    return jsonify(get_event(rnd['event'], need_rounds=False).decorate_application(out, rnd))


@bp.route('/api/admin/applications/<int:app_id>', methods=['PUT'])
@require_admin
def admin_update_application(app_id):
    """Admin edit: body {profile?: {...}, answers?: {...}}. Answers keys are merged then validated.

    No closing-time check (admins can always edit).
    """
    row = get_application_by_id(app_id)
    if not row:
        raise not_found('Application not found')
    rnd = get_round_row(row['round_id'])
    spec = get_event(rnd['event'], need_rounds=False)
    data = get_json_body()
    fields = validate_profile_fields(data.get('profile'))
    answers = json.loads(row['answers'] or '{}')
    if 'answers' in data:
        if not isinstance(data['answers'], dict):
            raise validation_error('answers must be an object', 'answers')
        answers.update(data['answers'])
    answers = spec.validate_answers(answers, rnd)
    profile, _ = upsert_profile(row['fid'], fields, required=('game_name',), commit=False)
    app_row, _ = save_application(rnd, profile, answers, commit=False)
    get_db().commit()
    out = application_to_json(app_row, rnd)
    out['profile'] = profile
    return jsonify(spec.decorate_application(out, rnd))


@bp.route('/api/admin/applications/<int:app_id>', methods=['DELETE'])
@require_admin
def admin_delete_application(app_id):
    row = get_application_by_id(app_id)
    if not row:
        raise not_found('Application not found')
    delete_application_row(row)
    return jsonify({'deleted': True, 'id': app_id})


@bp.route('/api/admin/rounds/<int:round_id>/export', methods=['GET'])
@require_admin
def admin_export_round(round_id):
    rnd = require_round(round_id)
    return get_event(rnd['event'], need_rounds=False).export_round(rnd)
