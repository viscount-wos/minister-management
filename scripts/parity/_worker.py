"""Parity worker: drives ONE app (v1.4 'old' or phase-1 'new') through a fixed script of
ministry operations via Flask's test_client and dumps normalised results as JSON.

Run by run_parity.py in a subprocess (one interpreter per app: both apps are called
``app.py`` and must not share sys.modules). Not meant to be run by hand, but you can:

    venv/bin/python _worker.py --side new --db /tmp/x.db --backend ../../backend --out /tmp/new.json

Sides:
  old         v1.4 (commit 5454016) exactly as live; preference walk follows set hash order
  old_sorted  v1.4 with ONE shim: sets iterate in sorted order. This is the documented
              phase-1 deviation ("auto-assign walks a player's preferences in sorted order"),
              so old_sorted is the parity ORACLE for the new app.
  new         phase-1 backend (this branch), on a DB migrated from the same v1.4 file
"""
import argparse
import io
import json
import logging
import os
import sqlite3
import sys
import types
from urllib.parse import quote

ADMIN_PW = 'parity-admin-pw'
MINISTER_PW = 'parity-minister-pw'
CARD_KEYS = ('player_id', 'fid', 'game_name', 'points', 'alliance', 'avatar_image', 'stove_lv',
             'stove_lv_content', 'is_sticky')
NEW_FID_1 = '123456789012'
NEW_FID_2 = '123456789013'


def _no_dotenv():
    # Neither app may read a stray .env from a parent directory (e.g. ~/.hermes/.env).
    mod = types.ModuleType('dotenv')
    mod.load_dotenv = lambda *a, **k: False
    sys.modules['dotenv'] = mod


class _SortedIterSet(set):
    """set whose iteration order is sorted: emulates the documented deterministic pref order."""

    def __iter__(self):
        return iter(sorted(set.__iter__(self)))


def generate_time_slots(scheme):
    if scheme == 'exact_alignment':
        return [f'{h:02d}:{m:02d}' for h in range(24) for m in (0, 30)]
    slots = ['23:50']
    for h in range(24):
        for m in (20, 50):
            slots.append('23:50+' if (h, m) == (23, 50) else f'{h:02d}:{m:02d}')
    return slots


def norm_card(c):
    out = {k: c.get(k) for k in CARD_KEYS}
    out['player_id'] = c.get('player_id', c.get('id'))
    out['is_sticky'] = bool(c.get('is_sticky'))
    out['preferred_times'] = c.get('preferred_times')  # None when the key is absent
    return out


def norm_assignments(body):
    slots = {s: [norm_card(c) for c in ps] for s, ps in (body.get('assignments') or {}).items()}
    return {'slots': slots, 'unassigned': [norm_card(c) for c in body.get('unassigned') or []]}


def parse_xlsx(data):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data))
    out = {}
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        out[ws.title] = {'header': rows[0] if rows else [], 'rows': rows[1:]}
    return {'sheets': list(out), 'content': out}


# ------------------------------------------------------------------ adapters

class OldAdapter:
    def __init__(self, db, old_dir, sorted_sets):
        os.environ['DATABASE_PATH'] = db
        os.environ['ADMIN_PASSWORD'] = ADMIN_PW
        os.environ['MINISTER_PASSWORD'] = MINISTER_PW
        os.environ['SECRET_KEY'] = 'parity-old-secret'
        os.environ.pop('FLASK_ENV', None)
        sys.path.insert(0, old_dir)
        import app as old_app  # noqa: E402  (v1.4 module)
        if sorted_sets:
            old_app.set = _SortedIterSet  # module global shadows the builtin
        self.mod = old_app
        self.c = old_app.app.test_client()
        r = self.c.post('/api/admin/login', json={'password': ADMIN_PW})
        assert r.status_code == 200, r.data
        self.h = {'Authorization': f'Bearer {r.json["token"]}'}
        self.db = db

    def _s(self, key, default):
        con = sqlite3.connect(self.db)
        row = con.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
        con.close()
        return row[0] if row else default

    def research_day(self):
        return self._s('research_day', 'tuesday')

    def scheme(self):
        s = self._s('time_slot_scheme', 'exact_alignment')
        return s if s in ('exact_alignment', 'max_slots') else 'exact_alignment'

    def points(self):
        r = self.c.get('/api/admin/players', headers=self.h)
        assert r.status_code == 200, r.data
        return {p['fid']: [p['monday_points'], p['research_points'], p['thursday_points']] for p in r.json}

    def player_count(self):
        return len(self.c.get('/api/admin/players', headers=self.h).json)

    def heatmap(self):
        return self.c.get('/api/time-preferences/heatmap').json

    def orphan_prefs(self):
        con = sqlite3.connect(self.db)
        rows = con.execute('SELECT day_type, time_slot, COUNT(*) FROM time_preferences WHERE player_id NOT IN '
                           '(SELECT id FROM players) GROUP BY day_type, time_slot').fetchall()
        con.close()
        return [list(r) for r in rows]

    def orphan_assignment_rows(self):
        con = sqlite3.connect(self.db)
        n = con.execute('SELECT COUNT(*) FROM assignments WHERE player_id NOT IN (SELECT id FROM players)').fetchone()[0]
        con.close()
        return n

    def get_assignments(self, day):
        r = self.c.get(f'/api/admin/assignments/{day}', headers=self.h)
        assert r.status_code == 200, r.data
        return norm_assignments(r.json)

    def auto_assign(self, day):
        r = self.c.post('/api/admin/assignments/auto-assign', json={'day': day}, headers=self.h)
        assert r.status_code == 200, r.data
        return norm_assignments(r.json)

    def update_assignments(self, day, mapping):
        body = {'day': day, 'assignments': {s: [{'player_id': pid, 'is_sticky': st, 'is_assigned': True}]
                                            for s, (pid, st) in mapping.items()}}
        r = self.c.post('/api/admin/assignments/update', json=body, headers=self.h)
        return r.status_code

    def schedule(self, day):
        j = self.c.get(f'/api/published-schedule/{day}').json
        return j

    def published_days(self):
        return self.c.get('/api/settings/published-days').json['published_days']

    def publish(self, day, on):
        url = '/api/admin/settings/publish' if on else '/api/admin/settings/unpublish'
        r = self.c.put(url, json={'day': day}, headers=self.h)
        return r.status_code, r.json.get('published_days')

    def player_assignments(self, fid):
        r = self.c.get(f'/api/player/{quote(fid, safe="")}/assignments')
        return r.status_code, (r.json.get('assignments') if r.status_code == 200 else None)

    def export_json(self):
        r = self.c.get('/api/admin/players/export-json', headers=self.h)
        return json.loads(r.data)['players']

    def export_xlsx(self):
        r = self.c.get('/api/admin/export', headers=self.h)
        assert r.status_code == 200, r.data[:200]
        return parse_xlsx(r.data)

    def set_scheme(self, scheme):
        r = self.c.put('/api/admin/settings/time-slot-scheme', json={'time_slot_scheme': scheme}, headers=self.h)
        return r.json.get('remapped')

    def set_closing(self, iso):
        r = self.c.put('/api/admin/settings/application-closing-time', json={'closing_time': iso}, headers=self.h)
        assert r.status_code == 200, r.data

    def resync_boundary_after_remap(self):
        """Oracle emulation of the documented L3 fix (milestone 1c): after a scheme switch the new app
        mirrors the shared 23:50 boundary (from the earlier day if occupied, else from the later day).
        In v1.4 that is exactly what re-saving that day unchanged does (its save syncs the boundary)."""
        if self.scheme() != 'max_slots':
            return
        rd = self.research_day()
        earlier, later = ('monday', 'tuesday') if rd == 'tuesday' else ('thursday', 'friday')
        if self.get_assignments(earlier)['slots'].get('23:50+'):
            day = earlier
        elif self.get_assignments(later)['slots'].get('23:50'):
            day = later
        else:
            return
        cur = self.get_assignments(day)['slots']
        self.update_assignments(day, {s: (cs[0]['player_id'], cs[0]['is_sticky']) for s, cs in cur.items() if cs})

    def submit(self, fid, entry):
        body = {'fid': fid, 'game_name': entry.get('game_name'), 'alliance': entry.get('alliance') or '',
                'timezone': entry.get('timezone')}
        for k in ('construction_speedups_days', 'research_speedups_days', 'troop_training_speedups_days',
                  'general_speedups_days', 'fire_crystals', 'refined_fire_crystals', 'fire_crystal_shards'):
            body[k] = entry.get(k, 0)
        body['time_slots_by_day'] = entry.get('time_slots_by_day') or {}
        return self.c.post('/api/player/submit', json=body).status_code

    def lookup(self, fid):
        return self.c.get(f'/api/player/{quote(fid, safe="")}').status_code


class NewAdapter:
    def __init__(self, db, backend_dir):
        os.environ.pop('FLASK_ENV', None)
        sys.path.insert(0, backend_dir)
        from app import create_app  # noqa: E402  (phase-1 module)
        # The v1.4 import is explicit since milestone 1c (a normal boot refuses a v1.4 file):
        # run it the way the cut-over runbook does, then boot normally.
        from core.db import migrate  # noqa: E402
        migrate(db, allow_v14=True)
        self.app = create_app({'DATABASE_PATH': db, 'SECRET_KEY': 'parity-new-secret-not-placeholder',
                               'ADMIN_PASSWORD': ADMIN_PW, 'MINISTER_PASSWORD': MINISTER_PW,
                               'STATIC_DIR': '/nonexistent', 'TESTING': True})
        self.c = self.app.test_client()
        r = self.c.post('/api/admin/login', json={'password': ADMIN_PW})
        assert r.status_code == 200, r.data
        self.h = {'Authorization': f'Bearer {r.json["token"]}'}
        self.db = db
        self._round()
        if os.environ.get('PARITY_MUTATION') == 'shared_winner':
            # --self-test only: break the shared 23:50 rule at runtime to prove the harness notices
            from events.ministry import logic
            orig = logic.compute_shared_winner

            def lowest(players, earlier, later, rd):
                w = orig(players, earlier, later, rd)
                cands = [p for p in players if '_combined' in p]
                return min(cands, key=lambda p: p['_combined']) if w and cands else w
            logic.compute_shared_winner = lowest

    def _round(self):
        r = self.c.get('/api/events/ministry/current')
        assert r.status_code == 200, r.data
        self.round = r.json
        return self.round

    def research_day(self):
        return self._round()['settings']['research_day']

    def scheme(self):
        return self._round()['settings']['time_slot_scheme']

    def _apps(self):
        r = self.c.get(f'/api/admin/rounds/{self.round["id"]}/applications', headers=self.h)
        assert r.status_code == 200, r.data
        return r.json['applications']

    def points(self):
        return {a['fid']: [a['monday_points'], a['research_points'], a['thursday_points']] for a in self._apps()}

    def player_count(self):
        return len(self._apps())

    def heatmap(self):
        return self.c.get('/api/events/ministry/current/heatmap').json

    def get_assignments(self, day):
        r = self.c.get(f'/api/admin/ministry/rounds/current/assignments/{day}', headers=self.h)
        assert r.status_code == 200, r.data
        return norm_assignments(r.json)

    def auto_assign(self, day):
        r = self.c.post('/api/admin/ministry/rounds/current/auto-assign', json={'day': day}, headers=self.h)
        assert r.status_code == 200, r.data
        return norm_assignments(r.json)

    def update_assignments(self, day, mapping):
        body = {'assignments': {s: [{'player_id': pid, 'is_sticky': st, 'is_assigned': True}]
                                for s, (pid, st) in mapping.items()}}
        r = self.c.put(f'/api/admin/ministry/rounds/current/assignments/{day}', json=body, headers=self.h)
        return r.status_code

    def schedule(self, day):
        j = dict(self.c.get(f'/api/events/ministry/current/schedule/{day}').json)
        j.pop('round_id', None)
        return j

    def published_days(self):
        return self.c.get('/api/events/ministry/current/schedule').json['published_days']

    def publish(self, day, on):
        url = 'publish' if on else 'unpublish'
        r = self.c.post(f'/api/admin/ministry/rounds/current/{url}', json={'day': day}, headers=self.h)
        return r.status_code, r.json.get('published_days')

    def player_assignments(self, fid):
        r = self.c.get(f'/api/events/ministry/current/assignments/{quote(fid, safe="")}')
        return r.status_code, (r.json.get('assignments') if r.status_code == 200 else None)

    def export_json(self):
        r = self.c.get('/api/admin/ministry/rounds/current/export-json', headers=self.h)
        return json.loads(r.data)['players']

    def export_xlsx(self):
        r = self.c.get(f'/api/admin/rounds/{self.round["id"]}/export', headers=self.h)
        assert r.status_code == 200, r.data[:200]
        return parse_xlsx(r.data)

    def set_scheme(self, scheme):
        r = self.c.put(f'/api/admin/rounds/{self.round["id"]}', json={'settings': {'time_slot_scheme': scheme}},
                       headers=self.h)
        assert r.status_code == 200, r.data
        return r.json.get('remapped')

    def set_closing(self, iso):
        r = self.c.put(f'/api/admin/rounds/{self.round["id"]}', json={'closing_time': iso}, headers=self.h)
        assert r.status_code == 200, r.data

    def submit(self, fid, entry):
        answers = {k: entry.get(k, 0) for k in (
            'construction_speedups_days', 'research_speedups_days', 'troop_training_speedups_days',
            'general_speedups_days', 'fire_crystals', 'refined_fire_crystals', 'fire_crystal_shards')}
        answers['time_slots_by_day'] = entry.get('time_slots_by_day') or {}
        body = {'profile': {'game_name': entry.get('game_name'), 'alliance': entry.get('alliance') or '',
                            'timezone': entry.get('timezone') or None},
                'answers': answers}
        r = self.c.put(f'/api/events/ministry/current/application/{quote(fid, safe="")}', json=body)
        return 200 if r.status_code in (200, 201) else r.status_code

    def lookup(self, fid):
        return self.c.get(f'/api/profile/{quote(fid, safe="")}').status_code


# ------------------------------------------------------------------ script

def run(ad, cases):
    steps = []

    def rec(name, kind, data):
        steps.append({'name': name, 'kind': kind, 'data': data})

    rd = ad.research_day()
    days = ['monday', rd, 'thursday']
    linked = None
    if ad.scheme() == 'max_slots':
        linked = ('monday', 'tuesday') if rd == 'tuesday' else ('thursday', 'friday')
    all_fids = [p['fid'] for p in ad.export_json()]
    rec('meta', 'meta', {'research_day': rd, 'scheme': ad.scheme(), 'players': len(all_fids)})

    def boundary(tag):
        if not linked:
            return
        e = ad.get_assignments(linked[0])['slots'].get('23:50+') or []
        l_ = ad.get_assignments(linked[1])['slots'].get('23:50') or []
        rec(f'{tag}:shared_23:50', 'shared',
            {'earlier': [c['player_id'] for c in e], 'later': [c['player_id'] for c in l_]})

    def snapshot(tag, full=True):
        for d in days:
            rec(f'{tag}:get_assignments:{d}', 'assignments', ad.get_assignments(d))
        for d in ('monday', 'tuesday', 'thursday', 'friday'):
            rec(f'{tag}:schedule:{d}', 'schedule', ad.schedule(d))
        rec(f'{tag}:published_days', 'plain', ad.published_days())
        if full:
            pa = {fid: ad.player_assignments(fid) for fid in all_fids}
            pa['__published__'] = ad.published_days()
            rec(f'{tag}:player_assignments', 'player_assignments', pa)
            rec(f'{tag}:xlsx', 'xlsx', ad.export_xlsx())
        boundary(tag)

    def sticky_rows(day):
        a = ad.get_assignments(day)
        grid = set(generate_time_slots(ad.scheme()))
        return sorted([s, c['player_id']] for s, cs in a['slots'].items() for c in cs if c['is_sticky'] and s in grid)

    def auto_all(tag):
        for d in days:
            before = sticky_rows(d)
            res = ad.auto_assign(d)
            rec(f'{tag}:auto_assign:{d}', 'assignments', res)
            placed = {(s, c['player_id']) for s, cs in res['slots'].items() for c in cs if c['is_sticky']}
            missing = [r for r in before if tuple(r) not in placed]
            # a sticky row on a linked day may legitimately be replaced by the mirror of the other day
            rec(f'{tag}:sticky_kept:{d}', 'sticky', {'before': before, 'missing': missing})

    # S0: straight after migration
    rec('S0:points', 'points', ad.points())
    hm = ad.heatmap()
    if isinstance(ad, OldAdapter):
        hm = {'heatmap': hm, 'orphans': ad.orphan_prefs()}
    else:
        hm = {'heatmap': hm, 'orphans': []}
    rec('S0:heatmap', 'heatmap', hm)
    rec('S0:export_json', 'export_json', ad.export_json())
    snapshot('S0')

    # S1: auto-assign every active day (sticky rows from v1.4 must survive)
    auto_all('S1')
    snapshot('S1')

    # S2: clear every sticky flag, re-run: exercises the shared 23:50 combined-score winner
    for d in days:
        cur = ad.get_assignments(d)['slots']
        mapping = {s: (cs[0]['player_id'], False) for s, cs in cur.items() if cs}
        rec(f'S2:unsticky_save:{d}', 'plain', ad.update_assignments(d, mapping))
    auto_all('S2')
    snapshot('S2', full=False)

    # S3: manual drag-and-drop saves
    pid_by_fid = {}
    for d in days:
        a = ad.get_assignments(d)
        for cs in list(a['slots'].values()) + [a['unassigned']]:
            for c in cs:
                pid_by_fid[c['fid']] = c['player_id']
    if linked:
        loser = pid_by_fid.get(cases['shared_slot_loser'])
        cur = ad.get_assignments(linked[0])['slots']
        mapping = {s: (cs[0]['player_id'], cs[0]['is_sticky']) for s, cs in cur.items()
                   if cs and cs[0]['player_id'] != loser and s != '23:50+'}
        mapping['23:50+'] = (loser, True)
        rec('S3:boundary_move_save', 'plain', ad.update_assignments(linked[0], mapping))
        rec(f'S3:get_assignments:{linked[1]}', 'assignments', ad.get_assignments(linked[1]))
    a = ad.get_assignments('thursday')
    if a['unassigned']:
        pick = sorted(a['unassigned'], key=lambda c: c['fid'])[0]['player_id']
        empty = [s for s in generate_time_slots(ad.scheme()) if not a['slots'].get(s)]
        mapping = {s: (cs[0]['player_id'], cs[0]['is_sticky']) for s, cs in a['slots'].items() if cs}
        if empty:
            mapping[empty[0]] = (pick, True)
        rec('S3:manual_sticky_save', 'plain', ad.update_assignments('thursday', mapping))
    auto_all('S3')
    snapshot('S3', full=False)

    # S4: publish / unpublish
    rec('S4:publish_thursday', 'plain', ad.publish('thursday', True))
    rec('S4:unpublish_monday', 'plain', ad.publish('monday', False))
    rec(f'S4:publish_{rd}', 'plain', ad.publish(rd, True))
    snapshot('S4')

    # S5: switch slot scheme -> best-effort remap of every stored assignment
    other = 'exact_alignment' if ad.scheme() == 'max_slots' else 'max_slots'
    orphans_before = ad.orphan_assignment_rows() if isinstance(ad, OldAdapter) else 0
    remapped = ad.set_scheme(other)
    orphans_after = ad.orphan_assignment_rows() if isinstance(ad, OldAdapter) else 0
    if isinstance(ad, OldAdapter):
        ad.resync_boundary_after_remap()  # documented deviation L3 applied to the oracle
    rec('S5:remap', 'remap', {'remapped': remapped, 'orphan_rows_before': orphans_before,
                              'orphan_rows_after': orphans_after})
    linked = None
    if ad.scheme() == 'max_slots':
        linked = ('monday', 'tuesday') if rd == 'tuesday' else ('thursday', 'friday')
    snapshot('S5', full=False)
    auto_all('S6')
    snapshot('S6')

    # S7: player-side edits / lookups / closing time (last: these may fork data)
    exp = {p['fid']: p for p in ad.export_json()}
    edit_cases = ['fid_leading_zero', 'fid_beyond_js_safe_int', 'import_lowercase_long_tag',
                  'real_in_integer_column', 'fid_trailing_space']
    rec('S7:lookup', 'plain', {c: ad.lookup(cases[c]) for c in edit_cases})
    statuses = {}
    for c in edit_cases:
        fid = cases[c]
        key = fid if fid in exp else fid.strip()  # the v1.4 import trims FID whitespace (documented)
        statuses[c] = ad.submit(fid, exp[key]) if key in exp else 'missing'
    statuses['brand_new'] = ad.submit(NEW_FID_1, {'game_name': 'Parity New', 'alliance': 'PAR',
                                                  'construction_speedups_days': 1,
                                                  'time_slots_by_day': {'construction': ['10:00']}})
    rec('S7:edit_status', 'plain', statuses)
    rec('S7:player_count', 'plain', ad.player_count())
    pts = ad.points()
    wanted = {cases[c] for c in edit_cases} | {cases[c].strip() for c in edit_cases} | {NEW_FID_1}
    rec('S7:points_after_edit', 'points', {k: v for k, v in pts.items() if k in wanted})
    ad.set_closing('2020-01-01T00:00:00.000Z')
    some = sorted(f for f in all_fids if f.isdigit() and len(f) == 9 and f in exp)[0]
    rec('S7:closed_status', 'plain', {
        'existing_edit': ad.submit(some, exp[some]),
        'brand_new': ad.submit(NEW_FID_2, {'game_name': 'Too Late', 'alliance': 'LAT'}),
        'just_created_edit': ad.submit(NEW_FID_1, {'game_name': 'Parity New', 'alliance': 'PAR'}),
    })
    rec('S7:player_count_closed', 'plain', ad.player_count())
    return steps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--side', choices=['old', 'old_sorted', 'new'], required=True)
    ap.add_argument('--db', required=True)
    ap.add_argument('--old-dir')
    ap.add_argument('--backend')
    ap.add_argument('--fixtures', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    _no_dotenv()
    logging.disable(logging.CRITICAL)
    sys.path.insert(0, a.fixtures)
    from make_legacy_db import CASES  # noqa: E402
    if a.side == 'new':
        ad = NewAdapter(a.db, a.backend)
    else:
        ad = OldAdapter(a.db, a.old_dir, sorted_sets=(a.side == 'old_sorted'))
    steps = run(ad, CASES)
    with open(a.out, 'w') as f:
        json.dump({'side': a.side, 'steps': steps}, f, default=str)


if __name__ == '__main__':
    main()
