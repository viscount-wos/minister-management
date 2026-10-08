"""SQLite connection, schema and versioned migrations.

Rules carried over from v1.4 (see claude.md):
- ``PRAGMA journal_mode=DELETE``: WAL sidecar files break on GCS FUSE.
- one gunicorn worker; every request gets its own connection via flask.g.

Migrations are numbered and recorded in ``schema_version``. Migration code is
deliberately self-contained (it does not import event logic), so a migration
keeps meaning the same thing even when the app code evolves.

Migration 1 creates the v2 schema. If the file holds a v1.4 database (a
``players`` table with ``construction_speedups_days``), the file is first
backed up to ``<db>.pre-v2-<timestamp>.bak``, the old tables are renamed to
``legacy_*`` and their data is imported into one open ministry round. The whole
migration runs in a single transaction, so a crash leaves the DB untouched.
"""
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone

from flask import current_app, g

logger = logging.getLogger(__name__)

IMPORTED_ROUND_NAME = 'Imported from previous system'
LEGACY_TABLES = ('players', 'time_preferences', 'assignments', 'settings', 'admin_users')
# v1.4 global settings that become per-round ministry settings
LEGACY_ROUND_SETTING_KEYS = ('research_day', 'show_fire_crystals', 'time_slot_scheme',
                             'published_days', 'application_closing_time')
WEEKDAY_ORDER = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


# --------------------------------------------------------------------------
# connections
# --------------------------------------------------------------------------

def connect(db_path):
    d = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(d, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=DELETE')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def get_db():
    if 'db' not in g:
        g.db = connect(current_app.config['DATABASE_PATH'])
    return g.db


def close_db(exc=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
    migrate(app.config['DATABASE_PATH'])


def row_to_dict(row):
    return dict(row) if row is not None else None


# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------

SCHEMA_V2 = [
    '''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''',
    '''CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fid TEXT UNIQUE NOT NULL,
        game_name TEXT NOT NULL,
        alliance TEXT,
        timezone TEXT,
        furnace_level INTEGER,
        power INTEGER,
        troops TEXT,
        avatar_image TEXT,
        stove_lv INTEGER,
        stove_lv_content TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )''',
    '''CREATE TABLE IF NOT EXISTS rounds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event TEXT NOT NULL,
        name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'open', 'closed')),
        closing_time TEXT,
        settings TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )''',
    # At most ONE open round per event, enforced by the database itself.
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_rounds_one_open ON rounds(event) WHERE status = 'open'",
    'CREATE INDEX IF NOT EXISTS idx_rounds_event ON rounds(event)',
    '''CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
        player_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
        answers TEXT NOT NULL DEFAULT '{}',
        profile_snapshot TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (round_id, player_id)
    )''',
    'CREATE INDEX IF NOT EXISTS idx_applications_player ON applications(player_id)',
    '''CREATE TABLE IF NOT EXISTS ministry_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
        player_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
        day TEXT NOT NULL,
        time_slot TEXT NOT NULL,
        position INTEGER NOT NULL DEFAULT 0,
        is_assigned INTEGER NOT NULL DEFAULT 1,
        is_sticky INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        UNIQUE (round_id, day, time_slot, position)
    )''',
    'CREATE INDEX IF NOT EXISTS idx_ministry_assignments_round_day ON ministry_assignments(round_id, day)',
]


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _table_exists(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _columns(conn, table):
    return {r['name'] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()}


def current_version(conn):
    if not _table_exists(conn, 'schema_version'):
        return 0
    row = conn.execute('SELECT MAX(version) AS v FROM schema_version').fetchone()
    return row['v'] or 0


def is_legacy_v14(conn):
    return _table_exists(conn, 'players') and 'construction_speedups_days' in _columns(conn, 'players')


def backup_file(conn, db_path):
    """Consistent copy of the DB file (sqlite backup API also captures a stray -wal)."""
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    path = f'{db_path}.pre-v2-{ts}.bak'
    n = 1
    while os.path.exists(path):
        path = f'{db_path}.pre-v2-{ts}-{n}.bak'
        n += 1
    dest = sqlite3.connect(path)
    try:
        conn.backup(dest)
    finally:
        dest.close()
    logger.info('Backed up v1.4 database to %s', path)
    return path


# --------------------------------------------------------------------------
# migration 1: v2 schema (+ v1.4 import)
# --------------------------------------------------------------------------

def _legacy_ts(value):
    if not value:
        return _now()
    try:
        dt = datetime.fromisoformat(str(value).strip().replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    except ValueError:
        return str(value)


def _num(value, integer=False):
    if value is None or value == '':
        return 0
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0
    if integer:
        return int(f)
    return f


def _import_v14(conn):
    """Copy data out of legacy_* tables into the v2 schema. Returns a stats dict."""
    now = _now()

    # ---- settings
    legacy_settings = {}
    if _table_exists(conn, 'legacy_settings'):
        legacy_settings = {r['key']: r['value'] for r in conn.execute('SELECT key, value FROM legacy_settings')}
    for key, value in legacy_settings.items():
        if key not in LEGACY_ROUND_SETTING_KEYS:
            conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))

    legacy_slots = []
    if _table_exists(conn, 'legacy_assignments'):
        legacy_slots = [r['time_slot'] for r in conn.execute('SELECT time_slot FROM legacy_assignments')]

    research_day = (legacy_settings.get('research_day') or 'tuesday').lower()
    if research_day not in ('tuesday', 'friday'):
        research_day = 'tuesday'
    scheme = legacy_settings.get('time_slot_scheme')
    if scheme not in ('exact_alignment', 'max_slots'):
        # No stored scheme: v1.4 would pin max_slots at its next start if assignments
        # existed, but a running v1.4 used exact_alignment. Infer from the slots
        # actually stored (:20/:50 only exist on the max_slots grid).
        on_max_grid = any(str(s).endswith((':20', ':50', ':50+')) for s in legacy_slots)
        scheme = 'max_slots' if on_max_grid else 'exact_alignment'
    published = [d for d in (legacy_settings.get('published_days') or '').split(',') if d.strip()]
    published = sorted({d.strip().lower() for d in published},
                       key=lambda d: (WEEKDAY_ORDER.index(d) if d in WEEKDAY_ORDER else 99, d))
    round_settings = {
        'research_day': research_day,
        'show_fire_crystals': legacy_settings.get('show_fire_crystals', 'false') == 'true',
        'time_slot_scheme': scheme,
        'published_days': published,
    }
    closing_raw = legacy_settings.get('application_closing_time') or ''
    closing = None
    if closing_raw:
        try:
            dt = datetime.fromisoformat(closing_raw.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            closing = dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        except ValueError:
            logger.warning('Ignoring unparseable legacy closing time %r', closing_raw)
            round_settings['legacy_closing_time_raw'] = closing_raw

    cur = conn.execute(
        'INSERT INTO rounds (event, name, status, closing_time, settings, created_at, updated_at) '
        "VALUES ('ministry', ?, 'open', ?, ?, ?, ?)",
        (IMPORTED_ROUND_NAME, closing, json.dumps(round_settings), now, now))
    round_id = cur.lastrowid

    # ---- players -> profiles + applications
    pcols = _columns(conn, 'legacy_players')

    def col(row, name):
        return row[name] if name in pcols else None

    prefs_by_player = {}
    if _table_exists(conn, 'legacy_time_preferences'):
        tcols = _columns(conn, 'legacy_time_preferences')
        has_day_type = 'day_type' in tcols
        q = 'SELECT player_id, time_slot' + (', day_type' if has_day_type else '') + \
            ' FROM legacy_time_preferences ORDER BY id'
        for r in conn.execute(q):
            types = [r['day_type']] if has_day_type else ['construction', 'research', 'troop']
            bucket = prefs_by_player.setdefault(r['player_id'], {'construction': [], 'research': [], 'troop': []})
            for t in types:
                if t in bucket and r['time_slot'] not in bucket[t]:
                    bucket[t].append(r['time_slot'])

    players = conn.execute('SELECT * FROM legacy_players ORDER BY id').fetchall()
    for p in players:
        created = _legacy_ts(col(p, 'created_at'))
        updated = _legacy_ts(col(p, 'updated_at')) if col(p, 'updated_at') else created
        profile = {
            'fid': p['fid'],
            'game_name': p['game_name'],
            'alliance': col(p, 'alliance'),
            'timezone': col(p, 'timezone'),
            'furnace_level': None,
            'power': None,
            'troops': None,
            'avatar_image': col(p, 'avatar_image'),
            'stove_lv': col(p, 'stove_lv'),
            'stove_lv_content': col(p, 'stove_lv_content'),
        }
        conn.execute(
            'INSERT INTO profiles (id, fid, game_name, alliance, timezone, furnace_level, power, troops, '
            'avatar_image, stove_lv, stove_lv_content, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?, ?)',
            (p['id'], profile['fid'], profile['game_name'], profile['alliance'], profile['timezone'],
             profile['avatar_image'], profile['stove_lv'], profile['stove_lv_content'], created, updated))
        answers = {
            'construction_speedups_days': _num(col(p, 'construction_speedups_days')),
            'research_speedups_days': _num(col(p, 'research_speedups_days')),
            'troop_training_speedups_days': _num(col(p, 'troop_training_speedups_days')),
            'general_speedups_days': _num(col(p, 'general_speedups_days')),
            'fire_crystals': _num(col(p, 'fire_crystals'), integer=True),
            'refined_fire_crystals': _num(col(p, 'refined_fire_crystals'), integer=True),
            'fire_crystal_shards': _num(col(p, 'fire_crystal_shards'), integer=True),
            'time_slots_by_day': prefs_by_player.get(p['id'], {'construction': [], 'research': [], 'troop': []}),
        }
        conn.execute(
            'INSERT INTO applications (round_id, player_id, answers, profile_snapshot, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (round_id, p['id'], json.dumps(answers), json.dumps(profile), created, updated))

    # ---- assignments (orphans whose player no longer exists stay in legacy_assignments only)
    imported_assignments = skipped = 0
    if _table_exists(conn, 'legacy_assignments'):
        acols = _columns(conn, 'legacy_assignments')
        player_ids = {p['id'] for p in players}
        for a in conn.execute('SELECT * FROM legacy_assignments ORDER BY id'):
            if a['player_id'] not in player_ids:
                skipped += 1
                continue
            conn.execute(
                'INSERT INTO ministry_assignments (round_id, player_id, day, time_slot, position, '
                'is_assigned, is_sticky, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (round_id, a['player_id'], str(a['day']).lower(), a['time_slot'],
                 a['position'] if 'position' in acols and a['position'] is not None else 0,
                 1 if ('is_assigned' not in acols or a['is_assigned'] is None or a['is_assigned']) else 0,
                 1 if ('is_sticky' in acols and a['is_sticky']) else 0,
                 _legacy_ts(a['created_at']) if 'created_at' in acols else now))
            imported_assignments += 1

    return {'round_id': round_id, 'players': len(players), 'assignments': imported_assignments,
            'orphan_assignments_skipped': skipped}


def _migration_1(conn, db_path):
    stats = {}
    if is_legacy_v14(conn):
        stats['backup'] = backup_file(conn, db_path)
        conn.execute('BEGIN')
        for t in LEGACY_TABLES:
            if _table_exists(conn, t):
                conn.execute(f'ALTER TABLE {t} RENAME TO legacy_{t}')
        for stmt in SCHEMA_V2:
            conn.execute(stmt)
        stats.update(_import_v14(conn))
        desc = 'v2 schema + import from v1.4'
    else:
        conn.execute('BEGIN')
        for stmt in SCHEMA_V2:
            conn.execute(stmt)
        desc = 'v2 schema'
    conn.execute('INSERT INTO schema_version (version, description, applied_at) VALUES (1, ?, ?)', (desc, _now()))
    conn.execute('COMMIT')
    return stats


# (version, function). Append new migrations; never edit applied ones.
MIGRATIONS = [
    (1, _migration_1),
]


def migrate(db_path):
    """Bring the DB at db_path up to the latest schema version. Idempotent."""
    conn = connect(db_path)
    conn.isolation_level = None  # explicit BEGIN/COMMIT so DDL is transactional
    results = {}
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS schema_version ('
                     'version INTEGER PRIMARY KEY, description TEXT, applied_at TEXT NOT NULL)')
        version = current_version(conn)
        for number, fn in MIGRATIONS:
            if number <= version:
                continue
            try:
                # FK enforcement off during table renames/bulk import (legacy data has no FK guarantees).
                # PRAGMA foreign_keys cannot change inside a transaction, so it is toggled here.
                conn.execute('PRAGMA foreign_keys=OFF')
                results[number] = fn(conn, db_path)
                conn.execute('PRAGMA foreign_keys=ON')
                logger.info('Applied migration %s: %s', number, results[number])
            except Exception:
                if conn.in_transaction:
                    conn.execute('ROLLBACK')
                raise
    finally:
        conn.close()
    return results
