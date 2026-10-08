"""Ministry HTTP routes. Admin routes are scoped to a round: ``<ref>`` is a round id or ``current``."""
import json

from flask import Blueprint, Response, jsonify

from core.auth import require_admin
from core.db import begin_immediate, get_db
from core.errors import get_json_body, not_found, validation_error
from core.profiles import find_profile
from core.rounds import get_round_row, require_current_round, require_round, require_writable
from core.validation import now_iso
from events.ministry import logic
from events.ministry import validation as mv

bp = Blueprint('ministry', __name__)

EVENT = 'ministry'


def resolve_round(ref):
    if ref == 'current':
        return require_current_round(EVENT)
    try:
        rid = int(ref)
    except (TypeError, ValueError):
        raise not_found(f'Round {ref} not found')
    row = require_round(rid)
    if row['event'] != EVENT:
        raise not_found(f'Round {rid} is not a ministry round')
    return row


# ---------------------------------------------------------------- public

@bp.route('/api/events/ministry/current/heatmap', methods=['GET'])
def public_heatmap():
    rnd = require_current_round(EVENT)
    return jsonify(logic.heatmap(get_db(), rnd['id']))


@bp.route('/api/events/ministry/current/schedule', methods=['GET'])
def public_published_days():
    rnd = require_current_round(EVENT)
    return jsonify({'round_id': rnd['id'], 'published_days': logic.active_published_days(logic.round_settings(rnd))})


@bp.route('/api/events/ministry/current/schedule/<day>', methods=['GET'])
def public_schedule_day(day):
    rnd = require_current_round(EVENT)
    if str(day).lower() not in logic.MINISTRY_WEEKDAYS:
        raise validation_error('Invalid day (expected monday, tuesday, thursday or friday)', 'day')
    out = logic.published_schedule(get_db(), rnd, day)
    out['round_id'] = rnd['id']
    return jsonify(out)


@bp.route('/api/events/ministry/current/assignments/<fid>', methods=['GET'])
def public_player_assignments(fid):
    """A player's own assignments in the current round: day + time slot, PUBLISHED days only.

    v1.4 also returned draft (unpublished) days; anyone holding an FID could read them, so drafts are
    now filtered server-side. Admins see everything through the admin assignment endpoints.
    """
    rnd = require_current_round(EVENT)
    prof = find_profile(fid)
    db = get_db()
    if not prof or not db.execute('SELECT 1 FROM applications WHERE round_id = ? AND player_id = ?',
                                  (rnd['id'], prof['id'])).fetchone():
        raise not_found('No application in the current round')
    published = logic.active_published_days(logic.round_settings(rnd))
    mine = logic.player_assignments(db, rnd['id'], prof['id'])
    return jsonify({'round_id': rnd['id'], 'published_days': published,
                    'assignments': {d: v for d, v in mine.items() if d in published}})


# ---------------------------------------------------------------- admin

@bp.route('/api/admin/ministry/rounds/<ref>/auto-assign', methods=['POST'])
@require_admin
def admin_auto_assign(ref):
    rnd = resolve_round(ref)
    require_writable(rnd)
    data = get_json_body()
    out = logic.auto_assign(get_db(), rnd, data.get('day'))
    out['round_id'] = rnd['id']
    return jsonify(out)


@bp.route('/api/admin/ministry/rounds/<ref>/assignments/<day>', methods=['GET'])
@require_admin
def admin_get_assignments(ref, day):
    rnd = resolve_round(ref)
    out = logic.get_assignments(get_db(), rnd, day)
    out['round_id'] = rnd['id']
    return jsonify(out)


@bp.route('/api/admin/ministry/rounds/<ref>/assignments/<day>', methods=['PUT'])
@require_admin
def admin_update_assignments(ref, day):
    rnd = resolve_round(ref)
    require_writable(rnd)
    data = get_json_body()
    out = logic.update_assignments(get_db(), rnd, day, data.get('assignments', {}))
    out['round_id'] = rnd['id']
    return jsonify(out)


def _set_published(rnd, day, publish):
    db = get_db()
    begin_immediate(db)  # read-modify-write of the settings JSON under the write lock (L2)
    rnd = get_round_row(rnd['id'])
    require_writable(rnd)
    settings = logic.round_settings(rnd)
    if publish:
        day = mv.validate_day(day, settings['research_day'])
    else:
        day = str(day or '').lower()
        if not day:
            raise validation_error('day is required', 'day')
    days = set(settings['published_days'])
    if publish:
        days.add(day)
    else:
        days.discard(day)
    settings['published_days'] = logic.sort_days_by_week(days)
    db.execute('UPDATE rounds SET settings = ?, updated_at = ? WHERE id = ?',
               (json.dumps(settings), now_iso(), rnd['id']))
    db.commit()
    return jsonify({'round_id': rnd['id'], 'published_days': settings['published_days']})


@bp.route('/api/admin/ministry/rounds/<ref>/publish', methods=['POST'])
@require_admin
def admin_publish(ref):
    return _set_published(resolve_round(ref), get_json_body().get('day'), True)


@bp.route('/api/admin/ministry/rounds/<ref>/unpublish', methods=['POST'])
@require_admin
def admin_unpublish(ref):
    return _set_published(resolve_round(ref), get_json_body().get('day'), False)


@bp.route('/api/admin/ministry/rounds/<ref>/export', methods=['GET'])
@require_admin
def admin_export(ref):
    return logic.MinistryEvent().export_round(resolve_round(ref))


@bp.route('/api/admin/ministry/rounds/<ref>/export-json', methods=['GET'])
@require_admin
def admin_export_json(ref):
    rnd = resolve_round(ref)
    data = logic.export_json(get_db(), rnd)
    filename = f'ministry_{logic._slug(rnd["name"])}_backup.json'
    return Response(json.dumps(data, indent=2), mimetype='application/json',
                    headers={'Content-Disposition': f'attachment; filename={filename}'})


@bp.route('/api/admin/ministry/rounds/<ref>/import', methods=['POST'])
@require_admin
def admin_import_json(ref):
    rnd = resolve_round(ref)
    require_writable(rnd)
    out = logic.import_json(get_db(), rnd, get_json_body())
    out['round_id'] = rnd['id']
    return jsonify(out)
