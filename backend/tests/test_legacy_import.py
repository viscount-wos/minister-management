"""Milestone 1c: explicit v1.4 import (H1), locking (H2), exact crystals (M1), legacy FIDs/alliance (M2),
guard views against a stray v1.4 instance, one backup per import (L1), and the migrate CLI."""
import glob
import json
import multiprocessing as mp
import os
import shutil
import sqlite3
import subprocess
import sys
import textwrap

import pytest

from core import db as core_db
from core import migrate as migrate_cli
from tests.conftest import ADMIN_PW
from tests.test_migration import build_app, make_v14_db

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(HERE, 'fixtures'))
import make_legacy_db as F  # noqa: E402

V14_COMMIT = '5454016'


def _rich_legacy(tmp_path, name='rich.db', **kw):
    p = str(tmp_path / name)
    F.build_legacy_db(p, players=kw.pop('players', 60), seed=kw.pop('seed', 2807), force=True, **kw)
    return p


def _admin(client):
    tok = client.post('/api/admin/login', json={'password': ADMIN_PW}).json['token']
    return {'Authorization': f'Bearer {tok}'}


def _tables(path, kind='table'):
    c = sqlite3.connect(path)
    try:
        return {r[0] for r in c.execute('SELECT name FROM sqlite_master WHERE type = ?', (kind,))}
    finally:
        c.close()


# ---------------------------------------------------------------- H1: explicit import

def test_normal_boot_refuses_legacy_db_and_leaves_it_untouched(tmp_path):
    p = str(tmp_path / 'data' / 'minister.db')
    make_v14_db(p)
    before = open(p, 'rb').read()
    with pytest.raises(core_db.LegacyDatabaseError, match='python -m core.migrate'):
        build_app(p, migrate_v14=False)
    assert open(p, 'rb').read() == before
    assert glob.glob(p + '.pre-v2-*') == []


def test_migrate_cli_check_then_import_and_verify(tmp_path, capsys):
    p = _rich_legacy(tmp_path)
    before = open(p, 'rb').read()
    assert migrate_cli.main(['--db', p, '--check']) == 0
    out = capsys.readouterr().out
    assert 'v1.4_import_pending=True' in out
    assert open(p, 'rb').read() == before  # --check never writes
    assert migrate_cli.main(['--db', p]) == 0
    out = capsys.readouterr().out
    assert 'counts match' in out and 'schema_version=5' in out
    assert len(glob.glob(p + '.pre-v2-*.bak')) == 1
    assert migrate_cli.main(['--db', p]) == 0  # second run: no-op, still one backup
    assert len(glob.glob(p + '.pre-v2-*.bak')) == 1
    build_app(p, migrate_v14=False)  # a normal boot now works


def test_migrate_cli_refuses_missing_file(tmp_path):
    assert migrate_cli.main(['--db', str(tmp_path / 'nope.db')]) == 2
    assert not os.path.exists(tmp_path / 'nope.db')


def test_migrate_cli_runs_as_module(tmp_path):
    p = _rich_legacy(tmp_path, players=10)
    env = {k: v for k, v in os.environ.items() if k not in ('DATABASE_PATH',)}
    r = subprocess.run([sys.executable, '-m', 'core.migrate', '--db', p], cwd=os.path.dirname(HERE), env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert 'counts match' in r.stdout


# ---------------------------------------------------------------- H2: lock before version check

def _race_worker(path, barrier, q):
    barrier.wait()
    try:
        q.put(('ok', core_db.migrate(path, allow_v14=True)))
    except Exception as e:  # noqa: BLE001
        q.put(('error', f'{type(e).__name__}: {e}'))


@pytest.mark.skipif(sys.platform == 'win32', reason='fork')
def test_two_processes_migrating_at_once(tmp_path):
    p = _rich_legacy(tmp_path, players=1500, seed=5)
    ctx = mp.get_context('fork')
    barrier, q = ctx.Barrier(2), ctx.Queue()
    procs = [ctx.Process(target=_race_worker, args=(p, barrier, q)) for _ in range(2)]
    for x in procs:
        x.start()
    for x in procs:
        x.join(180)
    res = [q.get(timeout=5) for _ in procs]
    assert all(kind == 'ok' for kind, _ in res), res
    assert sorted(bool(r) for _, r in res) == [False, True]  # exactly one did the work, the other saw it done
    c = sqlite3.connect(p)
    assert c.execute('SELECT COUNT(*) FROM rounds').fetchone()[0] == 1
    assert c.execute('SELECT COUNT(*) FROM profiles').fetchone()[0] == \
        c.execute('SELECT COUNT(*) FROM legacy_players').fetchone()[0] > 1000
    assert [r[0] for r in c.execute('SELECT version FROM schema_version ORDER BY version')] == [1, 2, 3, 4, 5]
    c.close()
    assert len(glob.glob(p + '.pre-v2-*.bak')) == 1 and not glob.glob(p + '*.partial')


def test_stale_partial_backup_is_cleaned(tmp_path):
    p = str(tmp_path / 'm.db')
    make_v14_db(p)
    stale = p + '.pre-v2-20200101T000000Z.bak.partial'
    open(stale, 'w').write('junk from a killed attempt')
    core_db.migrate(p, allow_v14=True)
    assert not os.path.exists(stale)
    assert len(glob.glob(p + '.pre-v2-*.bak')) == 1


# ---------------------------------------------------------------- M1: crystals exactly as stored

def test_fractional_crystals_survive_and_points_match_v14(tmp_path):
    p = _rich_legacy(tmp_path)
    app = build_app(p)
    c = app.test_client()
    h = _admin(c)
    fid = F.CASES['real_in_integer_column']  # fire_crystals=12.5, shards=7.75
    a = c.get(f'/api/events/ministry/current/application/{fid}').json['answers']
    assert a['fire_crystals'] == 12.5 and a['fire_crystal_shards'] == 7.75 and a['refined_fire_crystals'] == 0
    rid = c.get('/api/events/ministry/current').json['id']
    row = next(x for x in c.get(f'/api/admin/rounds/{rid}/applications', headers=h).json['applications']
               if x['fid'] == fid)
    # v1.4 maths: monday = ... + fire_crystals*2000; research = ... + shards*1000
    assert row['monday_points'] == 25000 and row['research_points'] == 7750
    whole = F.CASES['max_values']
    assert c.get(f'/api/events/ministry/current/application/{whole}').json['answers']['fire_crystals'] == 99999
    assert isinstance(c.get(f'/api/events/ministry/current/application/{whole}').json['answers']['fire_crystals'],
                      int)

    # unchanged fractional value: player resubmit and admin edit both accepted, value kept exactly
    r = c.put(f'/api/events/ministry/current/application/{fid}', json={'profile': {}, 'answers': dict(a)})
    assert r.status_code == 200, r.json
    assert r.json['application']['answers']['fire_crystals'] == 12.5
    r = c.put(f'/api/admin/applications/{row["id"]}', json={'answers': {'general_speedups_days': 2}}, headers=h)
    assert r.status_code == 200 and r.json['answers']['fire_crystal_shards'] == 7.75
    # a NEW fractional value is still rejected (crystals are whole numbers)
    bad = dict(a, fire_crystals=13.5)
    r = c.put(f'/api/events/ministry/current/application/{fid}', json={'profile': {}, 'answers': bad})
    assert r.status_code == 400 and r.json['field'] == 'answers.fire_crystals'
    # and a whole number replaces the legacy fraction
    r = c.put(f'/api/events/ministry/current/application/{fid}', json={'profile': {}, 'answers': dict(a, fire_crystals=12)})
    assert r.status_code == 200 and r.json['application']['answers']['fire_crystals'] == 12


def test_exact_number_helper():
    assert core_db._exact_number(12.5) == 12.5
    assert core_db._exact_number(12.0) == 12 and isinstance(core_db._exact_number(12.0), int)
    assert core_db._exact_number('7.75') == 7.75
    assert core_db._exact_number(None) == 0 and core_db._exact_number('junk') == 0
    assert core_db._exact_number(float('nan')) == 0


# ---------------------------------------------------------------- M2: legacy FIDs

def test_fid_normalisation_rules():
    m, trimmed, kept = core_db.normalize_legacy_fids(['1 ', ' 2', '3', '3 ', '  ', '0040', '90071992547409931',
                                                     'abc '])
    assert m['1 '] == '1' and m[' 2'] == '2' and m['abc '] == 'abc'
    assert m['3 '] == '3 ' and m['3'] == '3'           # trimmed form collides: kept as stored
    assert m['  '] == '  '                              # trimmed form empty: kept
    assert m['0040'] == '0040' and m['90071992547409931'] == '90071992547409931'
    assert ('1 ', '1') in trimmed and '3 ' in kept


def test_legacy_fids_reachable_and_never_fork(tmp_path):
    p = _rich_legacy(tmp_path)
    app = build_app(p)
    c = app.test_client()
    h = _admin(c)
    rid = c.get('/api/events/ministry/current').json['id']
    n_apps = len(c.get(f'/api/admin/rounds/{rid}/applications', headers=h).json['applications'])
    n_profiles = len(c.get('/api/admin/profiles', headers=h).json['profiles'])

    ws = F.CASES['fid_trailing_space']            # '330000777 ' -> trimmed by the import
    for url_fid in ('330000777%20', '330000777'):
        assert c.get(f'/api/profile/{url_fid}').status_code == 200
        assert c.get(f'/api/events/ministry/current/application/{url_fid}').status_code == 200
        assert c.get(f'/api/events/ministry/current/assignments/{url_fid}').status_code == 200
        assert c.get(f'/api/admin/profiles/{url_fid}', headers=h).status_code == 200
    assert c.get('/api/profile/330000777').json['fid'] == ws.strip()
    r = c.put('/api/events/ministry/current/application/330000777%20',
              json={'profile': {'game_name': 'Space Tail', 'alliance': 'SPC'}, 'answers': {}})
    assert r.status_code == 200 and r.json['created'] is False and r.json['profile_created'] is False

    lead = F.CASES['fid_leading_zero']            # '0040021': leading zeros are significant
    assert c.get(f'/api/profile/{lead}').json['fid'] == '0040021'
    assert c.get('/api/profile/40021').status_code == 404
    big = F.CASES['fid_beyond_js_safe_int']       # > 2^53: string end to end
    j = c.get(f'/api/profile/{big}').json
    assert j['fid'] == '90071992547409931' and isinstance(j['fid'], str)
    r = c.put(f'/api/events/ministry/current/application/{big}', json={'profile': {}, 'answers': {}})
    assert r.status_code == 200 and r.json['application']['fid'] == '90071992547409931'
    for fid in (lead, big):
        r = c.put(f'/api/profile/{fid}', json={'timezone': 'UTC'})
        assert r.status_code == 200 and r.json['created'] is False

    # admin application edit of a legacy row updates by id (no fork, no 'game_name is required')
    apps = {a['fid']: a for a in c.get(f'/api/admin/rounds/{rid}/applications', headers=h).json['applications']}
    r = c.put(f'/api/admin/applications/{apps[ws.strip()]["id"]}', json={'answers': {'general_speedups_days': 3}},
              headers=h)
    assert r.status_code == 200, r.json
    assert len(c.get(f'/api/admin/rounds/{rid}/applications', headers=h).json['applications']) == n_apps
    assert len(c.get('/api/admin/profiles', headers=h).json['profiles']) == n_profiles
    assert c.delete('/api/admin/profiles/330000777%20', headers=h).status_code == 200


def test_non_digit_legacy_fid_can_resubmit(tmp_path):
    p = str(tmp_path / 'm.db')
    make_v14_db(p)  # contains FID 'legacy-fid-9'
    c = build_app(p).test_client()
    h = _admin(c)
    r = c.put('/api/events/ministry/current/application/legacy-fid-9',
              json={'profile': {'game_name': 'OddFid', 'alliance': 'ODD'}, 'answers': {'research_speedups_days': 4}})
    assert r.status_code == 200 and r.json['created'] is False, r.json
    assert c.put('/api/profile/legacy-fid-9', json={'timezone': 'UTC'}).status_code == 200
    assert c.put('/api/admin/profiles/legacy-fid-9', json={'alliance': 'ODD'}, headers=h).status_code == 200
    # a NEW non-digit FID is still rejected
    r = c.put('/api/events/ministry/current/application/other-odd', json={'profile': {'game_name': 'x', 'alliance': 'Y'}})
    assert r.status_code == 400 and r.json['field'] == 'fid'
    assert c.put('/api/profile/abc', json={'game_name': 'x'}).status_code == 400


def test_trailing_space_collision_kept_and_both_reachable(tmp_path):
    p = str(tmp_path / 'm.db')
    make_v14_db(p)
    con = sqlite3.connect(p)
    con.execute("INSERT INTO players (id, fid, game_name) VALUES (20, '1001 ', 'Twin')")  # collides with '1001'
    con.commit()
    con.close()
    c = build_app(p).test_client()
    assert c.get('/api/profile/1001').json['game_name'] == 'PreAugust'
    assert c.get('/api/profile/1001%20').json['game_name'] == 'Twin'  # exact match first


def test_legacy_four_char_alliance_resubmits(tmp_path):
    p = _rich_legacy(tmp_path)
    app = build_app(p)
    c = app.test_client()
    h = _admin(c)
    fid = F.CASES['import_lowercase_long_tag']  # alliance 'love'
    prof = c.get(f'/api/profile/{fid}').json
    assert prof['alliance'] == 'love'
    for sent in ('love', 'LOVE', ' Love '):
        r = c.put(f'/api/events/ministry/current/application/{fid}',
                  json={'profile': {'game_name': prof['game_name'], 'alliance': sent}, 'answers': {}})
        assert r.status_code == 200, r.json
        assert r.json['profile']['alliance'] == 'love'  # kept exactly as v1.4 stored it
    r = c.put(f'/api/events/ministry/current/application/{fid}',
              json={'profile': {'alliance': 'lovely'}, 'answers': {}})
    assert r.status_code == 400 and r.json['field'] == 'profile.alliance'  # a NEW long tag is still rejected
    r = c.put(f'/api/events/ministry/current/application/{fid}', json={'profile': {'alliance': 'luv'}}, )
    assert r.status_code == 200 and r.json['profile']['alliance'] == 'LUV'
    rid = c.get('/api/events/ministry/current').json['id']
    assert len(c.get(f'/api/admin/rounds/{rid}/applications?alliance=luv', headers=h).json['applications']) == 1


def test_migration_sorts_prefs_and_logs_stats(tmp_path):
    p = _rich_legacy(tmp_path)
    res = core_db.migrate(p, allow_v14=True)
    s = res[1]
    assert (F.CASES['fid_trailing_space'], F.CASES['fid_trailing_space'].strip()) in [tuple(x) for x in s['fids_trimmed']]
    assert F.CASES['real_in_integer_column'] in s['fractional_crystal_fids']
    con = sqlite3.connect(p)
    for (answers,) in con.execute('SELECT answers FROM applications'):
        for slots in json.loads(answers)['time_slots_by_day'].values():
            assert slots == sorted(slots)
    con.close()


# ---------------------------------------------------------------- guard views / triggers

def test_guard_views_and_settings_trigger(tmp_path):
    p = str(tmp_path / 'm.db')
    make_v14_db(p)
    build_app(p)
    assert {'players', 'time_preferences', 'assignments', 'admin_users'} <= _tables(p, 'view')
    con = sqlite3.connect(p)
    with pytest.raises(sqlite3.OperationalError, match='view'):
        con.execute("INSERT INTO players (fid, game_name) VALUES ('1', 'x')")
    with pytest.raises(sqlite3.IntegrityError, match='v1.4 is retired'):
        con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('research_day', 'friday')")
    con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('state_number', '2807')")  # v2 keys fine
    con.close()
    # fresh v2 databases get the guards too
    q = str(tmp_path / 'fresh.db')
    build_app(q, migrate_v14=False)
    assert 'players' in _tables(q, 'view')


def test_ghost_table_written_by_v14_after_import_is_refused(tmp_path):
    p = str(tmp_path / 'm.db')
    make_v14_db(p)
    core_db.migrate(p, allow_v14=True)
    con = sqlite3.connect(p)  # simulate a DB migrated before the guards existed, then written by v1.4
    con.execute('DROP VIEW players')
    con.execute('DELETE FROM schema_version WHERE version >= 2')  # migration 3 is idempotent
    con.execute('CREATE TABLE players (id INTEGER PRIMARY KEY, fid TEXT, game_name TEXT, '
                'construction_speedups_days REAL)')
    con.execute("INSERT INTO players (fid, game_name) VALUES ('555', 'lost write')")
    con.commit()
    con.close()
    with pytest.raises(core_db.LegacyDatabaseError, match='written by a v1.4 instance'):
        core_db.migrate(p)
    con = sqlite3.connect(p)
    con.execute('DELETE FROM players')
    con.commit()
    con.close()
    core_db.migrate(p)  # empty ghost table: dropped and replaced by the guard view
    assert 'players' in _tables(p, 'view') and 'players' not in _tables(p)


def _v14_source(dest):
    try:
        for f in ('app.py', 'database.py'):
            src = subprocess.run(['git', '-C', REPO, 'show', f'{V14_COMMIT}:backend/{f}'], capture_output=True,
                                 text=True, check=True).stdout
            with open(os.path.join(dest, f), 'w') as fh:
                fh.write(src)
    except (OSError, subprocess.CalledProcessError) as e:
        pytest.skip(f'v1.4 source not available via git: {e}')


V14_RUNNER = textwrap.dedent('''
    import json, logging, os, sys, types
    m = types.ModuleType('dotenv'); m.load_dotenv = lambda *a, **k: None; sys.modules['dotenv'] = m
    logging.disable(logging.CRITICAL)
    os.environ['DATABASE_PATH'] = sys.argv[1]
    sys.path.insert(0, sys.argv[2])
    out = {}
    try:
        import app  # v1.4: init_db() runs at import
        out['boot'] = 'ok'
    except Exception as e:
        out['boot'] = f'{type(e).__name__}: {e}'
        import database  # bypass init_db to prove the WRITES fail too
        database.init_db = lambda a: a.teardown_appcontext(database.close_db)
        sys.modules.pop('app', None)
        import app
    c = app.app.test_client()
    r = c.post('/api/player/submit', json={'fid': '555000111', 'game_name': 'Late v1.4 user', 'alliance': 'OLD',
               'time_slots': ['10:00']})
    out['submit'] = r.status_code
    r = c.put('/api/admin/settings/research-day', json={'research_day': 'friday'},
              headers={'Authorization': 'admin-token'})
    out['settings'] = r.status_code
    print(json.dumps(out))
''')


@pytest.mark.parametrize('legacy', [True, False])
def test_stray_v14_instance_fails_loudly(tmp_path, legacy):
    """Run the real v1.4 code (git show 5454016) against a migrated DB: it must not write anywhere."""
    old = tmp_path / 'v14'
    old.mkdir()
    _v14_source(str(old))
    p = str(tmp_path / 'm.db')
    if legacy:
        make_v14_db(p)
    build_app(p, migrate_v14=legacy)
    before = {t: sqlite3.connect(p).execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
              for t in ('profiles', 'applications', 'settings')}
    r = subprocess.run([sys.executable, '-c', V14_RUNNER, p, str(old)], capture_output=True, text=True,
                       timeout=120, cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out['boot'] != 'ok'                 # v1.4 cannot even start ...
    assert out['submit'] >= 500                # ... and its writes fail instead of landing in ghost tables
    assert out['settings'] >= 500
    assert 'players' not in _tables(p) and 'players' in _tables(p, 'view')
    con = sqlite3.connect(p)
    after = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in before}
    assert con.execute("SELECT COUNT(*) FROM settings WHERE key = 'research_day'").fetchone()[0] == 0
    con.close()
    assert after == before
