"""Cross-check: migrate the rich v1.4 dummy DB with the new backend and compare counts.

Run: cd backend && venv/bin/python ../scripts/xcheck_migration.py
"""
import json, os, shutil, sqlite3, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(HERE, '..', 'backend')
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, 'tests', 'fixtures'))
import make_legacy_db as F  # noqa: E402

tmp = tempfile.mkdtemp()
src = os.path.join(tmp, 'legacy.db')
F.build_legacy_db(src, players=150, seed=2807) if 'players' in F.build_legacy_db.__code__.co_varnames else F.build_legacy_db(src)
before = sqlite3.connect(src)
q = lambda c, s: c.execute(s).fetchone()[0]
live_players = q(before, 'select count(*) from players')
prefs_live = q(before, 'select count(*) from time_preferences where player_id in (select id from players)')
asg_live = q(before, 'select count(*) from assignments where player_id in (select id from players)')
sticky_live = q(before, 'select count(*) from assignments where is_sticky=1 and player_id in (select id from players)')
settings_before = dict(before.execute('select key,value from settings').fetchall())
before.close()

db = os.path.join(tmp, 'app.db')
shutil.copy(src, db)
os.environ['DATABASE_PATH'] = db
os.environ.setdefault('SECRET_KEY', 'xcheck-secret')
os.environ.setdefault('ADMIN_PASSWORD', 'admin123')
from app import create_app  # noqa: E402
app = create_app()
c = sqlite3.connect(db)
c.row_factory = sqlite3.Row
tables = [r[0] for r in c.execute("select name from sqlite_master where type='table' order by name")]
print('tables:', tables)
def cnt(t):
    return q(c, f'select count(*) from {t}') if t in tables else None
prof = cnt('profiles')
apps = cnt('applications')
asg = cnt('ministry_assignments')
rounds = [dict(r) for r in c.execute('select * from rounds')]
print(json.dumps({'legacy_live_players': live_players, 'profiles': prof, 'applications': apps,
                  'legacy_assignments_live': asg_live, 'ministry_assignments': asg,
                  'legacy_sticky_live': sticky_live, 'legacy_prefs_live': prefs_live,
                  'rounds': len(rounds)}, indent=1))
print('round settings:', rounds[0]['settings'] if rounds else None, '| closing:', rounds[0].get('closing_time') if rounds else None)
print('settings before:', settings_before)
sticky_new = q(c, 'select count(*) from ministry_assignments where is_sticky=1') if asg is not None else None
print('sticky after:', sticky_new)

# awkward cases survive
for name, fid in F.CASES.items():
    r = c.execute('select fid, game_name from profiles where fid=?', (fid,)).fetchone()
    if r is None:
        print('  MISSING case', name, repr(fid))
# idempotence
h1 = q(c, 'select count(*) from applications')
c.close()
app2 = create_app()
c = sqlite3.connect(db)
print('rerun idempotent:', q(c, 'select count(*) from applications') == h1)

# API smoke on migrated data
cl = app.test_client()
tok = cl.post('/api/admin/login', json={'password': 'admin123'}).get_json()
print('login:', {k: v for k, v in tok.items() if k != 'token'})
H = {'Authorization': 'Bearer ' + tok['token']}
for path in ['/api/events', '/api/events/ministry/current',
             '/api/admin/ministry/rounds/current/assignments/monday',
             '/api/admin/ministry/rounds/current/assignments/thursday']:
    r = cl.get(path, headers=H)
    print(path, r.status_code, (r.get_data(as_text=True)[:120]).replace('\n', ' '))
print('forged token:', cl.get('/api/admin/profiles', headers={'Authorization': 'Bearer admin-token'}).status_code)

# time preferences preserved (stored in answers JSON)
n = 0
for (a,) in c.execute('select answers from applications'):
    d = json.loads(a).get('time_slots_by_day', {})
    n += sum(len(v) for v in d.values())
print('time prefs after:', n, 'before (live players):', prefs_live)
