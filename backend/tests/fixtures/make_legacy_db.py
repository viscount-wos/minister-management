#!/usr/bin/env python3
"""Build a DUMMY minister_management v1.4.0 SQLite database for migration tests.

Usage:
    python make_legacy_db.py OUT.db [--players N] [--seed S]
                             [--research-day tuesday|friday]
                             [--scheme max_slots|exact_alignment] [--force]
    python make_legacy_db.py OUT.db --check      # print counts/digest as JSON

From Python (pytest):
    from make_legacy_db import build_legacy_db, table_counts, CASES
    build_legacy_db(tmp_path / "legacy.db", players=150, seed=2807)
    counts = table_counts(tmp_path / "legacy.db")

Everything here is invented. No real player data is used or fetched.

The schema is replicated statement-for-statement from backend/database.py at
v1.4.0 (commit 5454016): the original CREATE TABLEs, then the ALTER TABLE
migrations in the same order, so `sqlite_master.sql` and PRAGMA table_info
column order match a real long-lived v1.4 database (the ALTER-added columns sit
at the END of `players` / `assignments`). See README.md for the awkward cases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sqlite3
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# v1.4 schema, copied verbatim from backend/database.py::init_db (v1.4.0)
# ---------------------------------------------------------------------------
V14_CREATE = [
    '''
            CREATE TABLE IF NOT EXISTS players (
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
            )
        ''',
    '''
            CREATE TABLE IF NOT EXISTS time_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                time_slot TEXT NOT NULL,
                day_type TEXT NOT NULL DEFAULT 'construction',
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
                UNIQUE(player_id, time_slot, day_type)
            )
        ''',
    '''
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                day TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                position INTEGER DEFAULT 0,
                is_assigned BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
                UNIQUE(day, time_slot, position)
            )
        ''',
    '''
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''',
    '''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''',
    'CREATE INDEX IF NOT EXISTS idx_players_fid ON players(fid)',
    'CREATE INDEX IF NOT EXISTS idx_time_prefs_player ON time_preferences(player_id)',
    'CREATE INDEX IF NOT EXISTS idx_assignments_day ON assignments(day)',
]

V14_ALTERS = [
    'ALTER TABLE players ADD COLUMN avatar_image TEXT DEFAULT NULL',
    'ALTER TABLE players ADD COLUMN stove_lv INTEGER DEFAULT NULL',
    'ALTER TABLE players ADD COLUMN stove_lv_content TEXT DEFAULT NULL',
    'ALTER TABLE players ADD COLUMN alliance TEXT DEFAULT NULL',
    'ALTER TABLE players ADD COLUMN timezone TEXT DEFAULT NULL',
    'ALTER TABLE assignments ADD COLUMN is_sticky BOOLEAN DEFAULT 0',
]

# Column order a real v1.4 DB ends up with (checked by --check).
EXPECTED_COLUMNS = {
    'players': [
        'id', 'fid', 'game_name', 'construction_speedups_days', 'research_speedups_days',
        'troop_training_speedups_days', 'general_speedups_days', 'fire_crystals',
        'refined_fire_crystals', 'fire_crystal_shards', 'created_at', 'updated_at',
        'avatar_image', 'stove_lv', 'stove_lv_content', 'alliance', 'timezone',
    ],
    'time_preferences': ['id', 'player_id', 'time_slot', 'day_type'],
    'assignments': [
        'id', 'player_id', 'day', 'time_slot', 'position', 'is_assigned', 'created_at',
        'is_sticky',
    ],
    'admin_users': ['id', 'username', 'password_hash', 'role', 'created_at'],
    'settings': ['key', 'value'],
}

TABLES = ['players', 'time_preferences', 'assignments', 'admin_users', 'settings']


def create_v14_schema(conn: sqlite3.Connection) -> None:
    """Create the schema exactly as a v1.4 init_db() run leaves it."""
    conn.execute('PRAGMA journal_mode=DELETE')
    cur = conn.cursor()
    for stmt in V14_CREATE:
        cur.execute(stmt)
    conn.commit()
    for stmt in V14_ALTERS:
        cur.execute(stmt)
    conn.commit()


# ---------------------------------------------------------------------------
# Slot helpers (mirror app.py v1.4)
# ---------------------------------------------------------------------------
def generate_time_slots(scheme: str) -> list[str]:
    if scheme == 'exact_alignment':
        return [f'{h:02d}:{m:02d}' for h in range(24) for m in (0, 30)]
    slots = ['23:50']
    h, m = 0, 20
    while True:
        s = f'{h:02d}:{m:02d}'
        if s == '23:50':
            slots.append('23:50+')
            return slots
        slots.append(s)
        m += 30
        if m >= 60:
            m -= 60
            h += 1


def matching_slots_for_pref(hour: int, scheme: str) -> list[str]:
    if scheme == 'exact_alignment':
        return [f'{hour:02d}:00', f'{hour:02d}:30']
    prev_h = (hour - 1) % 24
    res = ['23:50'] if hour == 0 else [f'{prev_h:02d}:50']
    res.append(f'{hour:02d}:20')
    res.append('23:50+' if hour == 23 else f'{hour:02d}:50')
    return res


def calculate_points(p: dict, day: str) -> int:
    """v1.4 calculate_points, for picking plausible assignment winners."""
    c = p['construction_speedups_days'] * 1440
    r = p['research_speedups_days'] * 1440
    g = p['general_speedups_days'] * 1440
    if day == 'monday':
        return int(c + g + p['refined_fire_crystals'] * 30000 + p['fire_crystals'] * 2000)
    if day in ('tuesday', 'friday'):
        return int(r + g + p['fire_crystal_shards'] * 1000)
    if day == 'thursday':
        return int(p['troop_training_speedups_days'])
    return 0


DAY_TYPE = {'monday': 'construction', 'tuesday': 'research', 'friday': 'research',
            'thursday': 'troop'}
HOURS = [f'{h:02d}:00' for h in range(24)]

# ---------------------------------------------------------------------------
# Dummy name / tag material
# ---------------------------------------------------------------------------
ALLIANCES = ['LOV', 'ICE', 'WLF', 'KOR', '龍族', 'TRK', 'PLX', 'نجم']
ALLIANCE_WEIGHTS = [30, 18, 14, 12, 8, 8, 6, 4]
LATIN = ['Frost', 'Ember', 'Viking', 'Nova', 'Raven', 'Blaze', 'Storm', 'Aurora',
         'Ghost', 'Titan', 'Luna', 'Wolf', 'Kai', 'Odin', 'Mira', 'Zed']
KOREAN = ['눈보라', '불꽃', '겨울왕', '하늘', '용사', '북극곰', '별빛']
CHINESE = ['冰雪', '龙王', '火焰', '小白', '风暴', '老虎', '雪狼']
ARABIC = ['صقر', 'نمر', 'الأسد', 'ليث', 'فارس', 'ذئب']
TURKISH = ['Çağrı', 'Gümüş', 'Şimşek', 'Ilık', 'Öztürk', 'Yiğit', 'İsmail']
POLISH = ['Łukasz', 'Źdźbło', 'Wiedźmin', 'Żubr', 'Gęś', 'Ślązak']
EMOJI = ['🔥', '❄️', '🐺', '👑', '⚔️', '🐉', '💀', '✨']
TIMEZONES = ['UTC', 'Asia/Seoul', 'Asia/Shanghai', 'America/New_York', 'America/Chicago',
             'America/Los_Angeles', 'Europe/Istanbul', 'Asia/Riyadh']

BASE_PRE_AUG = datetime(2026, 4, 20, 9, 0, 0)      # v1.0 era, "Load from WOS" existed
AUG_CUTOFF = datetime(2026, 8, 1, 0, 0, 0)         # v1.3.0 removed the WOS lookup
BASE_POST_AUG = datetime(2026, 8, 3, 12, 0, 0)
FIXTURE_NOW = datetime(2026, 10, 7, 21, 0, 0)      # pinned "today" for determinism


def ts(dt: datetime) -> str:
    return dt.strftime('%Y-%m-%d %H:%M:%S')     # SQLite CURRENT_TIMESTAMP format


# ---------------------------------------------------------------------------
# Hand-written awkward cases. FIDs are fixed so tests can look them up.
# Each: dict of player columns + 'prefs' ({day_type: [hours]} | list (legacy) | None)
# ---------------------------------------------------------------------------
def _p(**kw):
    base = dict(construction_speedups_days=0.0, research_speedups_days=0.0,
                troop_training_speedups_days=0.0, general_speedups_days=0.0,
                fire_crystals=0, refined_fire_crystals=0, fire_crystal_shards=0,
                avatar_image=None, stove_lv=None, stove_lv_content=None,
                alliance='LOV', timezone='UTC', prefs=None,
                created=BASE_POST_AUG, updated=None)
    base.update(kw)
    return base


def _avatar(n):
    return f'https://example.invalid/avatar/{n}.png'


def _stove_icon(lv):
    return f'https://example.invalid/stove/fc{lv}.png'


SPECIAL_CASES = {
    # --- pre-August rows: legacy WOS lookup columns populated -----------------
    'pre_aug_full': _p(fid='310000001', game_name='Frost Viking', stove_lv=30,
                       avatar_image=_avatar(1), stove_lv_content=_stove_icon(5),
                       alliance=None, timezone=None, construction_speedups_days=120.5,
                       created=datetime(2026, 4, 21, 10, 0), prefs=['12:00', '13:00', '23:00']),
    'pre_aug_stove_only': _p(fid='310000002', game_name='눈보라왕', stove_lv=27,
                             stove_lv_content=None, avatar_image=_avatar(2),
                             alliance='KOR', timezone='Asia/Seoul',
                             created=datetime(2026, 5, 2, 3, 4, 5),
                             updated=datetime(2026, 9, 30, 8, 0),
                             prefs={'construction': ['01:00'], 'research': [], 'troop': ['01:00']}),
    'pre_aug_fc_level_high': _p(fid='310000003', game_name='龙王🐉', stove_lv=35,
                                avatar_image=_avatar(3), stove_lv_content=_stove_icon(10),
                                alliance='龍族', timezone='Asia/Shanghai',
                                research_speedups_days=300.25,
                                created=datetime(2026, 7, 31, 23, 59, 59),
                                prefs={'construction': [], 'research': ['00:00', '01:00'], 'troop': []}),
    # --- import path (POST /api/admin/players/import) writes '' not NULL ----
    'import_empty_strings': _p(fid='320000001', game_name='Imported Ghost', avatar_image='',
                               stove_lv=None, stove_lv_content='', alliance='',
                               timezone='', prefs=None),
    'import_lowercase_long_tag': _p(fid='320000002', game_name='Mira', alliance='love',
                                    timezone='Europe/Istanbul',
                                    prefs={'construction': ['08:00'], 'research': ['08:00'],
                                           'troop': ['08:00']}),
    # --- awkward FIDs ---------------------------------------------------------
    'fid_leading_zero': _p(fid='0040021', game_name='Zero Lead', prefs={'troop': ['05:00']}),
    'fid_trailing_space': _p(fid='330000777 ', game_name='Space Tail',
                             prefs={'construction': ['06:00']}),
    'fid_beyond_js_safe_int': _p(fid='90071992547409931', game_name='BigFid',
                                 prefs={'research': ['07:00']}),
    # --- awkward names ----------------------------------------------------------
    'name_dup_exact_ci': _p(fid='340000001', game_name='viking', prefs=None),
    'name_dup_trailing_space': _p(fid='340000002', game_name='Viking ', prefs=None),
    'name_dup_homoglyph': _p(fid='340000003', game_name='Vikіng', prefs=None),  # Cyrillic і
    'name_dup_fullwidth': _p(fid='340000004', game_name='Ｖｉｋｉｎｇ', prefs=None),
    'name_nfc': _p(fid='340000005', game_name=unicodedata.normalize('NFC', 'Zoë'), prefs=None),
    'name_nfd': _p(fid='340000006', game_name=unicodedata.normalize('NFD', 'Zoë'), prefs=None),
    'name_zwj_emoji': _p(fid='340000007', game_name='👨‍👩‍👧 Family', prefs=None),
    'name_rtl_mixed': _p(fid='340000008', game_name='الأسد 2807 LOV', alliance='نجم',
                         timezone='Asia/Riyadh', prefs={'troop': ['20:00', '21:00']}),
    'name_sql_quote': _p(fid='340000009', game_name="Robert'); DROP TABLE players;--",
                         prefs=None),
    'name_html': _p(fid='340000010', game_name='<b>bold</b> & "quoted"', prefs=None),
    'name_csv_formula': _p(fid='340000011', game_name='=HYPERLINK("x","y"),;', prefs=None),
    'name_long': _p(fid='340000012', game_name='Ł' * 20 + 'Şimşek' * 5 + '🔥' * 4, prefs=None),
    'name_turkish_i': _p(fid='340000013', game_name='İSMAİL ılık', alliance='TRK',
                         timezone='Europe/Istanbul', prefs={'construction': ['18:00']}),
    'name_polish': _p(fid='340000014', game_name='Źdźbło Gęś-Żubr', alliance='PLX',
                      prefs={'research': ['19:00']}),
    # --- numeric edge values ----------------------------------------------------
    'max_values': _p(fid='350000001', game_name='Max Whale 👑',
                     construction_speedups_days=99999.0, research_speedups_days=99999.0,
                     troop_training_speedups_days=99999.0, general_speedups_days=99999.0,
                     fire_crystals=99999, refined_fire_crystals=99999, fire_crystal_shards=99999,
                     prefs={'construction': HOURS, 'research': HOURS, 'troop': HOURS}),
    'all_zero': _p(fid='350000002', game_name='Zero Hero',
                   prefs={'construction': ['10:00'], 'research': ['10:00'], 'troop': ['10:00']}),
    'fractional': _p(fid='350000003', game_name='Frac 0.1',
                     construction_speedups_days=0.1, research_speedups_days=12.25,
                     troop_training_speedups_days=3.3333333333, general_speedups_days=0.5,
                     prefs={'construction': ['11:00'], 'research': ['11:00']}),
    'real_in_integer_column': _p(fid='350000004', game_name='Half Crystal',
                                 fire_crystals=12.5, fire_crystal_shards=7.75,
                                 prefs={'construction': ['14:00']}),
    # --- time-pref shapes -------------------------------------------------------
    'legacy_prefs_all_days': _p(fid='360000001', game_name='Legacy Same Slots',
                                created=datetime(2026, 5, 10, 12, 0), avatar_image=_avatar(9),
                                stove_lv=29, stove_lv_content=_stove_icon(2),
                                prefs=['15:00', '16:00', '17:00']),
    'no_prefs_assigned_manually': _p(fid='360000002', game_name='Manual Pick',
                                     construction_speedups_days=500.0, prefs=None),
    'shared_slot_winner': _p(fid='360000003', game_name='Midnight Owl 🦉',
                             construction_speedups_days=900.0, research_speedups_days=900.0,
                             troop_training_speedups_days=900.0,
                             prefs={'construction': ['23:00'], 'research': ['00:00'],
                                    'troop': ['23:00']}),
    'shared_slot_loser': _p(fid='360000004', game_name='Midnight Second',
                            construction_speedups_days=10.0, research_speedups_days=10.0,
                            prefs={'construction': ['23:00'], 'research': ['00:00'],
                                   'troop': ['23:00']}),
    # --- deleted players (FKs are OFF in v1.4 -> orphans remain) --------------
    'deleted_assigned_sticky': _p(fid='370000001', game_name='Gone Sticky',
                                  construction_speedups_days=700.0,
                                  prefs={'construction': ['09:00']}),
    'deleted_with_prefs': _p(fid='370000002', game_name='Gone Prefs',
                             prefs={'research': ['09:00'], 'troop': ['09:00']}),
}

DELETED_CASES = ('deleted_assigned_sticky', 'deleted_with_prefs')

# Public map case -> fid, for tests.
CASES = {k: v['fid'] for k, v in SPECIAL_CASES.items()}


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
def _random_name(rng: random.Random, i: int) -> str:
    pool = rng.choice([LATIN, LATIN, KOREAN, CHINESE, ARABIC, TURKISH, POLISH])
    name = rng.choice(pool)
    r = rng.random()
    if r < 0.25:
        name += rng.choice(EMOJI)
    elif r < 0.45:
        name = rng.choice(EMOJI) + name
    if rng.random() < 0.5:
        name += str(rng.randint(1, 999))
    else:
        name += f' {i}'
    return name


def _random_prefs(rng: random.Random):
    r = rng.random()
    if r < 0.15:
        return None                                       # no prefs at all
    if r < 0.25:
        return rng.sample(HOURS, rng.randint(1, 6))       # legacy list, same all days
    prefs = {}
    for dt in ('construction', 'research', 'troop'):
        if rng.random() < 0.3:
            continue                                      # some days only
        n = rng.choice([1, 2, 3, 4, 6, 8, 12, 24])
        prefs[dt] = sorted(rng.sample(HOURS, n))
    return prefs


def _random_player(rng: random.Random, i: int) -> dict:
    pre_aug = rng.random() < 0.4
    created = (BASE_PRE_AUG + timedelta(minutes=rng.randint(0, 100 * 24 * 60))) if pre_aug \
        else (BASE_POST_AUG + timedelta(minutes=rng.randint(0, 60 * 24 * 60)))
    created = min(created, AUG_CUTOFF - timedelta(seconds=1)) if pre_aug else created

    def speed():
        r = rng.random()
        if r < 0.15:
            return 0.0
        if r < 0.5:
            return round(rng.uniform(0, 80), rng.choice([0, 1, 2]))
        return round(rng.uniform(50, 2500), rng.choice([0, 1, 2]))

    p = _p(
        fid=str(rng.randint(10_000_000, 999_999_999)),
        game_name=_random_name(rng, i),
        construction_speedups_days=speed(), research_speedups_days=speed(),
        troop_training_speedups_days=speed(), general_speedups_days=speed(),
        fire_crystals=rng.choice([0, 0, 0, rng.randint(1, 3000)]),
        refined_fire_crystals=rng.choice([0, 0, 0, rng.randint(1, 400)]),
        fire_crystal_shards=rng.choice([0, 0, rng.randint(1, 5000)]),
        alliance=rng.choices(ALLIANCES, ALLIANCE_WEIGHTS)[0],
        timezone=rng.choice(TIMEZONES),
        prefs=_random_prefs(rng),
        created=created,
    )
    if pre_aug:
        # Pre-v1.3 rows: avatar/stove from the old WOS lookup. Some had no
        # alliance/timezone yet (columns added later -> NULL).
        lv = rng.randint(22, 35)
        p.update(avatar_image=_avatar(1000 + i), stove_lv=lv,
                 stove_lv_content=_stove_icon(lv - 30) if lv > 30 else None)
        if rng.random() < 0.3:
            p['alliance'] = None
        if rng.random() < 0.5:
            p['timezone'] = None
    if rng.random() < 0.3:
        p['updated'] = created + timedelta(days=rng.randint(1, 20), minutes=rng.randint(0, 999))
    return p


def _insert_player(cur, p) -> int:
    upd = p['updated'] or p['created']
    if upd > FIXTURE_NOW:
        upd = FIXTURE_NOW
    cur.execute('''
        INSERT INTO players (fid, game_name, construction_speedups_days, research_speedups_days,
            troop_training_speedups_days, general_speedups_days, fire_crystals,
            refined_fire_crystals, fire_crystal_shards, created_at, updated_at,
            avatar_image, stove_lv, stove_lv_content, alliance, timezone)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
        p['fid'], p['game_name'], p['construction_speedups_days'], p['research_speedups_days'],
        p['troop_training_speedups_days'], p['general_speedups_days'], p['fire_crystals'],
        p['refined_fire_crystals'], p['fire_crystal_shards'], ts(min(p['created'], FIXTURE_NOW)),
        ts(upd), p['avatar_image'], p['stove_lv'], p['stove_lv_content'], p['alliance'],
        p['timezone']))
    pid = cur.lastrowid
    prefs = p['prefs']
    if isinstance(prefs, list):          # legacy list -> same slots on all three day types
        for slot in prefs:
            for dt in ('construction', 'research', 'troop'):
                cur.execute('INSERT INTO time_preferences (player_id, time_slot, day_type) '
                            'VALUES (?,?,?)', (pid, slot, dt))
    elif isinstance(prefs, dict):
        for dt, slots in prefs.items():
            for slot in slots:
                cur.execute('INSERT INTO time_preferences (player_id, time_slot, day_type) '
                            'VALUES (?,?,?)', (pid, slot, dt))
    return pid


def _prefs_for(p: dict, day_type: str) -> list[str]:
    prefs = p['prefs']
    if isinstance(prefs, list):
        return prefs
    if isinstance(prefs, dict):
        return prefs.get(day_type, [])
    return []


def build_legacy_db(out, players: int = 150, seed: int = 2807, research_day: str = 'tuesday',
                    scheme: str = 'max_slots', force: bool = False) -> dict:
    """Create the dummy v1.4 DB at `out`. Returns table_counts(out)."""
    out = Path(out)
    if out.exists():
        if not force:
            raise FileExistsError(f'{out} exists (use --force)')
        out.unlink()
    if research_day not in ('tuesday', 'friday'):
        raise ValueError('research_day must be tuesday or friday')
    rng = random.Random(seed)

    conn = sqlite3.connect(out)
    conn.row_factory = sqlite3.Row
    create_v14_schema(conn)
    cur = conn.cursor()

    # 1) players: special cases interleaved with random ones, in created_at order
    n_random = max(players - len(SPECIAL_CASES), 0)
    rows = [(k, v) for k, v in SPECIAL_CASES.items()]
    rows += [(None, _random_player(rng, i)) for i in range(n_random)]
    seen_fids = {v['fid'] for _, v in SPECIAL_CASES.items()}
    for case, p in rows:
        while case is None and p['fid'] in seen_fids:
            p['fid'] = str(rng.randint(10_000_000, 999_999_999))
        seen_fids.add(p['fid'])
    rows.sort(key=lambda kv: (kv[1]['created'], kv[1]['fid']))

    by_pid: dict[int, dict] = {}
    case_pid: dict[str, int] = {}
    for idx, (case, p) in enumerate(rows):
        pid = _insert_player(cur, p)
        by_pid[pid] = p
        if case:
            case_pid[case] = pid
        # a few random rows get deleted later -> id gaps without orphans
        if case is None and idx % 37 == 5:
            p['_gap'] = True

    # 2) assignments on monday, research day, thursday (+ stale other research day)
    slots = generate_time_slots(scheme)
    days = ['monday', research_day, 'thursday']
    shared = None
    if scheme == 'max_slots':
        shared = ('monday', 'tuesday') if research_day == 'tuesday' else ('thursday', 'friday')

    assign_time = ts(datetime(2026, 10, 5, 19, 30))
    taken: dict[str, dict[str, int]] = {d: {} for d in days}
    sticky_pids: set[tuple[str, int]] = set()

    def put(day, slot, pid, sticky=0):
        taken[day][slot] = pid
        if sticky:
            sticky_pids.add((day, pid))

    # shared 23:50 boundary slot: one player holds both rows, sticky on both
    if shared:
        w = case_pid['shared_slot_winner']
        put(shared[0], '23:50+', w, 1)
        put(shared[1], '23:50', w, 1)
    # sticky manual placement of someone with no time prefs
    manual_slot = '12:20' if scheme == 'max_slots' else '12:00'
    put('monday', manual_slot, case_pid['no_prefs_assigned_manually'], 1)
    # sticky for a player that will be deleted (orphan sticky assignment)
    gone_slot = '09:20' if scheme == 'max_slots' else '09:00'
    put('monday', gone_slot, case_pid['deleted_assigned_sticky'], 1)

    for day in days:
        dtype = DAY_TYPE[day]
        cands = [(calculate_points(p, day), pid) for pid, p in by_pid.items()
                 if _prefs_for(p, dtype) and pid not in taken[day].values()]
        cands.sort(key=lambda t: (-t[0], t[1]))
        for pts, pid in cands:
            if pid == case_pid['shared_slot_loser']:
                continue                      # lost the boundary -> stays unassigned
            if rng.random() < 0.12:
                continue                      # leave some genuine unassigned applicants
            p = by_pid[pid]
            options = [s for h in _prefs_for(p, dtype)
                       for s in matching_slots_for_pref(int(h[:2]), scheme)
                       if s in slots and s not in taken[day]]
            if shared and day in shared:
                options = [s for s in options if s not in ('23:50', '23:50+')]
            if not options:
                continue
            put(day, options[0], pid, 1 if rng.random() < 0.08 else 0)
        # leave a handful of slots deliberately empty by dropping late picks
    for day in days:
        for slot in slots:
            if slot in taken[day]:
                pid = taken[day][slot]
                cur.execute('''INSERT INTO assignments (player_id, day, time_slot, position,
                               is_assigned, created_at, is_sticky) VALUES (?,?,?,?,?,?,?)''',
                            (pid, day, slot, 0, 1, assign_time,
                             1 if (day, pid) in sticky_pids else 0))

    # stale rows for the OTHER research day (left behind after switching research_day)
    other = 'friday' if research_day == 'tuesday' else 'tuesday'
    stale_slots = [s for s in slots if s not in ('23:50', '23:50+')][10:15]
    stale_pids = sorted(by_pid)[:len(stale_slots)]
    for slot, pid in zip(stale_slots, stale_pids):
        cur.execute('''INSERT INTO assignments (player_id, day, time_slot, position, is_assigned,
                       created_at, is_sticky) VALUES (?,?,?,0,1,?,0)''',
                    (pid, other, slot, ts(datetime(2026, 9, 14, 18, 0))))

    # 3) deletions as v1.4 does them: DELETE FROM players only (FKs off -> orphans)
    for case in DELETED_CASES:
        cur.execute('DELETE FROM players WHERE id = ?', (case_pid[case],))
    gap_pids = [pid for pid, p in by_pid.items() if p.get('_gap')]
    for pid in gap_pids:
        # clean deletes (e.g. someone tidied up by hand) -> id gap, no orphans
        cur.execute('DELETE FROM assignments WHERE player_id = ?', (pid,))
        cur.execute('DELETE FROM time_preferences WHERE player_id = ?', (pid,))
        cur.execute('DELETE FROM players WHERE id = ?', (pid,))

    # 4) settings (all values are TEXT, as set_setting stores them)
    published = ['monday', research_day] if research_day == 'tuesday' else ['monday', 'thursday']
    settings = {
        'time_slot_scheme': scheme,
        'research_day': research_day,
        'show_fire_crystals': 'true',
        'application_closing_time': '2026-10-12T18:00:00.000Z',
        'state_number': '2807',
        'published_days': ','.join(published),
    }
    for k, v in settings.items():
        cur.execute('INSERT INTO settings (key, value) VALUES (?, ?)', (k, v))

    conn.commit()
    conn.close()
    return table_counts(out)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def _ro(path) -> sqlite3.Connection:
    conn = sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro&immutable=1', uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def table_counts(path) -> dict:
    """Row counts per table plus the awkward-case breakdowns tests assert on."""
    conn = _ro(path)
    q = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    counts = {t: q(f'SELECT COUNT(*) FROM {t}') for t in TABLES}
    counts['breakdown'] = {
        'players_with_avatar': q("SELECT COUNT(*) FROM players WHERE avatar_image IS NOT NULL "
                                 "AND avatar_image != ''"),
        'players_avatar_null': q('SELECT COUNT(*) FROM players WHERE avatar_image IS NULL'),
        'players_avatar_empty_string': q("SELECT COUNT(*) FROM players WHERE avatar_image = ''"),
        'players_stove_lv_set': q('SELECT COUNT(*) FROM players WHERE stove_lv IS NOT NULL'),
        'players_alliance_null': q('SELECT COUNT(*) FROM players WHERE alliance IS NULL'),
        'players_alliance_empty': q("SELECT COUNT(*) FROM players WHERE alliance = ''"),
        'players_timezone_null': q('SELECT COUNT(*) FROM players WHERE timezone IS NULL'),
        'players_no_prefs': q('SELECT COUNT(*) FROM players p WHERE NOT EXISTS '
                              '(SELECT 1 FROM time_preferences t WHERE t.player_id = p.id)'),
        'players_unassigned': q('SELECT COUNT(*) FROM players p WHERE NOT EXISTS '
                                '(SELECT 1 FROM assignments a WHERE a.player_id = p.id)'),
        'alliances': {r[0] if r[0] is not None else '<NULL>': r[1] for r in conn.execute(
            'SELECT alliance, COUNT(*) FROM players GROUP BY alliance ORDER BY alliance')},
        'prefs_by_day_type': {r[0]: r[1] for r in conn.execute(
            'SELECT day_type, COUNT(*) FROM time_preferences GROUP BY day_type')},
        'assignments_by_day': {r[0]: r[1] for r in conn.execute(
            'SELECT day, COUNT(*) FROM assignments GROUP BY day ORDER BY day')},
        'assignments_sticky': q('SELECT COUNT(*) FROM assignments WHERE is_sticky = 1'),
        'orphan_time_preferences': q('SELECT COUNT(*) FROM time_preferences t WHERE NOT EXISTS '
                                     '(SELECT 1 FROM players p WHERE p.id = t.player_id)'),
        'orphan_assignments': q('SELECT COUNT(*) FROM assignments a WHERE NOT EXISTS '
                                '(SELECT 1 FROM players p WHERE p.id = a.player_id)'),
        'shared_boundary_rows': q("SELECT COUNT(*) FROM assignments "
                                  "WHERE time_slot IN ('23:50', '23:50+')"),
        # max_slots: earlier day 23:50+ and later (research) day 23:50 are the same real
        # time and must hold the same player (monday/tuesday or thursday/friday).
        'linked_boundary_pairs': q(
            "SELECT COUNT(*) FROM assignments a JOIN assignments b ON a.player_id = b.player_id "
            "WHERE a.time_slot = '23:50+' AND b.time_slot = '23:50' AND "
            "((a.day = 'monday' AND b.day = 'tuesday') OR "
            " (a.day = 'thursday' AND b.day = 'friday'))"),
        'max_player_id': q('SELECT MAX(id) FROM players'),
    }
    counts['settings_values'] = {r[0]: r[1] for r in conn.execute(
        'SELECT key, value FROM settings ORDER BY key')}
    counts['schema_ok'] = all(
        [r[1] for r in conn.execute(f'PRAGMA table_info({t})')] == cols
        for t, cols in EXPECTED_COLUMNS.items())
    h = hashlib.sha256()
    for t in TABLES:
        for row in conn.execute(f'SELECT * FROM {t} ORDER BY 1'):
            h.update(repr(tuple(row)).encode())
    counts['content_sha256'] = h.hexdigest()
    conn.close()
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Build a DUMMY v1.4 ministry SQLite DB.')
    ap.add_argument('out', help='output .db path (or DB to inspect with --check)')
    ap.add_argument('--players', type=int, default=150)
    ap.add_argument('--seed', type=int, default=2807)
    ap.add_argument('--research-day', choices=['tuesday', 'friday'], default='tuesday')
    ap.add_argument('--scheme', choices=['max_slots', 'exact_alignment'], default='max_slots')
    ap.add_argument('--force', action='store_true', help='overwrite OUT if it exists')
    ap.add_argument('--check', action='store_true', help='only print counts for an existing DB')
    a = ap.parse_args(argv)
    if a.check:
        counts = table_counts(a.out)
    else:
        counts = build_legacy_db(a.out, a.players, a.seed, a.research_day, a.scheme, a.force)
    print(json.dumps(counts, ensure_ascii=False, indent=2))
    return 0 if counts['schema_ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
