"""Furnace levels: canonical string codes FC1-FC10 / 1-30, ordering, validation, migration 4."""
import json
import sqlite3

import pytest

from core import db as core_db
from core.furnace import FURNACE_LEVELS, furnace_ordinal, normalize_furnace, validate_furnace
from core.errors import ApiError
from tests.conftest import apply, start_round


def test_levels_order_and_ordinal():
    assert FURNACE_LEVELS[:3] == ('FC10', 'FC9', 'FC8') and FURNACE_LEVELS[9:12] == ('FC1', '30', '29')
    assert FURNACE_LEVELS[-1] == '1' and len(FURNACE_LEVELS) == 40
    ords = [furnace_ordinal(c) for c in FURNACE_LEVELS]
    assert ords == sorted(ords, reverse=True) and furnace_ordinal('FC10') == 40 and furnace_ordinal('1') == 1
    assert furnace_ordinal(None) == 0 and furnace_ordinal('FC11') == 0


@pytest.mark.parametrize('value,code', [('FC5', 'FC5'), ('fc10', 'FC10'), (' 7 ', '7'), (30, '30'), (1, '1'),
                                        (12.0, '12'), ('FC 3', 'FC3')])
def test_normalize(value, code):
    assert normalize_furnace(value) == code


@pytest.mark.parametrize('value', ['FC11', 'FC0', '31', '0', '007', 31, 0, -1, 2.5, True, 'high', [], 'FC05'])
def test_invalid(value):
    with pytest.raises(ApiError) as e:
        validate_furnace(value, 'profile.furnace_level')
    assert e.value.code == 'VALIDATION_ERROR' and e.value.field == 'profile.furnace_level'


def test_blank_is_null():
    assert validate_furnace(None) is None and validate_furnace('  ') is None


def test_api_stores_codes_for_every_event(client, admin):
    start_round(client, admin, 'M')
    r = apply(client, '1', furnace_level='fc9', expect=201)
    assert r.json['profile']['furnace_level'] == 'FC9'
    r = apply(client, '1', furnace_level=25)
    assert r.json['profile']['furnace_level'] == '25'
    r = apply(client, '1', furnace_level='FC11')
    assert r.status_code == 400 and r.json['field'] == 'profile.furnace_level'
    r = client.put('/api/profile/1', json={'furnace_level': '40'})
    assert r.status_code == 400 and r.json['field'] == 'furnace_level'
    r = client.put('/api/admin/profiles/1', json={'furnace_level': None}, headers=admin)
    assert r.status_code == 200 and r.json['profile']['furnace_level'] is None


def test_migration_4_converts_integers(tmp_path, monkeypatch):
    p = str(tmp_path / 'v3.db')
    monkeypatch.setattr(core_db, 'MIGRATIONS', core_db.MIGRATIONS[:3])
    core_db.migrate(p)
    con = sqlite3.connect(p)
    now = '2026-10-01T00:00:00Z'
    rows = [(1, '1', 30, None), (2, '2', 35, None), (3, '3', None, None), (4, '4', 0, None),
            (5, '5', 'FC4', json.dumps({'infantry': {'furnace_level': 12, 'tier': 10},
                                        'lancer': {'furnace_level': 99}, 'marksman': 5})),
            (9, '9', 1, None)]
    for pid, fid, lvl, troops in rows:
        con.execute('INSERT INTO profiles (id, fid, game_name, furnace_level, troops, created_at, updated_at) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?)', (pid, fid, f'P{fid}', lvl, troops, now, now))
    con.execute("INSERT INTO rounds (event, name, status, settings, created_at, updated_at) "
                "VALUES ('ministry', 'R', 'open', '{}', ?, ?)", (now, now))
    con.execute('INSERT INTO applications (round_id, player_id, created_at, updated_at) VALUES (1, 9, ?, ?)', (now, now))
    con.commit()
    con.close()
    monkeypatch.undo()  # all migrations again: only 4 is pending
    res = core_db.migrate(p)
    assert res[4]['converted'] == 3 and res[4]['nulled'] == 2  # 35 and 0 are not valid levels
    con = sqlite3.connect(p)
    got = dict(con.execute('SELECT fid, furnace_level FROM profiles').fetchall())
    assert got == {'1': '30', '2': None, '3': None, '4': None, '5': 'FC4', '9': '1'}
    assert con.execute("SELECT typeof(furnace_level) FROM profiles WHERE fid = '1'").fetchone()[0] == 'text'
    troops = json.loads(con.execute("SELECT troops FROM profiles WHERE fid = '5'").fetchone()[0])
    assert troops['infantry'] == {'furnace_level': '12', 'tier': 10} and troops['lancer']['furnace_level'] is None
    assert con.execute('PRAGMA foreign_key_check').fetchall() == []
    assert con.execute("SELECT seq FROM sqlite_sequence WHERE name = 'profiles'").fetchone()[0] == 9
    assert 'discord_id' in [r[1] for r in con.execute('PRAGMA table_info(profiles)')]
    con.execute('PRAGMA foreign_keys=ON')
    con.execute("DELETE FROM profiles WHERE fid = '9'")  # FK cascade still points at the rebuilt table
    assert con.execute('SELECT COUNT(*) FROM applications').fetchone()[0] == 0
    con.close()
    assert core_db.migrate(p) == {}  # idempotent
