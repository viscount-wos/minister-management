"""SVS admin routes. ``<ref>`` is an svs round id or ``current``. Player routes are the generic ones
(core/applications.py) with event ``svs``; admin create is ``POST /api/admin/rounds/<ref>/applications``; delete is
the generic ``DELETE /api/admin/applications/<id>``; round settings go through ``PUT /api/admin/rounds/<id>``."""
import hmac
import json

from flask import Blueprint, jsonify, request

from core.auth import require_admin
from core.db import begin_immediate, get_db
from core.errors import ApiError, get_json_body, not_found, validation_error
from core.ratelimit import rate_limited
from core.rounds import paginate, require_current_round, require_round, require_writable
from core.validation import now_iso
from events.svs import filters, logic
from events.svs import plan as plan_mod

bp = Blueprint('svs', __name__)


def resolve_round(ref):
    if ref == 'current':
        return require_current_round(logic.EVENT)
    try:
        rid = int(ref)
    except (TypeError, ValueError):
        raise not_found(f'Round {ref} not found')
    row = require_round(rid)
    if row['event'] != logic.EVENT:
        raise not_found(f'Round {rid} is not an svs round')
    return row


def _filters(rnd):
    return filters.parse_filters(request.args, logic.round_settings(rnd))


@bp.route('/api/admin/svs/rounds/<ref>/applications', methods=['GET'])
@require_admin
def admin_list(ref):
    """Filters: events/svs/filters.py (q, alliance, hours, role, vc, troop, min_camp, min_tier, <type>_camp,
    <type>_tier, submitted_from/to, days; AND). &sort=submitted|updated|name|alliance|fid|strength|hours
    &dir=asc|desc &limit= &offset= -> {round_id, total, applications} (total = after filters)."""
    rnd = resolve_round(ref)
    apps = logic.filter_and_sort(logic.round_applications(get_db(), rnd), _filters(rnd),
                                 sort=request.args.get('sort') or 'submitted',
                                 direction=(request.args.get('dir') or 'desc').lower())
    body = {'round_id': rnd['id']}
    body.update(paginate(apps, 'applications'))
    return jsonify(body)


@bp.route('/api/admin/svs/rounds/<ref>/summary', methods=['GET'])
@require_admin
def admin_summary(ref):
    """Counts for the FILTERED set + round_total (unfiltered) + alliance_options + the active filters."""
    rnd = resolve_round(ref)
    settings = logic.round_settings(rnd)
    every = logic.round_applications(get_db(), rnd)
    out = {'round_id': rnd['id'], 'round_total': len(every), 'filters': _filters(rnd)}
    out.update(logic.summary(filters.apply_filters(every, out['filters']), settings))
    out['alliance_options'] = sorted({(a['profile'].get('alliance') or '').strip().upper() for a in every} - {''})
    return jsonify(out)


@bp.route('/api/admin/svs/rounds/<ref>/export', methods=['GET'])
@require_admin
def admin_export_xlsx(ref):
    rnd = resolve_round(ref)
    return logic.export_xlsx_response(get_db(), rnd, _filters(rnd))


@bp.route('/api/admin/svs/rounds/<ref>/export.csv', methods=['GET'])
@require_admin
def admin_export_csv(ref):
    rnd = resolve_round(ref)
    return logic.export_csv_response(get_db(), rnd, _filters(rnd))


# ---------------------------------------------------------------- battle planner (docs/SPEC.md "SVS battle planner")

def _plan_context(rnd):
    from core.heroes import library
    from core.settings import state_generation
    settings = logic.round_settings(rnd)
    return settings, state_generation(), {h['slug']: h for h in library()['heroes']}


def _plan_body(db, rnd, row, plan):
    settings, gen, by_slug = _plan_context(rnd)
    names = plan_mod.people(db, plan_mod.plan_fids(plan), rnd['id'])
    return {
        'round_id': rnd['id'],
        'round_name': rnd['name'],
        'revision': row['revision'] if row else 0,
        'updated_at': row['updated_at'] if row else None,
        'plan': plan,
        'share': plan_mod.share_info(row),
        'battle': plan_mod.battle_window(settings),
        'pet_buff_times': plan_mod.pet_buff_times(settings),
        'state_generation': gen,
        'people': names,
        'view': plan_mod.resolve_view(plan, settings, names, by_slug, public=False),
    }


@bp.route('/api/admin/svs/rounds/<ref>/plan', methods=['GET'])
@require_admin
def admin_get_plan(ref):
    """The round's battle plan (an empty main + counter plan at revision 0 before the first save), its share link,
    the battle window + pet-buff times, ``people`` (fid -> name/alliance/signed_up for every FID in the plan) and
    ``view`` (the resolved read-only plan, real names always shown)."""
    rnd = resolve_round(ref)
    db = get_db()
    row = plan_mod.load_row(db, rnd['id'])
    return jsonify(_plan_body(db, rnd, row, plan_mod.stored_plan(row)))


@bp.route('/api/admin/svs/rounds/<ref>/plan', methods=['PUT'])
@require_admin
def admin_put_plan(ref):
    """Body {revision, plan}. ``revision`` must be the one the editor loaded: otherwise 409 PLAN_CONFLICT (someone
    saved a newer one; details.revision = the current one) and nothing is written. 400 VALIDATION_ERROR (field =
    the plan path), 422 DOUBLE_BOOKED (details = where the player already is), 409 ROUND_CLOSED.
    -> 200 the GET shape with the new revision."""
    rnd = resolve_round(ref)
    require_writable(rnd)
    data = get_json_body()
    revision = data.get('revision')
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise validation_error('revision must be the plan revision you loaded (a whole number)', 'revision')
    db = get_db()
    begin_immediate(db)  # read revision + write under the write lock: two editors can't both win
    row = plan_mod.load_row(db, rnd['id'])
    current = row['revision'] if row else 0
    if revision != current:
        db.rollback()
        raise ApiError(409, 'PLAN_CONFLICT', 'Someone else saved this plan in the meantime; reload it first',
                       details={'revision': current, 'updated_at': row['updated_at'] if row else None})
    from core.heroes import library
    from core.settings import state_generation
    hero = plan_mod.HeroCheck(library()['heroes'], state_generation(),
                              allowed_legacy=plan_mod.plan_heroes(plan_mod.stored_plan(row)) if row else ())
    try:
        plan = plan_mod.validate_plan(data.get('plan'), hero)
        plan_mod.check_double(plan, plan_mod.people(db, plan_mod.plan_fids(plan), rnd['id']))
    except ApiError:
        db.rollback()
        raise
    now = now_iso()
    doc = json.dumps(plan, separators=(',', ':'))
    if row:
        db.execute('UPDATE svs_plans SET plan = ?, revision = ?, updated_at = ? WHERE round_id = ?',
                   (doc, current + 1, now, rnd['id']))
    else:
        db.execute('INSERT INTO svs_plans (round_id, plan, revision, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                   (rnd['id'], doc, current + 1, now, now))
    db.commit()
    return jsonify(_plan_body(db, rnd, plan_mod.load_row(db, rnd['id']), plan))


@bp.route('/api/admin/svs/rounds/<ref>/plan/share', methods=['POST'])
@require_admin
def admin_share_plan(ref):
    """Body {action: create | rotate | disable}. create: a secret read-only link (128-bit token) if there is none
    (idempotent); rotate: a NEW token, the old link stops working at once; disable: sharing off. Works on closed
    rounds too (it doesn't change the plan or its revision). -> {share: {enabled, token, path, created_at}}."""
    rnd = resolve_round(ref)
    action = get_json_body().get('action')
    if action not in ('create', 'rotate', 'disable'):
        raise validation_error('action must be create, rotate or disable', 'action')
    db = get_db()
    begin_immediate(db)
    row = plan_mod.load_row(db, rnd['id'])
    now = now_iso()
    if not row:
        db.execute('INSERT INTO svs_plans (round_id, plan, revision, created_at, updated_at) VALUES (?, ?, 0, ?, ?)',
                   (rnd['id'], json.dumps(plan_mod.empty_plan()), now, now))
        row = plan_mod.load_row(db, rnd['id'])
    if action == 'disable':
        db.execute('UPDATE svs_plans SET share_token = NULL, share_token_hash = NULL, share_created_at = NULL '
                   'WHERE round_id = ?', (rnd['id'],))
    elif action == 'rotate' or not row['share_token']:
        token = plan_mod.new_token()
        db.execute('UPDATE svs_plans SET share_token = ?, share_token_hash = ?, share_created_at = ? '
                   'WHERE round_id = ?', (token, plan_mod.token_hash(token), now, rnd['id']))
    db.commit()
    return jsonify({'round_id': rnd['id'], 'share': plan_mod.share_info(plan_mod.load_row(db, rnd['id']))})


@bp.route('/api/svs/plan/<token>', methods=['GET'])
@rate_limited('lookup')
def public_plan(token):
    """The shared, read-only plan (phone view). Unknown, malformed, rotated or disabled token: 404 PLAN_NOT_FOUND
    (one answer for all, so a guess learns nothing). Rate-limited like the FID lookups; noindex + no-referrer +
    no-store (core/security.py)."""
    if not plan_mod.TOKEN_RE.match(token or ''):
        raise not_found('This plan link is not valid (it may have been replaced or turned off)', code='PLAN_NOT_FOUND')
    db = get_db()
    row = db.execute('SELECT * FROM svs_plans WHERE share_token_hash = ?', (plan_mod.token_hash(token),)).fetchone()
    if not row or not row['share_token'] or not hmac.compare_digest(row['share_token'], token):
        raise not_found('This plan link is not valid (it may have been replaced or turned off)', code='PLAN_NOT_FOUND')
    rnd = get_db().execute('SELECT * FROM rounds WHERE id = ?', (row['round_id'],)).fetchone()
    plan = plan_mod.stored_plan(row)
    settings, _gen, by_slug = _plan_context(rnd)
    names = plan_mod.people(db, plan_mod.plan_fids(plan), rnd['id'])
    from core.heroes import library
    body = {'round_name': rnd['name'], 'revision': row['revision'], 'updated_at': row['updated_at'],
            'attribution': library()['attribution']}
    body.update(plan_mod.resolve_view(plan, settings, names, by_slug, public=True))
    return jsonify(body)
