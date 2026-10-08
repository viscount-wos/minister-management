"""Migration from a v1.4 database (schema built exactly as v1.4 database.py did)."""
import glob
import json
import os
import sqlite3

import pytest

from app import create_app
from core import db as core_db
from tests.conftest import ADMIN_PW

V14_SCHEMA = [
    '''CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fid TEXT UNIQUE NOT NULL,
        game_name TEXT NOT NULL,
        construction_speedups_days REAL DEFAULT 0,
        research_speedups_days REAL DEFAULT 0,
        troop_training_speedups_days REAL DEFAULT 0,
        general_speedups_days REAL DEFAULT 0,
        fire_crystals INTEGER DEFAULT 0,
        refined_fire_crystals INTEGER DEFAULT 0,
        fire_crystal_shards INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''',
    '''CREATE TABLE IF NOT EXISTS time_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id INTEGER NOT NULL,
        time_slot TEXT NOT NULL,
        day_type TEXT NOT NULL DEFAULT 'construction',
        FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
        UNIQUE(player_id, time_slot, day_type)
    )''',
    '''CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id INTEGER NOT NULL,
        day TEXT NOT NULL,
        time_slot TEXT NOT NULL,
        position INTEGER DEFAULT 0,
        is_assigned BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
        UNIQUE(day, time_slot, position)
    )''',
    '''CREATE TABLE IF NOT EXISTS admin_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''',
    '''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''',
    'CREATE INDEX IF NOT EXISTS idx_players_fid ON players(fid)',
    'CREATE INDEX IF NOT EXISTS idx_time_prefs_player ON time_preferences(player_id)',
    'CREATE INDEX IF NOT EXISTS idx_assignments_day ON assignments(day)',
    'ALTER TABLE players ADD COLUMN avatar_image TEXT DEFAULT NULL',
    'ALTER TABLE players ADD COLUMN stove_lv INTEGER DEFAULT NULL',
    'ALTER TABLE players ADD COLUMN stove_lv_content TEXT DEFAULT NULL',
    'ALTER TABLE players ADD COLUMN alliance TEXT DEFAULT NULL',
    'ALTER TABLE players ADD COLUMN timezone TEXT DEFAULT NULL',
    'ALTER TABLE assignments ADD COLUMN is_sticky BOOLEAN DEFAULT 0',
]

# id, fid, name, c, r, t, g, fc, rfc, shards, created, avatar, stove_lv, stove_content, alliance, tz
PLAYERS = [
    (1, '1001', 'PreAugust', 3.5, 1, 20, 2, 10, 1, 4, '2026-03-02 10:00:00',
     'https://cdn/avatar1.png', 34, 'https://cdn/fc4.png', 'ABC', 'Europe/London'),
    (2, '1002', 'NoPrefs', 1, 1, 1, 0, 0, 0, 0, '2026-09-01 08:00:00', None, None, None, 'XYZ', None),
    (3, '1003', 'Shared2350', 2, 6, 5, 1, 0, 0, 0, '2026-09-02 09:00:00', None, None, None, 'abc', 'Asia/Seoul'),
    (5, '1005', 'Sticky', 0.25, 0, 99999, 0, 0, 0, 0, '2026-09-03 09:00:00', None, None, None, None, None),
    (7, '1007', 'Unassigned 名前', 0, 0, 0, 0, 0, 0, 0, '2026-09-04 09:00:00', None, None, None, 'Q', 'America/New_York'),
    (9, 'legacy-fid-9', 'OddFid', 0, 2, 0, 0, 0, 0, 3, '2026-09-05 09:00:00', 'https://cdn/a9.png', 20, None, '', ''),
]
PREFS = [
    (1, '10:00', 'construction'), (1, '11:00', 'construction'), (1, '05:00', 'research'), (1, '20:00', 'troop'),
    (3, '23:00', 'construction'), (3, '00:00', 'research'), (3, '01:00', 'research'),
    (5, '14:00', 'troop'), (5, '14:00', 'construction'),
    (7, '10:00', 'construction'),
    (9, '05:00', 'research'),
]
# player_id, day, slot, position, is_assigned, is_sticky
ASSIGNMENTS = [
    (1, 'monday', '09:50', 0, 1, 0),
    (3, 'monday', '23:50+', 0, 1, 0),   # shared 23:50 boundary (max_slots, research tuesday)
    (3, 'tuesday', '23:50', 0, 1, 0),
    (1, 'tuesday', '04:50', 0, 1, 0),
    (5, 'thursday', '14:20', 0, 1, 1),  # sticky
    (5, 'monday', '13:50', 0, 1, 1),    # sticky
    (999, 'thursday', '01:20', 0, 1, 0),  # orphan (v1.4 had no FK enforcement)
]
SETTINGS = {
    'research_day': 'tuesday',
    'show_fire_crystals': 'true',
    'time_slot_scheme': 'max_slots',
    'published_days': 'thursday,monday',
    'application_closing_time': '2026-09-14T18:00:00.000Z',
    'state_number': '2807',
}


def make_v14_db(path, settings=SETTINGS, assignments=ASSIGNMENTS):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute('PRAGMA journal_mode=DELETE')
    for stmt in V14_SCHEMA:
        conn.execute(stmt)
    for p in PLAYERS:
        conn.execute('INSERT INTO players (id, fid, game_name, construction_speedups_days, research_speedups_days, '
                     'troop_training_speedups_days, general_speedups_days, fire_crystals, refined_fire_crystals, '
                     'fire_crystal_shards, created_at, updated_at, avatar_image, stove_lv, stove_lv_content, '
                     'alliance, timezone) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                     p[:11] + (p[10],) + p[11:])
    for pr in PREFS:
        conn.execute('INSERT INTO time_preferences (player_id, time_slot, day_type) VALUES (?, ?, ?)', pr)
    for a in assignments:
        conn.execute('INSERT INTO assignments (player_id, day, time_slot, position, is_assigned, is_sticky) '
                     'VALUES (?, ?, ?, ?, ?, ?)', a)
    for k, v in settings.items():
        conn.execute('INSERT INTO settings (key, value) VALUES (?, ?)', (k, v))
    conn.commit()
    conn.close()


def build_app(db_path, migrate_v14=True):
    """migrate_v14=True = the explicit one-off import (env MIGRATE_V14=1); a normal boot passes False."""
    return create_app({'TESTING': True, 'DATABASE_PATH': db_path, 'SECRET_KEY': 'migration-test-key',
                       'ADMIN_PASSWORD': ADMIN_PW, 'MINISTER_PASSWORD': 'm', 'STATIC_DIR': '/nonexistent',
                       'MIGRATE_V14': migrate_v14})


def ro(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def dump(path):
    conn = ro(path)
    out = {}
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        out[name] = [tuple(r) for r in conn.execute(f'SELECT * FROM {name}')]
    conn.close()
    return out


@pytest.fixture
def legacy_path(tmp_path):
    p = str(tmp_path / 'data' / 'minister.db')
    make_v14_db(p)
    return p


def test_migration_preserves_everything(legacy_path):
    build_app(legacy_path)
    conn = ro(legacy_path)

    # backup made first and is the untouched v1.4 DB
    backups = glob.glob(legacy_path + '.pre-v2-*.bak')
    assert len(backups) == 1
    b = ro(backups[0])
    assert b.execute('SELECT COUNT(*) FROM players').fetchone()[0] == len(PLAYERS)
    assert b.execute('SELECT COUNT(*) FROM assignments').fetchone()[0] == len(ASSIGNMENTS)
    b.close()

    # legacy tables renamed, not dropped
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ('players', 'time_preferences', 'assignments', 'admin_users', 'settings'):
        assert f'legacy_{t}' in tables
    assert 'players' not in tables and 'time_preferences' not in tables and 'assignments' not in tables
    assert conn.execute('SELECT COUNT(*) FROM legacy_players').fetchone()[0] == len(PLAYERS)
    assert [tuple(r) for r in conn.execute('SELECT version FROM schema_version ORDER BY version')] == [(1,), (2,), (3,), (4,), (5,)]

    # one open imported ministry round with the old global settings
    rounds = conn.execute('SELECT * FROM rounds').fetchall()
    assert len(rounds) == 1
    rnd = rounds[0]
    assert (rnd['event'], rnd['name'], rnd['status']) == ('ministry', 'Imported from previous system', 'open')
    assert rnd['closing_time'] == '2026-09-14T18:00:00Z'
    assert json.loads(rnd['settings']) == {'research_day': 'tuesday', 'show_fire_crystals': True,
                                           'time_slot_scheme': 'max_slots', 'published_days': ['monday', 'thursday']}
    # global setting stays global; round keys moved out
    gs = dict(conn.execute('SELECT key, value FROM settings').fetchall())
    assert gs == {'state_number': '2807'}

    # every player -> profile (same id) + application
    for p in PLAYERS:
        (pid, fid, name, c, r, t, g, fc, rfc, sh, created, avatar, stove, stove_c, alliance, tz) = p
        prof = conn.execute('SELECT * FROM profiles WHERE id = ?', (pid,)).fetchone()
        assert prof is not None, fid
        assert (prof['fid'], prof['game_name'], prof['alliance'], prof['timezone']) == (fid, name, alliance, tz)
        assert (prof['avatar_image'], prof['stove_lv'], prof['stove_lv_content']) == (avatar, stove, stove_c)
        assert prof['created_at'] == created.replace(' ', 'T') + 'Z'
        app = conn.execute('SELECT * FROM applications WHERE player_id = ? AND round_id = ?',
                           (pid, rnd['id'])).fetchone()
        a = json.loads(app['answers'])
        assert (a['construction_speedups_days'], a['research_speedups_days'], a['troop_training_speedups_days'],
                a['general_speedups_days'], a['fire_crystals'], a['refined_fire_crystals'],
                a['fire_crystal_shards']) == (c, r, t, g, fc, rfc, sh)
        expected = {'construction': [], 'research': [], 'troop': []}
        for ppid, slot, dt in PREFS:
            if ppid == pid:
                expected[dt].append(slot)
        assert a['time_slots_by_day'] == expected, fid
        assert json.loads(app['profile_snapshot'])['game_name'] == name
    assert conn.execute('SELECT COUNT(*) FROM applications').fetchone()[0] == len(PLAYERS)

    # every (non-orphan) assignment with its sticky flag
    got = sorted(tuple(r) for r in conn.execute(
        'SELECT player_id, day, time_slot, position, is_assigned, is_sticky FROM ministry_assignments '
        'WHERE round_id = ?', (rnd['id'],)))
    assert got == sorted(a for a in ASSIGNMENTS if a[0] != 999)
    conn.close()


def test_migration_twice_is_noop(legacy_path):
    build_app(legacy_path)
    first = dump(legacy_path)
    build_app(legacy_path)
    build_app(legacy_path)
    assert dump(legacy_path) == first
    assert len(glob.glob(legacy_path + '.pre-v2-*.bak')) == 1


def test_migrated_db_works_through_api(legacy_path):
    app = build_app(legacy_path)
    c = app.test_client()
    tok = c.post('/api/admin/login', json={'password': ADMIN_PW}).json['token']
    h = {'Authorization': f'Bearer {tok}'}
    cur = c.get('/api/events/ministry/current').json
    assert cur['name'] == 'Imported from previous system'
    assert cur['settings']['time_slot_scheme'] == 'max_slots'
    # existing players can still edit after the (past) closing time; new ones are blocked
    r = c.put('/api/events/ministry/current/application/1002',
              json={'profile': {}, 'answers': {'construction_speedups_days': 2}})
    assert r.status_code == 200 and r.json['created'] is False
    r = c.put('/api/events/ministry/current/application/5555',
              json={'profile': {'game_name': 'New', 'alliance': 'N'}, 'answers': {}})
    assert r.status_code == 403 and r.json['code'] == 'APPLICATIONS_CLOSED'
    mon = c.get(f'/api/admin/ministry/rounds/{cur["id"]}/assignments/monday', headers=h).json
    assert mon['assignments']['23:50+'][0]['fid'] == '1003'
    assert mon['assignments']['13:50'][0]['is_sticky'] is True
    assert {u['fid'] for u in mon['unassigned']} == {'1002', '1007', 'legacy-fid-9'}
    # legacy odd FID is readable
    assert c.get('/api/events/ministry/current/application/legacy-fid-9').status_code == 200
    # sticky survives auto-assign on the migrated data
    thu = c.post(f'/api/admin/ministry/rounds/{cur["id"]}/auto-assign', json={'day': 'thursday'}, headers=h).json
    assert thu['assignments']['14:20'][0]['fid'] == '1005' and thu['assignments']['14:20'][0]['is_sticky']
    assert c.get('/api/events/ministry/current/schedule/thursday').json['published'] is True
    assert c.get('/api/settings/public').json['state_number'] == '2807'
    # start a new round: imported round kept, previous-application points at it
    c.post('/api/admin/events/ministry/start-new-round', json={'name': 'Next'}, headers=h)
    prev = c.get('/api/events/ministry/previous-application/1001').json
    assert prev['round_name'] == 'Imported from previous system'
    assert prev['answers']['construction_speedups_days'] == 3.5


def test_scheme_pinned_when_setting_missing(tmp_path):
    p = str(tmp_path / 'a.db')
    s = {k: v for k, v in SETTINGS.items() if k != 'time_slot_scheme'}
    make_v14_db(p, settings=s)
    build_app(p)
    conn = ro(p)
    assert json.loads(conn.execute('SELECT settings FROM rounds').fetchone()[0])['time_slot_scheme'] == 'max_slots'

    # no stored scheme and assignments on the hour grid -> exact_alignment (what v1.4 was running)
    p3 = str(tmp_path / 'c.db')
    make_v14_db(p3, settings=s, assignments=[(1, 'monday', '10:00', 0, 1, 0), (2, 'monday', '10:30', 0, 1, 0)])
    build_app(p3)
    row = ro(p3).execute('SELECT settings FROM rounds').fetchone()
    assert json.loads(row[0])['time_slot_scheme'] == 'exact_alignment'

    p2 = str(tmp_path / 'b.db')
    make_v14_db(p2, settings={}, assignments=[])
    build_app(p2)
    conn = ro(p2)
    row = conn.execute('SELECT settings, closing_time FROM rounds').fetchone()
    assert json.loads(row[0]) == {'research_day': 'tuesday', 'show_fire_crystals': False,
                                  'time_slot_scheme': 'exact_alignment', 'published_days': []}
    assert row[1] is None


def test_failed_migration_rolls_back(legacy_path, monkeypatch):
    def boom(conn):
        raise RuntimeError('simulated crash mid-migration')
    monkeypatch.setattr(core_db, '_import_v14', boom)
    with pytest.raises(RuntimeError):
        build_app(legacy_path)
    conn = ro(legacy_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert 'players' in tables and 'legacy_players' not in tables and 'profiles' not in tables
    # schema_version is created INSIDE the migration transaction now, so it rolled back too
    assert 'schema_version' not in tables
    conn.close()
    # L1: a failed attempt leaves no backup (neither final nor partial) behind
    assert glob.glob(legacy_path + '.pre-v2-*') == []
    monkeypatch.undo()
    build_app(legacy_path)  # retry succeeds
    assert ro(legacy_path).execute('SELECT COUNT(*) FROM profiles').fetchone()[0] == len(PLAYERS)
    assert len(glob.glob(legacy_path + '.pre-v2-*.bak')) == 1 and not glob.glob(legacy_path + '*.partial')


def test_fresh_db_gets_v2_schema_without_rounds(tmp_path):
    p = str(tmp_path / 'fresh.db')
    build_app(p)
    conn = ro(p)
    assert conn.execute('SELECT version FROM schema_version').fetchall()[0][0] == 1
    assert conn.execute('SELECT COUNT(*) FROM rounds').fetchone()[0] == 0
    assert conn.execute('PRAGMA journal_mode').fetchone()[0] == 'delete'
    assert not glob.glob(p + '.pre-v2-*.bak')


def test_older_pre_v14_columns_tolerated(tmp_path):
    """A DB that never ran the v1.1/v1.2 ALTERs (no alliance/is_sticky/day_type) still migrates."""
    p = str(tmp_path / 'old.db')
    conn = sqlite3.connect(p)
    conn.execute(V14_SCHEMA[0])
    conn.execute('CREATE TABLE time_preferences (id INTEGER PRIMARY KEY AUTOINCREMENT, player_id INTEGER, '
                 'time_slot TEXT)')
    conn.execute('CREATE TABLE assignments (id INTEGER PRIMARY KEY AUTOINCREMENT, player_id INTEGER, day TEXT, '
                 'time_slot TEXT, position INTEGER DEFAULT 0, is_assigned BOOLEAN DEFAULT 1)')
    conn.execute("INSERT INTO players (id, fid, game_name, construction_speedups_days, fire_crystals) "
                 "VALUES (1, '1', 'Old', NULL, 2)")
    conn.execute("INSERT INTO time_preferences (player_id, time_slot) VALUES (1, '08:00')")
    conn.execute("INSERT INTO assignments (player_id, day, time_slot) VALUES (1, 'Monday', '08:00')")
    conn.commit()
    conn.close()
    build_app(p)
    c = ro(p)
    a = json.loads(c.execute('SELECT answers FROM applications').fetchone()[0])
    assert a['construction_speedups_days'] == 0 and a['fire_crystals'] == 2
    assert a['time_slots_by_day'] == {'construction': ['08:00'], 'research': ['08:00'], 'troop': ['08:00']}
    assert tuple(c.execute('SELECT day, time_slot, is_sticky FROM ministry_assignments').fetchone()) == \
        ('monday', '08:00', 0)
    assert c.execute('SELECT alliance FROM profiles').fetchone()[0] is None
