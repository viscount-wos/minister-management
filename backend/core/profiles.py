"""Player profiles: one per FID, persistent across events and rounds."""
import json

from flask import Blueprint, jsonify, request

from core.auth import require_admin
from core.db import get_db
from core.errors import get_json_body, not_found, validation_error
from core.validation import (now_iso, validate_fid, validate_json_blob, validate_number, validate_str)

bp = Blueprint('profiles', __name__)

# Fields a player (or admin) may write. Legacy avatar/stove columns are read-only.
EDITABLE_FIELDS = ('game_name', 'alliance', 'timezone', 'furnace_level', 'power', 'troops')
PUBLIC_FIELDS = ('fid', 'game_name', 'alliance', 'timezone', 'furnace_level', 'power', 'troops',
                 'avatar_image', 'stove_lv', 'stove_lv_content', 'created_at', 'updated_at')


def profile_to_json(row):
    if row is None:
        return None
    d = dict(row)
    if d.get('troops'):
        try:
            d['troops'] = json.loads(d['troops'])
        except (TypeError, ValueError):
            d['troops'] = None
    out = {k: d.get(k) for k in PUBLIC_FIELDS}
    out['id'] = d['id']
    return out


def snapshot(profile_json):
    """Profile copy stored on an application at submit time."""
    return {k: profile_json.get(k) for k in PUBLIC_FIELDS if k not in ('created_at', 'updated_at')}


def get_profile_row(fid):
    return get_db().execute('SELECT * FROM profiles WHERE fid = ?', (str(fid).strip(),)).fetchone()


def get_profile_by_id(pid):
    return get_db().execute('SELECT * FROM profiles WHERE id = ?', (pid,)).fetchone()


def validate_profile_fields(data, field_prefix='profile.'):
    """Validate the editable profile fields present in ``data``. Returns only those present."""
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise validation_error('profile must be an object', field_prefix.rstrip('.'))
    out = {}
    if 'game_name' in data:
        out['game_name'] = validate_str(data['game_name'], field_prefix + 'game_name', 64)
    if 'alliance' in data:
        out['alliance'] = validate_str(data['alliance'], field_prefix + 'alliance', 3, upper=True)
    if 'timezone' in data:
        out['timezone'] = validate_str(data['timezone'], field_prefix + 'timezone', 64)
    if 'furnace_level' in data:
        out['furnace_level'] = validate_number(data['furnace_level'], field_prefix + 'furnace_level',
                                               minimum=1, maximum=100, integer=True, nullable=True)
    if 'power' in data:
        out['power'] = validate_number(data['power'], field_prefix + 'power', maximum=10 ** 13,
                                       integer=True, nullable=True)
    if 'troops' in data:
        out['troops'] = validate_json_blob(data['troops'], field_prefix + 'troops')
    return out


def upsert_profile(fid, fields, required=('game_name',), field_prefix='profile.', commit=True):
    """Create or partially update a profile. ``fields`` must already be validated.

    Returns (profile_json, created).
    """
    db = get_db()
    existing = get_profile_row(fid)
    merged = {k: (existing[k] if existing else None) for k in EDITABLE_FIELDS}
    if existing and merged.get('troops'):
        merged['troops'] = json.loads(merged['troops'])
    merged.update(fields)
    for req in required:
        if merged.get(req) in (None, ''):
            raise validation_error(f'{req} is required', field_prefix + req)
    troops = json.dumps(merged['troops']) if merged.get('troops') is not None else None
    now = now_iso()
    if existing:
        db.execute('UPDATE profiles SET game_name=?, alliance=?, timezone=?, furnace_level=?, power=?, troops=?, '
                   'updated_at=? WHERE id=?',
                   (merged['game_name'], merged['alliance'], merged['timezone'], merged['furnace_level'],
                    merged['power'], troops, now, existing['id']))
        created = False
    else:
        db.execute('INSERT INTO profiles (fid, game_name, alliance, timezone, furnace_level, power, troops, '
                   'created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (fid, merged['game_name'], merged['alliance'], merged['timezone'], merged['furnace_level'],
                    merged['power'], troops, now, now))
        created = True
    if commit:
        db.commit()
    return profile_to_json(get_profile_row(fid)), created


# ---------------------------------------------------------------- routes

@bp.route('/api/profile/<fid>', methods=['GET'])
def public_get_profile(fid):
    row = get_profile_row(fid)
    if not row:
        raise not_found('Profile not found')
    return jsonify(profile_to_json(row))


@bp.route('/api/profile/<fid>', methods=['PUT'])
def public_put_profile(fid):
    """Players have no login: anyone with the FID may update its profile (same trust model as
    applications). Body: partial profile fields; game_name required when creating."""
    fid = validate_fid(fid)
    data = get_json_body()
    if data.get('fid') is not None and str(data['fid']).strip() != fid:
        raise validation_error('fid does not match the FID in the URL', 'fid')
    profile, created = upsert_profile(fid, validate_profile_fields(data, field_prefix=''), field_prefix='')
    return jsonify({'profile': profile, 'created': created}), (201 if created else 200)


@bp.route('/api/admin/profiles', methods=['GET'])
@require_admin
def admin_list_profiles():
    sql = ('SELECT p.*, (SELECT COUNT(*) FROM applications a WHERE a.player_id = p.id) AS application_count '
           'FROM profiles p WHERE 1=1')
    params = []
    alliance = request.args.get('alliance', '').strip()
    if alliance:
        sql += ' AND UPPER(p.alliance) = ?'
        params.append(alliance.upper())
    q = request.args.get('q', '').strip()
    if q:
        sql += ' AND (p.fid LIKE ? OR LOWER(p.game_name) LIKE ?)'
        params += [f'%{q}%', f'%{q.lower()}%']
    sql += ' ORDER BY LOWER(p.game_name), p.id'
    out = []
    for row in get_db().execute(sql, params).fetchall():
        p = profile_to_json(row)
        p['application_count'] = row['application_count']
        out.append(p)
    return jsonify({'profiles': out})


@bp.route('/api/admin/profiles/<fid>', methods=['GET'])
@require_admin
def admin_get_profile(fid):
    row = get_profile_row(fid)
    if not row:
        raise not_found('Profile not found')
    return jsonify(profile_to_json(row))


@bp.route('/api/admin/profiles/<fid>', methods=['PUT'])
@require_admin
def admin_put_profile(fid):
    data = get_json_body()
    if get_profile_row(fid) is None:
        fid = validate_fid(fid)  # creating: enforce FID format (legacy FIDs may be odd)
    fields = validate_profile_fields(data, field_prefix='')
    profile, created = upsert_profile(str(fid).strip(), fields, field_prefix='')
    return jsonify({'profile': profile, 'created': created}), (201 if created else 200)


@bp.route('/api/admin/profiles/<fid>', methods=['DELETE'])
@require_admin
def admin_delete_profile(fid):
    db = get_db()
    row = get_profile_row(fid)
    if not row:
        raise not_found('Profile not found')
    apps = db.execute('SELECT COUNT(*) AS n FROM applications WHERE player_id = ?', (row['id'],)).fetchone()['n']
    db.execute('DELETE FROM ministry_assignments WHERE player_id = ?', (row['id'],))
    db.execute('DELETE FROM applications WHERE player_id = ?', (row['id'],))
    db.execute('DELETE FROM profiles WHERE id = ?', (row['id'],))
    db.commit()
    return jsonify({'deleted': True, 'fid': row['fid'], 'applications_deleted': apps})
