"""Frost Dragon Tyrant admin routes. ``<ref>`` is a tyrant round id or ``current``.

Player routes are the generic ones (core/applications.py) with event ``tyrant``; delete is the generic
``DELETE /api/admin/applications/<id>``; round settings go through ``PUT /api/admin/rounds/<id>``.
"""
from flask import Blueprint, jsonify, request

from core.auth import require_admin
from core.db import get_db
from core.errors import not_found
from core.rounds import paginate, require_current_round, require_round
from events.tyrant import logic

bp = Blueprint('tyrant', __name__)


def resolve_round(ref):
    if ref == 'current':
        return require_current_round(logic.EVENT)
    try:
        rid = int(ref)
    except (TypeError, ValueError):
        raise not_found(f'Round {ref} not found')
    row = require_round(rid)
    if row['event'] != logic.EVENT:
        raise not_found(f'Round {rid} is not a tyrant round')
    return row


@bp.route('/api/admin/tyrant/rounds/<ref>/applications', methods=['GET'])
@require_admin
def admin_list(ref):
    """?q= (FID, name or Discord ID) &alliance= &sort=submitted|updated|name|alliance|fid|furnace|power|gems|strength
    &dir=asc|desc &min_furnace=<code> &min_camp=FC1..FC10 &min_tier=1..11|T11 &troop=infantry|lancer|marksman|all
    &limit= &offset= -> {round_id, total, applications: [...]}"""
    rnd = resolve_round(ref)
    apps = logic.filter_and_sort(logic.round_applications(get_db(), rnd),
                                 q=request.args.get('q', ''), alliance=request.args.get('alliance', ''),
                                 sort=request.args.get('sort') or 'submitted',
                                 direction=(request.args.get('dir') or 'desc').lower(),
                                 min_furnace=request.args.get('min_furnace', ''),
                                 min_camp=request.args.get('min_camp', ''), min_tier=request.args.get('min_tier', ''),
                                 troop=request.args.get('troop', ''))
    body = {'round_id': rnd['id']}
    body.update(paginate(apps, 'applications'))
    return jsonify(body)


@bp.route('/api/admin/tyrant/rounds/<ref>/summary', methods=['GET'])
@require_admin
def admin_summary(ref):
    rnd = resolve_round(ref)
    apps = logic.filter_and_sort(logic.round_applications(get_db(), rnd), alliance=request.args.get('alliance', ''))
    out = {'round_id': rnd['id']}
    out.update(logic.summary(apps, logic.round_settings(rnd)))
    return jsonify(out)


@bp.route('/api/admin/tyrant/rounds/<ref>/export', methods=['GET'])
@require_admin
def admin_export_xlsx(ref):
    return logic.export_xlsx_response(get_db(), resolve_round(ref))


@bp.route('/api/admin/tyrant/rounds/<ref>/export.csv', methods=['GET'])
@require_admin
def admin_export_csv(ref):
    return logic.export_csv_response(get_db(), resolve_round(ref))
