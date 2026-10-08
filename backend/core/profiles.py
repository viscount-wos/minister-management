"""Player profiles: one per FID, persistent across events and rounds.

FID rules (docs/SPEC.md "FIDs"):
- FIDs are strings end to end (never parsed as numbers): leading zeros are significant and
  FIDs above 2^53 survive JSON/JS untouched.
- Lookup (``find_profile``) matches the FID exactly first, then with surrounding whitespace
  trimmed. Every read and write route uses it, so a legacy row stays reachable.
- A NEW profile needs a canonical FID: digits only, 1-20 chars, after trimming. An EXISTING
  profile keeps whatever FID it has (legacy v1.4 FIDs may be odd) and is always updated by id,
  so a resubmit never forks a second profile.
"""
import json

from flask import Blueprint, jsonify, request

from core.auth import require_admin
from core.db import get_db
from core.errors import ApiError, get_json_body, not_found, validation_error
from core.validation import (now_iso, validate_fid, validate_json_blob, validate_number, validate_str)

bp = Blueprint('profiles', __name__)

# Fields a player (or admin) may write. Legacy avatar/stove columns are read-only.
EDITABLE_FIELDS = ('game_name', 'alliance', 'timezone', 'furnace_level', 'power', 'troops')
# What anyone holding an FID may read (M6: no internal id, no timestamps).
PUBLIC_FIELDS = ('fid', 'game_name', 'alliance', 'timezone', 'furnace_level', 'power', 'troops',
                 'avatar_image', 'stove_lv', 'stove_lv_content')
ADMIN_FIELDS = PUBLIC_FIELDS + ('created_at', 'updated_at')
LEGACY_GRANDFATHERED = ('game_name', 'alliance', 'timezone')  # unchanged over-long legacy values are kept


def profile_to_json(row):
    """Full profile (admin responses and internal use): public fields + timestamps + internal id."""
    if row is None:
        return None
    d = dict(row)
    if d.get('troops'):
        try:
            d['troops'] = json.loads(d['troops'])
        except (TypeError, ValueError):
            d['troops'] = None
    out = {k: d.get(k) for k in ADMIN_FIELDS}
    out['id'] = d['id']
    return out


def public_profile(profile_json):
    """The public shape of a profile (GET/PUT /api/profile/<fid>, application PUT responses)."""
    if profile_json is None:
        return None
    return {k: profile_json.get(k) for k in PUBLIC_FIELDS}


def snapshot(profile_json):
    """Profile copy stored on an application at submit time."""
    return {k: profile_json.get(k) for k in PUBLIC_FIELDS}


def find_profile(fid):
    """Exact FID match first, then the whitespace-trimmed FID. None if neither exists."""
    db = get_db()
    raw = '' if fid is None else str(fid)
    row = db.execute('SELECT * FROM profiles WHERE fid = ?', (raw,)).fetchone()
    if row is None and raw.strip() != raw:
        row = db.execute('SELECT * FROM profiles WHERE fid = ?', (raw.strip(),)).fetchone()
    return row


# Backwards-compatible name used by the event modules.
get_profile_row = find_profile


def resolve_fid_for_write(fid):
    """(fid_to_store, existing_row). Existing profiles keep their stored FID (legacy-safe);
    a brand-new FID must be canonical (digits only)."""
    row = find_profile(fid)
    if row is not None:
        return row['fid'], row
    return validate_fid(fid), None


def get_profile_by_id(pid):
    return get_db().execute('SELECT * FROM profiles WHERE id = ?', (pid,)).fetchone()


def _unchanged_legacy(key, value, existing):
    """True when ``value`` re-sends the stored (possibly over-long legacy) value of ``key`` unchanged."""
    if existing is None or not isinstance(value, str):
        return False
    stored = existing[key]
    if not isinstance(stored, str) or not stored.strip():
        return False
    if key == 'alliance':
        return value.strip().casefold() == stored.strip().casefold()
    return value.strip() == stored.strip()


def validate_profile_fields(data, field_prefix='profile.', existing=None):
    """Validate the editable profile fields present in ``data``. Returns only those present.

    ``existing``: the stored profile row, if any. A legacy value that breaks today's limits
    (e.g. the 4-character v1.4 alliance 'love') is accepted when re-sent UNCHANGED and kept exactly
    as stored, so legacy players can resubmit; any new value must meet the limits.
    """
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise validation_error('profile must be an object', field_prefix.rstrip('.'))
    out = {}
    limits = {'game_name': (64, False), 'alliance': (3, True), 'timezone': (64, False)}
    for key in LEGACY_GRANDFATHERED:
        if key not in data:
            continue
        max_len, upper = limits[key]
        try:
            out[key] = validate_str(data[key], field_prefix + key, max_len, upper=upper)
        except ApiError:
            if not _unchanged_legacy(key, data[key], existing):
                raise
            out[key] = existing[key]
    if 'furnace_level' in data:
        out['furnace_level'] = validate_number(data['furnace_level'], field_prefix + 'furnace_level',
                                               minimum=1, maximum=100, integer=True, nullable=True)
    if 'power' in data:
        out['power'] = validate_number(data['power'], field_prefix + 'power', maximum=10 ** 13,
                                       integer=True, nullable=True)
    if 'troops' in data:
        out['troops'] = validate_json_blob(data['troops'], field_prefix + 'troops')
    return out


_LOOKUP = object()


def upsert_profile(fid, fields, required=('game_name',), field_prefix='profile.', commit=True, existing=_LOOKUP):
    """Create or partially update a profile. ``fields`` must already be validated.

    ``existing``: the stored row if the caller already resolved it (updates then go by id, so a
    legacy FID can never fork a duplicate), ``None`` to force a create, or omitted to look it up.
    Returns (profile_json, created).
    """
    db = get_db()
    if existing is _LOOKUP:
        existing = find_profile(fid)
    merged = {k: (existing[k] if existing else None) for k in EDITABLE_FIELDS}
    if existing and merged.get('troops'):
        try:
            merged['troops'] = json.loads(merged['troops'])
        except (TypeError, ValueError):
            merged['troops'] = None
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
        pid = existing['id']
        created = False
    else:
        cur = db.execute('INSERT INTO profiles (fid, game_name, alliance, timezone, furnace_level, power, troops, '
                         'created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                         (fid, merged['game_name'], merged['alliance'], merged['timezone'], merged['furnace_level'],
                          merged['power'], troops, now, now))
        pid = cur.lastrowid
        created = True
    if commit:
        db.commit()
    return profile_to_json(get_profile_by_id(pid)), created


# ---------------------------------------------------------------- routes

@bp.route('/api/profile/<fid>', methods=['GET'])
def public_get_profile(fid):
    row = find_profile(fid)
    if not row:
        raise not_found('Profile not found')
    return jsonify(public_profile(profile_to_json(row)))


def _check_body_fid(data, url_fid, stored_fid, field):
    if data.get('fid') is None:
        return
    body = str(data['fid']).strip()
    if body not in (str(url_fid).strip(), str(stored_fid).strip()):
        raise validation_error('fid does not match the FID in the URL', field)


@bp.route('/api/profile/<fid>', methods=['PUT'])
def public_put_profile(fid):
    """Players have no login: anyone with the FID may update its profile (same trust model as
    applications). Body: partial profile fields; game_name required when creating."""
    data = get_json_body()
    store_fid, existing = resolve_fid_for_write(fid)
    _check_body_fid(data, fid, store_fid, 'fid')
    fields = validate_profile_fields(data, field_prefix='', existing=existing)
    profile, created = upsert_profile(store_fid, fields, field_prefix='', existing=existing)
    return jsonify({'profile': public_profile(profile), 'created': created}), (201 if created else 200)


def _like_escape(text):
    return text.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


@bp.route('/api/admin/profiles', methods=['GET'])
@require_admin
def admin_list_profiles():
    sql = ('SELECT p.*, (SELECT COUNT(*) FROM applications a WHERE a.player_id = p.id) AS application_count '
           'FROM profiles p WHERE 1=1')
    params = []
    alliance = request.args.get('alliance', '').strip()
    if alliance:
        sql += ' AND casefold(trim(p.alliance)) = ?'
        params.append(alliance.casefold())
    q = request.args.get('q', '').strip()
    if q:
        like = f'%{_like_escape(q.casefold())}%'
        sql += " AND (casefold(p.fid) LIKE ? ESCAPE '\\' OR casefold(p.game_name) LIKE ? ESCAPE '\\')"
        params += [like, like]
    sql += ' ORDER BY casefold(p.game_name), p.id'
    out = []
    for row in get_db().execute(sql, params).fetchall():
        p = profile_to_json(row)
        p['application_count'] = row['application_count']
        out.append(p)
    return jsonify({'profiles': out})


@bp.route('/api/admin/profiles/<fid>', methods=['GET'])
@require_admin
def admin_get_profile(fid):
    row = find_profile(fid)
    if not row:
        raise not_found('Profile not found')
    return jsonify(profile_to_json(row))


@bp.route('/api/admin/profiles/<fid>', methods=['PUT'])
@require_admin
def admin_put_profile(fid):
    data = get_json_body()
    store_fid, existing = resolve_fid_for_write(fid)  # creating: FID must be canonical
    fields = validate_profile_fields(data, field_prefix='', existing=existing)
    profile, created = upsert_profile(store_fid, fields, field_prefix='', existing=existing)
    return jsonify({'profile': profile, 'created': created}), (201 if created else 200)


@bp.route('/api/admin/profiles/<fid>', methods=['DELETE'])
@require_admin
def admin_delete_profile(fid):
    db = get_db()
    row = find_profile(fid)
    if not row:
        raise not_found('Profile not found')
    apps = db.execute('SELECT COUNT(*) AS n FROM applications WHERE player_id = ?', (row['id'],)).fetchone()['n']
    db.execute('DELETE FROM ministry_assignments WHERE player_id = ?', (row['id'],))
    db.execute('DELETE FROM applications WHERE player_id = ?', (row['id'],))
    db.execute('DELETE FROM profiles WHERE id = ?', (row['id'],))
    db.commit()
    return jsonify({'deleted': True, 'fid': row['fid'], 'applications_deleted': apps})
