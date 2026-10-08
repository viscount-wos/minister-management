"""SQLite connection, schema and versioned migrations.

Rules carried over from v1.4 (see claude.md):
- ``PRAGMA journal_mode=DELETE``: WAL sidecar files break on GCS FUSE.
- one gunicorn worker; every request gets its own connection via flask.g.

Migrations are numbered and recorded in ``schema_version``. Migration code is
deliberately self-contained (it does not import event logic), so a migration
keeps meaning the same thing even when the app code evolves.

Migration 1 creates the v2 schema. Importing a v1.4 database (a ``players``
TABLE with ``construction_speedups_days``) is EXPLICIT: a normal boot on such a
file raises ``LegacyDatabaseError`` and refuses to start. Run the one-off
import with ``python -m core.migrate`` (or boot once with ``MIGRATE_V14=1``).
The import backs the file up to ``<db>.pre-v2-<timestamp>.bak``, renames the old
tables to ``legacy_*`` and imports their data into one open ministry round.

Migration 2 installs guards so a stray v1.4 instance fails loudly instead of
writing to ghost tables: VIEWs named like the v1.4 tables (``players``,
``time_preferences``, ``assignments``, ``admin_users``; v1.4's ``CREATE TABLE IF
NOT EXISTS`` becomes a no-op and every write raises "cannot modify ... because it
is a view"), and triggers that reject the v1.4 global round-setting keys in the
shared ``settings`` table.

``migrate()`` takes ``BEGIN IMMEDIATE`` (the write lock) BEFORE reading the
schema version or detecting a legacy file, so two processes can never both
decide to migrate; every pending migration runs in that one transaction, so a
crash leaves the DB untouched. The backup is written to ``*.bak.partial`` and
only renamed to ``*.bak`` after COMMIT (one backup per successful import;
failed attempts clean up after themselves).
"""
import glob
import json
import logging
import os
import sqlite3
from collections import Counter
from datetime import datetime, timezone

from flask import current_app, g

logger = logging.getLogger(__name__)

IMPORTED_ROUND_NAME = 'Imported from previous system'
LEGACY_TABLES = ('players', 'time_preferences', 'assignments', 'settings', 'admin_users')
# v1.4 global settings that become per-round ministry settings
LEGACY_ROUND_SETTING_KEYS = ('research_day', 'show_fire_crystals', 'time_slot_scheme',
                             'published_days', 'application_closing_time')
WEEKDAY_ORDER = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
CRYSTAL_KEYS = ('fire_crystals', 'refined_fire_crystals', 'fire_crystal_shards')
SPEEDUP_KEYS = ('construction_speedups_days', 'research_speedups_days', 'troop_training_speedups_days',
                'general_speedups_days')
MIGRATION_LOCK_TIMEOUT = 120  # seconds a second process waits for the migration write lock

# Columns of the v1.4 tables, used for the guard views (migration 2).
V14_GUARD_VIEWS = {
    'players': ('id', 'fid', 'game_name', 'construction_speedups_days', 'research_speedups_days',
                'troop_training_speedups_days', 'general_speedups_days', 'fire_crystals', 'refined_fire_crystals',
                'fire_crystal_shards', 'created_at', 'updated_at', 'avatar_image', 'stove_lv', 'stove_lv_content',
                'alliance', 'timezone'),
    'time_preferences': ('id', 'player_id', 'time_slot', 'day_type'),
    'assignments': ('id', 'player_id', 'day', 'time_slot', 'position', 'is_assigned', 'created_at', 'is_sticky'),
    'admin_users': ('id', 'username', 'password_hash', 'role', 'created_at'),
}
V14_GUARD_MESSAGE = ('wos-events v2 owns this database: v1.4 is retired and must not run against it '
                     '(see docs/DEPLOY-CUTOVER.md)')


class LegacyDatabaseError(RuntimeError):
    """The DB file needs an explicit, operator-run step (v1.4 import) before the app may start."""


# --------------------------------------------------------------------------
# connections
# --------------------------------------------------------------------------

def _casefold(value):
    return value.casefold() if isinstance(value, str) else value


def connect(db_path, timeout=5.0):
    d = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(d, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=DELETE')
    conn.execute('PRAGMA foreign_keys=ON')
    # Unicode-aware case folding for name/alliance comparisons (SQLite UPPER/LOWER are ASCII-only).
    conn.create_function('casefold', 1, _casefold, deterministic=True)
    return conn


def begin_immediate(db):
    """Take the write lock now (read-modify-write sections). No-op if a transaction is already open."""
    if not db.in_transaction:
        db.execute('BEGIN IMMEDIATE')


def get_db():
    if 'db' not in g:
        g.db = connect(current_app.config['DATABASE_PATH'], timeout=current_app.config.get('DB_BUSY_TIMEOUT', 5.0))
    return g.db


def close_db(exc=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
    migrate(app.config['DATABASE_PATH'], allow_v14=bool(app.config.get('MIGRATE_V14')))


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
    """True only for a real TABLE (the v1.4 guard objects are views)."""
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _view_exists(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='view' AND name=?", (name,)).fetchone() is not None


def _columns(conn, table):
    return {r['name'] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()}


def current_version(conn):
    if not _table_exists(conn, 'schema_version'):
        return 0
    row = conn.execute('SELECT MAX(version) AS v FROM schema_version').fetchone()
    return row['v'] or 0


def is_legacy_v14(conn):
    return _table_exists(conn, 'players') and 'construction_speedups_days' in _columns(conn, 'players')


PARTIAL_SUFFIX = '.partial'


def _remove_stale_partial_backups(db_path):
    """Called while holding the migration write lock, so no other migrator is mid-backup."""
    for stale in glob.glob(glob.escape(db_path) + '.pre-v2-*.bak' + PARTIAL_SUFFIX):
        try:
            os.remove(stale)
            logger.warning('Removed stale partial backup %s', stale)
        except OSError:
            pass


def backup_file(db_path):
    """Consistent copy of the (still untouched) v1.4 DB to ``<db>.pre-v2-<ts>.bak.partial``.

    Uses a SEPARATE read connection: the migrating connection already holds the
    RESERVED lock, which still admits readers in rollback-journal mode. Returns
    (partial_path, final_path); the caller renames after COMMIT.
    """
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    final = f'{db_path}.pre-v2-{ts}.bak'
    n = 1
    while os.path.exists(final) or os.path.exists(final + PARTIAL_SUFFIX):
        final = f'{db_path}.pre-v2-{ts}-{n}.bak'
        n += 1
    partial = final + PARTIAL_SUFFIX
    src = sqlite3.connect(db_path, timeout=MIGRATION_LOCK_TIMEOUT)
    dest = sqlite3.connect(partial)
    try:
        src.backup(dest)
    finally:
        dest.close()
        src.close()
    return partial, final


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


def _num(value):
    """Speedup days (v1.4 REAL columns) -> float. Junk -> 0."""
    if value is None or value == '':
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _exact_number(value):
    """Crystal counts EXACTLY as v1.4 stored them (no truncation).

    v1.4 declared the columns INTEGER, but its form posted parseFloat() values and
    the backend kept float() for anything with a '.', so REAL values like 12.5 exist.
    Integral values come back as int, fractional ones as float. Junk -> 0.
    """
    if value is None or value == '' or isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0
    if f != f or f in (float('inf'), float('-inf')):
        return 0
    return int(f) if f.is_integer() else f


def normalize_legacy_fids(fids):
    """Map each legacy FID to the FID it gets in v2.

    Rule (documented in docs/SPEC.md): FIDs are strings end to end. Surrounding
    whitespace is trimmed when the trimmed value is non-empty and unique among the
    legacy FIDs; otherwise the FID is kept byte-for-byte (lookups match exactly
    first, so it stays reachable). Nothing else changes: leading zeros, long
    (> 2^53) and non-digit legacy FIDs are kept as stored.
    """
    raw = [str(f) for f in fids]
    trimmed_counts = Counter(f.strip() for f in raw)
    raw_set = set(raw)
    out, trimmed, kept = {}, [], []
    for f in raw:
        t = f.strip()
        if t == f:
            out[f] = f
        elif t and trimmed_counts[t] == 1 and (t not in raw_set):
            out[f] = t
            trimmed.append((f, t))
        else:
            out[f] = f
            kept.append(f)
    return out, trimmed, kept


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
    for bucket in prefs_by_player.values():
        for t in bucket:
            bucket[t].sort()  # v1.4 read them back through its unique index, i.e. sorted

    players = conn.execute('SELECT * FROM legacy_players ORDER BY id').fetchall()
    fid_map, fids_trimmed, fids_kept = normalize_legacy_fids([p['fid'] for p in players])
    for raw, new in fids_trimmed:
        logger.warning('v1.4 import: FID %r trimmed to %r', raw, new)
    for raw in fids_kept:
        logger.warning('v1.4 import: FID %r kept as stored (trimmed value is empty or collides)', raw)
    nonstandard = [fid_map[str(p['fid'])] for p in players if not fid_map[str(p['fid'])].isdigit()]
    if nonstandard:
        logger.warning('v1.4 import: %d FID(s) are not plain digits; kept and reachable by exact lookup: %r',
                       len(nonstandard), nonstandard[:20])
    fractional = []
    for p in players:
        created = _legacy_ts(col(p, 'created_at'))
        updated = _legacy_ts(col(p, 'updated_at')) if col(p, 'updated_at') else created
        fid = fid_map[str(p['fid'])]
        profile = {
            'fid': fid,
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
        answers = {k: _num(col(p, k)) for k in SPEEDUP_KEYS}
        for k in CRYSTAL_KEYS:
            answers[k] = _exact_number(col(p, k))
        if any(isinstance(answers[k], float) for k in CRYSTAL_KEYS):
            fractional.append(fid)
        answers['time_slots_by_day'] = prefs_by_player.get(p['id'], {'construction': [], 'research': [], 'troop': []})
        conn.execute(
            'INSERT INTO applications (round_id, player_id, answers, profile_snapshot, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (round_id, p['id'], json.dumps(answers), json.dumps(profile), created, updated))
    if fractional:
        logger.warning('v1.4 import: %d player(s) have fractional crystal values, kept exactly: %r',
                       len(fractional), fractional[:20])

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
            'orphan_assignments_skipped': skipped, 'fids_trimmed': fids_trimmed, 'fids_kept_untrimmed': fids_kept,
            'nonstandard_fids': nonstandard, 'fractional_crystal_fids': fractional}


def _migration_1(conn, ctx):
    stats = {}
    if ctx['legacy']:
        for t in LEGACY_TABLES:
            if _table_exists(conn, t):
                conn.execute(f'ALTER TABLE {t} RENAME TO legacy_{t}')
        for stmt in SCHEMA_V2:
            conn.execute(stmt)
        stats.update(_import_v14(conn))
        stats['description'] = 'v2 schema + import from v1.4'
    else:
        for stmt in SCHEMA_V2:
            conn.execute(stmt)
        stats['description'] = 'v2 schema'
    return stats


# --------------------------------------------------------------------------
# migration 2: guards against a stray v1.4 instance
# --------------------------------------------------------------------------

def _migration_2(conn, ctx):
    created = []
    for name, cols in V14_GUARD_VIEWS.items():
        if _view_exists(conn, name):
            continue
        if _table_exists(conn, name):
            # A v1.4 instance ran after migration 1 and recreated its table ("ghost" table).
            n = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            if n:
                raise LegacyDatabaseError(
                    f'Table {name!r} has {n} row(s) written by a v1.4 instance AFTER the v2 import. Those '
                    f'writes are not in v2. Restore the pre-v2 backup or merge them by hand, then drop the table '
                    f'(docs/DEPLOY-CUTOVER.md).')
            conn.execute(f'DROP TABLE "{name}"')
            logger.warning('Dropped empty ghost v1.4 table %s', name)
        select = ', '.join(f'NULL AS {c}' for c in cols)
        conn.execute(f'CREATE VIEW {name} AS SELECT {select} WHERE 0')
        created.append(name)
    keys = ', '.join(f"'{k}'" for k in LEGACY_ROUND_SETTING_KEYS)
    for op in ('INSERT', 'UPDATE'):
        conn.execute(
            f'CREATE TRIGGER IF NOT EXISTS v14_guard_settings_{op.lower()} BEFORE {op} ON settings '
            f'WHEN NEW.key IN ({keys}) BEGIN SELECT RAISE(ABORT, \'{V14_GUARD_MESSAGE}\'); END')
    return {'description': 'guard views/triggers against v1.4', 'views': created}


# --------------------------------------------------------------------------
# migration 3: profiles.discord_id (phase 2, tyrant)
# --------------------------------------------------------------------------

def _migration_3(conn, ctx):
    # Shared profile field (tyrant asks for it; SVS will reuse it). Nullable, free text.
    if 'discord_id' not in _columns(conn, 'profiles'):
        conn.execute('ALTER TABLE profiles ADD COLUMN discord_id TEXT')
    return {'description': 'profiles.discord_id'}


# --------------------------------------------------------------------------
# migration 4: furnace levels become TEXT codes ('FC1'..'FC10', '1'..'30')
# --------------------------------------------------------------------------

def _furnace_code_v4(value):
    """Self-contained copy of the furnace rule at migration time: ints 1-30 -> '1'..'30', valid codes kept
    (upper-cased), anything else -> None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int):
        return str(value) if 1 <= value <= 30 else None
    if isinstance(value, str):
        s = value.strip().upper()
        if s.isdigit() and 1 <= int(s) <= 30 and not s.startswith('0'):
            return s
        if s.startswith('FC') and s[2:].isdigit() and 1 <= int(s[2:]) <= 10 and not s[2:].startswith('0'):
            return s
    return None


def _migration_4(conn, ctx):
    """profiles.furnace_level INTEGER -> TEXT. SQLite cannot change a column type, and INTEGER affinity would
    turn '30' back into 30, so the table is rebuilt (FKs are off during migrations; other tables reference
    `profiles` by name, which stays valid). Troop entries' `furnace_level` get the same conversion."""
    cols = ('id', 'fid', 'game_name', 'alliance', 'timezone', 'furnace_level', 'power', 'troops', 'avatar_image',
            'stove_lv', 'stove_lv_content', 'created_at', 'updated_at', 'discord_id')
    conn.execute('''CREATE TABLE profiles_v4 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fid TEXT UNIQUE NOT NULL,
        game_name TEXT NOT NULL,
        alliance TEXT,
        timezone TEXT,
        furnace_level TEXT,
        power INTEGER,
        troops TEXT,
        avatar_image TEXT,
        stove_lv INTEGER,
        stove_lv_content TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        discord_id TEXT
    )''')
    converted = nulled = 0
    for row in conn.execute(f'SELECT {", ".join(cols)} FROM profiles').fetchall():
        d = dict(zip(cols, tuple(row)))
        old = d['furnace_level']
        d['furnace_level'] = _furnace_code_v4(old)
        if old is not None:
            converted += d['furnace_level'] is not None
            nulled += d['furnace_level'] is None
        if d['troops']:
            try:
                troops = json.loads(d['troops'])
            except ValueError:
                troops = None
            if isinstance(troops, dict):
                for entry in troops.values():
                    if isinstance(entry, dict) and 'furnace_level' in entry:
                        entry['furnace_level'] = _furnace_code_v4(entry['furnace_level'])
                d['troops'] = json.dumps(troops)
        conn.execute(f'INSERT INTO profiles_v4 ({", ".join(cols)}) VALUES ({", ".join("?" * len(cols))})',
                     tuple(d[c] for c in cols))
    seq = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'profiles'").fetchone()
    conn.execute('DROP TABLE profiles')
    conn.execute('ALTER TABLE profiles_v4 RENAME TO profiles')
    if seq is not None:  # keep AUTOINCREMENT high-water mark (ids are never reused)
        if conn.execute("SELECT 1 FROM sqlite_sequence WHERE name = 'profiles'").fetchone():
            conn.execute("UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = 'profiles'", (seq[0],))
        else:
            conn.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('profiles', ?)", (seq[0],))
    return {'description': 'profiles.furnace_level as TEXT codes', 'converted': converted, 'nulled': nulled}


# (version, function). Append new migrations; never edit applied ones.
MIGRATIONS = [
    (1, _migration_1),
    (2, _migration_2),
    (3, _migration_3),
    (4, _migration_4),
]
LATEST_VERSION = MIGRATIONS[-1][0]

LEGACY_REFUSAL = (
    'DATABASE_PATH={path} holds a v1.4 (minister_management) database. Refusing to start: the v1.4 import is an '
    'explicit, one-off step. Stop every v1.4 instance, back up the file, then run `python -m core.migrate --db '
    '{path}` from backend/ (or boot ONE instance with MIGRATE_V14=1). See docs/DEPLOY-CUTOVER.md.')


def status(db_path):
    """Read-only summary: schema version, whether a v1.4 import is pending, row counts. Never writes."""
    if not os.path.exists(db_path):
        return {'exists': False, 'version': 0, 'legacy_v14': False, 'counts': {}}
    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        counts = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables
                  if t != 'sqlite_sequence'}
        return {'exists': True, 'version': current_version(conn), 'legacy_v14': is_legacy_v14(conn),
                'latest_version': LATEST_VERSION, 'counts': counts}
    finally:
        conn.close()


def migrate(db_path, allow_v14=False, lock_timeout=MIGRATION_LOCK_TIMEOUT):
    """Bring the DB at db_path up to the latest schema version. Idempotent.

    Raises LegacyDatabaseError on a v1.4 file unless ``allow_v14`` (explicit import).
    """
    conn = connect(db_path, timeout=lock_timeout)
    conn.isolation_level = None  # explicit BEGIN/COMMIT so DDL is transactional
    results = {}
    partial = final = None
    try:
        # FK enforcement off during table renames/bulk import (legacy data has no FK guarantees).
        # PRAGMA foreign_keys cannot change inside a transaction, so it is set first.
        conn.execute('PRAGMA foreign_keys=OFF')
        # Write lock FIRST: version and legacy detection are read under it, so a second
        # process blocks here and then sees the finished migration (re-check below).
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('CREATE TABLE IF NOT EXISTS schema_version ('
                     'version INTEGER PRIMARY KEY, description TEXT, applied_at TEXT NOT NULL)')
        version = current_version(conn)
        pending = [(n, fn) for n, fn in MIGRATIONS if n > version]
        if not pending:
            conn.execute('COMMIT')
            return results
        legacy = version == 0 and is_legacy_v14(conn)
        if legacy and not allow_v14:
            raise LegacyDatabaseError(LEGACY_REFUSAL.format(path=db_path))
        if legacy:
            _remove_stale_partial_backups(db_path)
            partial, final = backup_file(db_path)
        ctx = {'legacy': legacy, 'db_path': db_path}
        for number, fn in pending:
            stats = fn(conn, ctx) or {}
            conn.execute('INSERT INTO schema_version (version, description, applied_at) VALUES (?, ?, ?)',
                         (number, stats.pop('description', f'migration {number}'), _now()))
            results[number] = stats
        conn.execute('COMMIT')
        if partial:
            os.replace(partial, final)
            partial = None
            results.setdefault(1, {})['backup'] = final
            logger.info('Backed up v1.4 database to %s', final)
        for number, stats in results.items():
            logger.info('Applied migration %s: %s', number, stats)
    except BaseException:
        if conn.in_transaction:
            conn.execute('ROLLBACK')
        if partial and os.path.exists(partial):
            os.remove(partial)  # L1: no backup left behind by a failed attempt
        raise
    finally:
        conn.close()
    return results
