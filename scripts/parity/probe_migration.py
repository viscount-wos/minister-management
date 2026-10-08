#!/usr/bin/env python3
"""Migration / edge-case probes used for docs/REVIEW-phase1.md (reviewer evidence, not a test suite).

Run with the backend venv:  <venv>/bin/python scripts/parity/probe_migration.py
Each probe prints PROBE <name>: <observation>. Nothing outside a temp dir is touched.
"""
import glob
import multiprocessing as mp
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import types
import logging

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
BACKEND = os.path.join(REPO, 'backend')
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, 'tests', 'fixtures'))
_m = types.ModuleType('dotenv')
_m.load_dotenv = lambda *a, **k: None
sys.modules['dotenv'] = _m
logging.disable(logging.CRITICAL)

import make_legacy_db as F  # noqa: E402
from core import db as coredb  # noqa: E402


def fresh(tmp, name='legacy.db', **kw):
    p = os.path.join(tmp, name)
    F.build_legacy_db(p, force=True, **kw)
    return p


def counts(p):
    c = sqlite3.connect(p)
    t = [r[0] for r in c.execute("select name from sqlite_master where type='table' order by name")]
    out = {x: c.execute(f'select count(*) from "{x}"').fetchone()[0] for x in t if x != 'sqlite_sequence'}
    c.close()
    return out


def _race_worker(path, barrier, q):
    sys.modules['dotenv'] = _m
    barrier.wait()
    try:
        q.put(('ok', str(coredb.migrate(path))[:200]))
    except Exception as e:  # noqa: BLE001
        q.put(('error', f'{type(e).__name__}: {e}'))


def probe_race(tmp):
    p = fresh(tmp, 'race.db', players=1500, seed=5)
    ctx = mp.get_context('fork')
    barrier, q = ctx.Barrier(2), ctx.Queue()
    procs = [ctx.Process(target=_race_worker, args=(p, barrier, q)) for _ in range(2)]
    [x.start() for x in procs]
    [x.join(120) for x in procs]
    res = [q.get() for _ in procs]
    c = counts(p)
    baks = glob.glob(p + '.pre-v2-*.bak')
    print(f'PROBE two_instances_migrate_at_once: results={res}; rounds={c.get("rounds")} '
          f'applications={c.get("applications")} schema_version={c.get("schema_version")} backups={len(baks)}')


def probe_fail_halfway(tmp):
    p = fresh(tmp, 'fail.db')
    before = counts(p)
    orig = coredb._import_v14

    def boom(conn):
        orig(conn)
        raise RuntimeError('simulated crash after import, before COMMIT')
    coredb._import_v14 = boom
    try:
        coredb.migrate(p)
        print('PROBE fail_halfway: no exception?!')
    except RuntimeError:
        pass
    finally:
        coredb._import_v14 = orig
    after = counts(p)
    extra = {k: v for k, v in after.items() if k not in before}
    same = {k: v for k, v in after.items() if k in before} == before
    baks = glob.glob(p + '.pre-v2-*.bak')
    print(f'PROBE fail_halfway: v1.4 tables+rows unchanged={same}; extra tables={extra} '
          f'(schema_version is created before the migration transaction); backups left={len(baks)}')
    coredb.migrate(p)
    c2 = counts(p)
    coredb.migrate(p)
    c3 = counts(p)
    print(f'PROBE rerun_after_failure: migrated rounds={c2.get("rounds")} apps={c2.get("applications")}; '
          f'second rerun no-op={c2 == c3}; backups now={len(glob.glob(p + ".pre-v2-*.bak"))}')


def probe_old_revision_after_migration(tmp):
    """Cloud Run rollout: an old v1.4 instance (re)starts against the already-migrated file."""
    p = fresh(tmp, 'mixed.db')
    coredb.migrate(p)
    old_dir = os.path.join(tmp, 'v14')
    os.makedirs(old_dir, exist_ok=True)
    for f in ('app.py', 'database.py'):
        src = subprocess.run(['git', '-C', REPO, 'show', f'5454016:backend/{f}'], capture_output=True, text=True,
                             check=True).stdout
        open(os.path.join(old_dir, f), 'w').write(src)
    code = f'''
import sys, types, os, logging
m = types.ModuleType('dotenv'); m.load_dotenv = lambda *a, **k: None; sys.modules['dotenv'] = m
logging.disable(logging.CRITICAL)
os.environ['DATABASE_PATH'] = {p!r}
sys.path.insert(0, {old_dir!r})
import app
c = app.app.test_client()
r = c.post('/api/player/submit', json={{'fid': '555000111', 'game_name': 'Late v1.4 user', 'alliance': 'OLD',
           'time_slots': ['10:00']}})
print('v1.4 submit status', r.status_code)
print('v1.4 sees players:', len(c.get('/api/admin/players', headers={{'Authorization': 'admin-token'}}).json))
'''
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, cwd=tmp)
    c = counts(p)
    print(f'PROBE old_v14_revision_on_migrated_db: {r.stdout.strip()!r} {r.stderr.strip()[-200:]!r}; '
          f'tables now: players={c.get("players")} legacy_players={c.get("legacy_players")} '
          f'profiles={c.get("profiles")} settings={c.get("settings")}')
    coredb.migrate(p)
    con = sqlite3.connect(p)
    lost = con.execute("select count(*) from players").fetchone()[0]
    inprof = con.execute("select count(*) from profiles where fid='555000111'").fetchone()[0]
    print(f'PROBE ...then new app restarts: migrate() no-op; v1.4 write visible in v2 profiles={inprof}, '
          f'stranded in recreated v1.4 players table={lost}')


def probe_fid_and_admin_edit(tmp):
    p = fresh(tmp, 'fid.db')
    from app import create_app
    app = create_app({'DATABASE_PATH': p, 'SECRET_KEY': 'probe-key-xxxxxxxxxxxxxxxxxxxxxxxx', 'ADMIN_PASSWORD': 'a',
                      'MINISTER_PASSWORD': 'm', 'STATIC_DIR': '/nonexistent'})
    c = app.test_client()
    h = {'Authorization': 'Bearer ' + c.post('/api/admin/login', json={'password': 'a'}).json['token']}
    rid = c.get('/api/events/ministry/current').json['id']
    apps = {a['fid']: a for a in c.get(f'/api/admin/rounds/{rid}/applications', headers=h).json['applications']}
    ws = F.CASES['fid_trailing_space']
    a = apps[ws]
    r = c.put(f'/api/admin/applications/{a["id"]}', json={'answers': {'general_speedups_days': 3}}, headers=h)
    print(f'PROBE admin_edit_trailing_space_fid_application: {r.status_code} {r.json}')
    r = c.get('/api/admin/profiles/330000777%20', headers=h)
    print(f'PROBE admin_get_profile_trailing_space: {r.status_code}')
    r = c.delete('/api/admin/profiles/330000777%20', headers=h)
    print(f'PROBE admin_delete_profile_trailing_space: {r.status_code}')
    tag = apps[F.CASES['import_lowercase_long_tag']]
    r = c.put(f'/api/admin/applications/{tag["id"]}', json={'answers': {'general_speedups_days': 3}}, headers=h)
    print(f"PROBE admin_edit_answers_only_for_alliance_love: {r.status_code}")
    r = c.put(f'/api/admin/applications/{tag["id"]}', json={'profile': {'alliance': 'love'}}, headers=h)
    print(f"PROBE admin_resave_alliance_love: {r.status_code} {r.json.get('error')}")
    # public write with only an FID: rename someone who is on the published schedule
    pub = c.get('/api/events/ministry/current/schedule/monday').json
    slot, people = next(iter(pub['assignments'].items()))
    victim = next(x for x in apps.values() if x['profile']['game_name'] == people[0]['game_name'])
    r = c.put(f'/api/profile/{victim["fid"]}', json={'game_name': 'renamed by a stranger'})
    after = c.get('/api/events/ministry/current/schedule/monday').json['assignments'][slot][0]['game_name']
    print(f'PROBE stranger_renames_published_player: PUT {r.status_code}; public schedule now shows {after!r}')
    r = c.get(f'/api/profile/{victim["fid"]}')
    print(f'PROBE public_profile_fields: {sorted(r.json)}')
    r = c.get(f'/api/events/ministry/current/application/{victim["fid"]}')
    print(f'PROBE public_application_fields: {sorted(r.json)} answers={sorted(r.json["answers"])}')
    # unpublished days visible to anyone with an FID
    r = c.get(f'/api/events/ministry/current/assignments/{victim["fid"]}')
    print(f'PROBE public_assignments_incl_unpublished: published={r.json["published_days"]} '
          f'days_returned={sorted(r.json["assignments"])}')
    # Excel formula injection
    import io
    import openpyxl
    x = c.get(f'/api/admin/rounds/{rid}/export', headers=h)
    wb = openpyxl.load_workbook(io.BytesIO(x.data))
    f = [(ws_.title, cell.coordinate, cell.value) for ws_ in wb.worksheets for row in ws_.iter_rows()
         for cell in row if cell.data_type == 'f']
    print(f'PROBE xlsx_formula_cells: {f[:3]} (total {len(f)})')


def probe_closing_time(tmp):
    p = os.path.join(tmp, 'close.db')
    from app import create_app
    app = create_app({'DATABASE_PATH': p, 'SECRET_KEY': 'probe-key-xxxxxxxxxxxxxxxxxxxxxxxx', 'ADMIN_PASSWORD': 'a',
                      'MINISTER_PASSWORD': 'm', 'STATIC_DIR': '/nonexistent'})
    c = app.test_client()
    h = {'Authorization': 'Bearer ' + c.post('/api/admin/login', json={'password': 'a'}).json['token']}
    for ct in ('2026-10-12T20:00:00+02:00', '2026-10-12T18:00', '2026-10-12 18:00:00', '12/10/2026 18:00', 1760292000,
               '2026-10-12T18:00:00.999Z'):
        r = c.post('/api/admin/events/ministry/start-new-round', json={'name': 'x', 'closing_time': ct}, headers=h)
        print(f'PROBE closing_time_input {ct!r}: {r.status_code} -> '
              f'{(r.json.get("round") or {}).get("closing_time") if r.status_code == 201 else r.json.get("error")}')


if __name__ == '__main__':
    tmp = tempfile.mkdtemp(prefix='wos-probe-')
    try:
        probe_fail_halfway(tmp)
        probe_race(tmp)
        probe_old_revision_after_migration(tmp)
        probe_fid_and_admin_edit(tmp)
        probe_closing_time(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
