"""Frost Dragon Tyrant admin routes. ``<ref>`` is a tyrant round id or ``current``.

Player routes are the generic ones (core/applications.py) with event ``tyrant``; delete is the generic
``DELETE /api/admin/applications/<id>``; round settings go through ``PUT /api/admin/rounds/<id>``.
"""
from flask import Blueprint, jsonify, request

from core.auth import require_admin
from core.db import get_db
from core.errors import not_found
from core.rounds import paginate, require_current_round, require_round
from events.tyrant import filters, logic

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


def _filters(rnd):
    return filters.parse_filters(request.args, logic.round_settings(rnd))


@bp.route('/api/admin/tyrant/rounds/<ref>/applications', methods=['GET'])
@require_admin
def admin_list(ref):
    """Filters: see events/tyrant/filters.py (q, alliance, min_furnace, min/max_power, min/max_gems, windows, rush,
    vc, troop, min_camp, min_tier, <type>_camp, <type>_tier, roles, roles_mode, submitted_from/to, days; AND).
    &sort=submitted|updated|name|alliance|fid|furnace|power|gems|strength &dir=asc|desc &limit= &offset=
    -> {round_id, total, applications: [...]} (total = after filters)."""
    rnd = resolve_round(ref)
    apps = logic.filter_and_sort(logic.round_applications(get_db(), rnd), _filters(rnd), logic.round_settings(rnd),
                                 sort=request.args.get('sort') or 'submitted',
                                 direction=(request.args.get('dir') or 'desc').lower())
    body = {'round_id': rnd['id']}
    body.update(paginate(apps, 'applications'))
    return jsonify(body)


@bp.route('/api/admin/tyrant/rounds/<ref>/summary', methods=['GET'])
@require_admin
def admin_summary(ref):
    """Same filters as the list: the counts are computed for the FILTERED set. Also returns round_total
    (unfiltered) and alliance_options (every alliance of the round, for the filter picker)."""
    rnd = resolve_round(ref)
    settings = logic.round_settings(rnd)
    every = logic.round_applications(get_db(), rnd)
    out = {'round_id': rnd['id'], 'round_total': len(every), 'filters': _filters(rnd)}
    out.update(logic.summary(filters.apply_filters(every, out['filters'], settings), settings))
    out['alliance_options'] = sorted({(a['profile'].get('alliance') or '').strip().upper() for a in every} - {''})
    return jsonify(out)


@bp.route('/api/admin/tyrant/rounds/<ref>/export', methods=['GET'])
@require_admin
def admin_export_xlsx(ref):
    """Same filters as the list (the download is the filtered view)."""
    rnd = resolve_round(ref)
    return logic.export_xlsx_response(get_db(), rnd, _filters(rnd))


@bp.route('/api/admin/tyrant/rounds/<ref>/export.csv', methods=['GET'])
@require_admin
def admin_export_csv(ref):
    rnd = resolve_round(ref)
    return logic.export_csv_response(get_db(), rnd, _filters(rnd))
