#!/usr/bin/env python3
"""Ministry parity harness: v1.4 (live, commit 5454016) vs the phase-1 backend on the same dummy data.

For every scenario (seed x research day x slot scheme, plus "no stored scheme" variants):
  1. build a dummy v1.4 DB with backend/tests/fixtures/make_legacy_db.py
  2. run the OLD app (v1.4 app.py + database.py extracted with `git show`) on copies of it,
     and the NEW app on a copy that its own startup migration converts
  3. drive both through the same script (_worker.py) via Flask test_client: points, heatmap,
     assignments, auto-assign x3 days (twice, with and without sticky), manual saves incl. the
     shared 23:50 boundary, publish/unpublish, scheme switch remap, export-json, Excel export,
     player lookups/edits and the closing-time rule
  4. compare step by step and classify each difference.

Sides (each its own interpreter, see _worker.py):
  old         v1.4 exactly as live (pref walk in set-hash order; PYTHONHASHSEED fixed for reproducibility)
  old_sorted  v1.4 with sets iterating sorted = the documented deviation applied. THE ORACLE.
  old_int     old_sorted on a copy where REAL crystal values were cast to int (isolates that one
              known migration change so it does not cascade into every later step)
  new         phase-1 backend on a migrated copy

Classification (per step):
  OK          identical to the oracle
  EXPECTED    differs only in a way SPEC.md "Backend phase 1 deviations" / API.md documents
  BENIGN      differs only cosmetically and the change is NOT documented (doc gap, not a failure)
  REGRESSION  anything else. Exit code 1 if any.

Usage:
  python3 scripts/parity/run_parity.py [--quick] [--python VENV_PY] [--json report.json] [-v]
The default interpreter for the apps is $PARITY_PYTHON or the backend-core venv.
"""
import argparse
import copy
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
BACKEND = os.path.join(REPO, 'backend')
FIXTURES = os.path.join(BACKEND, 'tests', 'fixtures')
V14_COMMIT = '5454016'
DEFAULT_PY = os.environ.get('PARITY_PYTHON') or \
    '/home/bevans/ai/fun/wos/wos-events-wt/backend-core/backend/venv/bin/python'

OK, EXPECTED, BENIGN, REGRESSION = 'OK', 'EXPECTED', 'BENIGN', 'REGRESSION'
RANK = {OK: 0, EXPECTED: 1, BENIGN: 2, REGRESSION: 3}

sys.path.insert(0, FIXTURES)
import make_legacy_db as F  # noqa: E402  (stdlib only)

FID_WS = F.CASES['fid_trailing_space']
STR_FIELDS = ('alliance', 'avatar_image', 'stove_lv_content', 'timezone')


# ------------------------------------------------------------------ scenarios

def scenarios(quick=False):
    out = []
    seeds = [2807] if quick else [2807, 7, 42]
    for seed in seeds:
        for rd in ('tuesday', 'friday'):
            for scheme in ('max_slots', 'exact_alignment'):
                out.append({'name': f's{seed}-{rd[:3]}-{"max" if scheme == "max_slots" else "exact"}',
                            'seed': seed, 'research_day': rd, 'scheme': scheme, 'players': 150})
    if not quick:
        out.append({'name': 's99-fri-max-300p', 'seed': 99, 'research_day': 'friday', 'scheme': 'max_slots',
                    'players': 300})
        # v1.4 DB without a stored time_slot_scheme row (installs from before the setting existed)
        for scheme in ('max_slots', 'exact_alignment'):
            out.append({'name': f'noscheme-{"max" if scheme == "max_slots" else "exact"}', 'seed': 2807,
                        'research_day': 'tuesday', 'scheme': scheme, 'players': 150, 'drop_scheme_key': True})
    return out


def build(sc, workdir):
    legacy = os.path.join(workdir, 'legacy.db')
    F.build_legacy_db(legacy, players=sc['players'], seed=sc['seed'], research_day=sc['research_day'],
                      scheme=sc['scheme'], force=True)
    notes = []
    if sc.get('drop_scheme_key'):
        con = sqlite3.connect(legacy)
        con.execute("DELETE FROM settings WHERE key = 'time_slot_scheme'")
        con.commit()
        con.close()
    dbs = {}
    for side in ('old', 'old_sorted', 'old_int', 'new'):
        p = os.path.join(workdir, f'{side}.db')
        shutil.copy(legacy, p)
        dbs[side] = p
    if sc.get('drop_scheme_key'):
        # v1.4's init_db would pin max_slots at its next start because assignments exist; the
        # documented phase-1 rule infers the scheme from the stored slots instead (what a running
        # v1.4 without the key was actually using). The oracle follows the documented rule.
        inferred = sc['scheme']
        notes.append(f'EXPECTED: no stored scheme; v1.4 restart would pin max_slots, migration infers '
                     f'{inferred} from stored slots (documented). Oracle run with {inferred}.')
        for side in ('old', 'old_sorted', 'old_int'):
            con = sqlite3.connect(dbs[side])
            con.execute("INSERT INTO settings (key, value) VALUES ('time_slot_scheme', ?)", (inferred,))
            con.commit()
            con.close()
    con = sqlite3.connect(dbs['old_int'])
    for col in ('fire_crystals', 'refined_fire_crystals', 'fire_crystal_shards'):
        con.execute(f'UPDATE players SET {col} = CAST({col} AS INTEGER) WHERE typeof({col}) = \'real\'')
    con.commit()
    con.close()
    return dbs, notes


def run_worker(py, side, db, old_dir, out, mutation=None):
    real_side = 'old_sorted' if side == 'old_int' else side
    cmd = [py, os.path.join(HERE, '_worker.py'), '--side', real_side, '--db', db, '--fixtures', FIXTURES,
           '--out', out]
    if real_side == 'new':
        cmd += ['--backend', BACKEND]
    else:
        cmd += ['--old-dir', old_dir]
    env = {k: v for k, v in os.environ.items()
           if k not in ('FLASK_ENV', 'SECRET_KEY', 'ADMIN_PASSWORD', 'MINISTER_PASSWORD', 'DATABASE_PATH')}
    env['PYTHONHASHSEED'] = '0'
    if mutation and real_side == 'new':
        env['PARITY_MUTATION'] = mutation
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    r = subprocess.run(cmd, cwd=os.path.dirname(db), env=env, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        raise RuntimeError(f'{side} worker failed:\n{r.stderr[-4000:]}')
    with open(out) as f:
        return {s['name']: s for s in json.load(f)['steps']}


# ------------------------------------------------------------------ normalisers

def _nullstr_card(c):
    c = dict(c)
    for k in STR_FIELDS:
        if k in c and c[k] is None:
            c[k] = ''
    return c


def n_assign_null(o, n):
    f = lambda d: {'slots': {s: [_nullstr_card(c) for c in cs] for s, cs in d['slots'].items()},
                   'unassigned': [_nullstr_card(c) for c in d['unassigned']]}
    return f(o), f(n)


def n_assign_prefs(o, n):
    def f(d):
        drop = lambda c: {k: v for k, v in c.items() if k != 'preferred_times'}
        return {'slots': {s: [drop(c) for c in cs] for s, cs in d['slots'].items()},
                'unassigned': [drop(c) for c in d['unassigned']]}
    return f(o), f(n)


def n_assign_ties(o, n):
    def f(d):
        d = dict(d)
        d['unassigned'] = sorted(d['unassigned'], key=lambda c: (-(c['points'] or 0), c['player_id']))
        return d
    return f(o), f(n)


def n_export_null(o, n):
    f = lambda rows: [_nullstr_card(r) for r in rows]
    return f(o), f(n)


def n_export_pref_order(o, n):
    def f(rows):
        out = []
        for r in rows:
            r = dict(r)
            r['time_slots_by_day'] = {k: sorted(v) for k, v in (r.get('time_slots_by_day') or {}).items()}
            out.append(r)
        return out
    return f(o), f(n)


def n_export_order(o, n):
    return sorted(o, key=lambda r: r['fid']), sorted(n, key=lambda r: r['fid'])


def _cells(v):
    return '' if v is None else v


def xlsx_base(d):
    return {'sheets': d['sheets'],
            'content': {t: {'header': [_cells(c) for c in s['header']],
                            'rows': [[_cells(c) for c in r] for r in s['rows']]}
                        for t, s in d['content'].items()}}


def n_xlsx_unassigned_sheet(o, n):
    n = copy.deepcopy(n)
    if 'Unassigned' in n['sheets']:
        n['sheets'] = [s for s in n['sheets'] if s != 'Unassigned']
        n['content'].pop('Unassigned', None)
    return o, n


def n_xlsx_ties(o, n):
    def f(d):
        d = copy.deepcopy(d)
        for s in d['content'].values():
            rows = s['rows']
            if ['UNASSIGNED PLAYERS'] + [''] * 11 in rows:
                i = rows.index(['UNASSIGNED PLAYERS'] + [''] * 11)
                s['rows'] = rows[:i + 1] + sorted(rows[i + 1:], key=lambda r: (-(r[11] or 0), str(r[1])))
        return d
    return f(o), f(n)


def n_heat_orphans(o, n):
    hm = copy.deepcopy(o['heatmap'])
    for dt, slot, cnt in o['orphans']:
        if dt in hm and slot in hm[dt]:
            hm[dt][slot] -= cnt
            if hm[dt][slot] == 0:
                del hm[dt][slot]
    return {'heatmap': hm}, {'heatmap': n['heatmap']}


def n_schedule(o, n):
    n = dict(n)
    if not n.get('published'):
        n.pop('day', None)  # API.md: unpublished response also echoes the day
    return o, n


NORMALISERS = {
    'assignments': [("null alliance/avatar/stove_lv_content returned as '' instead of null on cards",
                     BENIGN, n_assign_null),
                    ("preferred_times = that day's own prefs (documented)", EXPECTED, n_assign_prefs),
                    ('order of equal-points players in unassigned list', BENIGN, n_assign_ties)],
    'export_json': [("null alliance/avatar/stove_lv_content/timezone exported as '' instead of null", BENIGN,
                     n_export_null),
                    ('order of hours inside time_slots_by_day lists (v1.4 read them via the unique index, i.e. '
                     'sorted; migration keeps insertion order)', BENIGN, n_export_pref_order),
                    ('player order', BENIGN, n_export_order)],
    'xlsx': [("extra 'Unassigned' summary sheet (documented)", EXPECTED, n_xlsx_unassigned_sheet),
             ('order of equal-points rows in the UNASSIGNED section', BENIGN, n_xlsx_ties)],
    'heatmap': [('v1.4 also counted time_preferences rows of deleted players (orphans); new counts '
                 'round applicants only', BENIGN, n_heat_orphans)],
    'schedule': [],
    'points': [], 'plain': [], 'shared': [], 'meta': [], 'player_assignments': [],
}
PRE = {'xlsx': xlsx_base, 'schedule': None}


def diff_summary(o, n, limit=4):
    out = []
    if isinstance(o, dict) and isinstance(n, dict):
        for k in sorted(set(o) | set(n), key=str):
            if o.get(k, '<missing>') != n.get(k, '<missing>'):
                out.append(f'{k}: old={_short(o.get(k, "<missing>"))} new={_short(n.get(k, "<missing>"))}')
    elif isinstance(o, list) and isinstance(n, list):
        if len(o) != len(n):
            out.append(f'len old={len(o)} new={len(n)}')
        for i, (a, b) in enumerate(zip(o, n)):
            if a != b:
                out.append(f'[{i}] old={_short(a)} new={_short(b)}')
    else:
        out.append(f'old={_short(o)} new={_short(n)}')
    return out[:limit] + ([f'... {len(out) - limit} more'] if len(out) > limit else [])


def _short(v, n=160):
    s = json.dumps(v, ensure_ascii=False, default=str) if not isinstance(v, str) else repr(v)
    return s if len(s) <= n else s[:n] + '...'


def compare(kind, o, n):
    """Return (status, [labels], diff) for oracle data o vs new data n."""
    pre = PRE.get(kind)
    if kind == 'schedule':
        o, n = n_schedule(o, n)
    elif pre:
        o, n = pre(o), pre(n)
    if o == n:
        return OK, [], []
    pipeline = list(NORMALISERS.get(kind, []))

    def run(items):
        a, b = o, n
        for _, _, fn in items:
            a, b = fn(a, b)
        return a, b

    a, b = run(pipeline)
    if a != b:
        return REGRESSION, [], diff_summary(a, b)
    needed = list(pipeline)
    for item in list(needed):  # keep only the normalisers that are actually required
        trial = [x for x in needed if x is not item]
        ta, tb = run(trial)
        if ta == tb:
            needed = trial
    status = max([cls for _, cls, _ in needed] or [OK], key=RANK.get)
    return status, [(cls, label) for label, cls, _ in needed], []


def _changed_relevant(o, n, o2, n2):
    return (o != n) and (o2 != o or n2 != n)


# ------------------------------------------------------------------ special checks

def check_sticky(o, n):
    if n['data']['missing']:
        return REGRESSION, [(REGRESSION, 'sticky placement lost by auto-assign')], [_short(n['data']['missing'])]
    if sorted(map(tuple, o['data']['before'])) != sorted(map(tuple, n['data']['before'])):
        return REGRESSION, [(REGRESSION, 'different sticky rows before auto-assign')], diff_summary(o['data']['before'],
                                                                                       n['data']['before'])
    return OK, [], []


def check_remap(o, n):
    od, nd = o['data'], n['data']
    expected = (od['remapped'] or 0) - od['orphan_rows_after']
    if nd['remapped'] == od['remapped']:
        return OK, [], []
    if nd['remapped'] == expected:
        return EXPECTED, [(EXPECTED, 'v1.4 scheme remap also kept orphan rows of deleted players '
                                     '(orphans are not migrated, documented)')], []
    return REGRESSION, [], [f"remapped old={od['remapped']} (orphans kept {od['orphan_rows_after']}) "
                            f"new={nd['remapped']}"]


# Per-step known outcomes for the S7 player-edit probes: (step, key) -> (class, reason)
S7_EXPECT = {
    ('S7:edit_status', 'import_lowercase_long_tag'):
        (EXPECTED, "4-char alliance 'love' rejected on resubmit (SPEC: alliance <=3 chars)"),
}
CRYSTAL_REASON = ('REAL fire_crystals/refined/shards values (e.g. 12.5) truncated to int by the migration: '
                  'points change (and everything ranked on them)')
FID_WS_REASON = (f'legacy FID with trailing space {FID_WS!r}: new strips FIDs on lookup, so the stored '
                 f'profile is unreachable; a resubmit forks a duplicate profile/application')


def check_s7(name, o, n):
    od, nd = o['data'], n['data']
    if od == nd:
        return OK, [], []
    status, labels, rest = OK, [], []
    if isinstance(od, dict) and isinstance(nd, dict):
        for k in sorted(set(od) | set(nd), key=str):
            a, b = od.get(k, '<missing>'), nd.get(k, '<missing>')
            if a == b:
                continue
            if (name, k) in S7_EXPECT:
                cls, why = S7_EXPECT[(name, k)]
            elif k in ('fid_trailing_space', FID_WS, FID_WS.strip()):
                cls, why = REGRESSION, FID_WS_REASON
            else:
                cls, why = REGRESSION, None
                rest.append(f'{k}: old={_short(a)} new={_short(b)}')
            status = max(status, cls, key=RANK.get)
            if why and (cls, why) not in labels:
                labels.append((cls, why))
        return status, labels, rest
    if name.startswith('S7:player_count') and nd == od + 1:
        return REGRESSION, [(REGRESSION, FID_WS_REASON)], []
    return REGRESSION, [], diff_summary(od, nd)


def check_player_assignments(o, n):
    od, nd = o['data'], n['data']
    bad = [f for f in od if od[f] != nd.get(f)]
    if not bad:
        return OK, [], []
    if bad == [FID_WS]:
        return REGRESSION, [(REGRESSION, FID_WS_REASON)], []
    return REGRESSION, [], [f'{f}: old={_short(od[f])} new={_short(nd.get(f))}' for f in bad[:4]]


def check_step(name, o, n):
    kind = n['kind']
    if kind == 'sticky':
        return check_sticky(o, n)
    if kind == 'remap':
        return check_remap(o, n)
    if name.startswith('S7:'):
        if kind == 'points':
            od = {k: v for k, v in o['data'].items()}
            nd = {k: v for k, v in n['data'].items()}
            extra = set(nd) - set(od)
            if extra == {FID_WS.strip()}:
                nd = {k: v for k, v in nd.items() if k not in extra}
                st, lab, d = compare('points', od, nd)
                if st == REGRESSION:
                    return st, [(REGRESSION, FID_WS_REASON)] + lab, d
                return REGRESSION, [(REGRESSION, FID_WS_REASON)] + lab, d
            return compare('points', od, nd)
        return check_s7(name, o, n)
    if kind == 'player_assignments':
        return check_player_assignments(o, n)
    return compare(kind, o['data'], n['data'])


# ------------------------------------------------------------------ driver

def run_scenario(sc, py, old_dir, root, verbose=False, mutation=None):
    wd = os.path.join(root, sc['name'])
    os.makedirs(wd)
    dbs, notes = build(sc, wd)
    with ThreadPoolExecutor(4) as ex:
        futs = {side: ex.submit(run_worker, py, side, dbs[side], old_dir, os.path.join(wd, f'{side}.json'),
                                mutation)
                for side in ('old', 'old_sorted', 'old_int', 'new')}
        res = {side: f.result() for side, f in futs.items()}
    rows = []
    hash_sensitive = 0
    for name, nstep in res['new'].items():
        ostep = res['old_sorted'].get(name)
        if ostep is None:
            rows.append({'step': name, 'status': REGRESSION, 'labels': [], 'diff': ['step missing in oracle']})
            continue
        st, labels, diff = check_step(name, ostep, nstep)
        if st == REGRESSION and not any(c == REGRESSION for c, _ in labels):
            st2, labels2, d2 = check_step(name, res['old_int'][name], nstep)
            if st2 != REGRESSION:
                labels = [(REGRESSION, CRYSTAL_REASON)] + labels2
                diff = []
            elif any(c == REGRESSION for c, _ in labels2):
                labels = [(REGRESSION, CRYSTAL_REASON)] + labels2
                diff = d2
            else:
                labels = labels + [(REGRESSION, '(unexplained)')]
        raw = res['old'].get(name)
        pref_order = False
        if raw is not None and raw['data'] != ostep['data']:
            hash_sensitive += 1
            if st != REGRESSION:
                st_raw, _, _ = check_step(name, raw, nstep)
                pref_order = st_raw == REGRESSION
        rows.append({'step': name, 'status': st, 'labels': labels, 'diff': diff, 'pref_order': pref_order})
    # direct facts worth printing
    facts = {}
    xs = res['new'].get('S1:xlsx')
    if xs:
        facts['xlsx_new'] = {t: len(c['rows']) for t, c in xs['data']['content'].items()}
        facts['xlsx_old'] = {t: len(c['rows']) for t, c in res['old_sorted']['S1:xlsx']['data']['content'].items()}
    sh = [res['new'][k]['data'] for k in res['new'] if k.endswith('shared_23:50')]
    facts['shared_23:50_new'] = [f"{k.split(':')[0]}:{v['earlier']}/{v['later']}" for k, v in
                                 ((k, res['new'][k]['data']) for k in res['new'] if k.endswith('shared_23:50'))]
    facts['shared_23:50_mirrored'] = all(v['earlier'] == v['later'] for v in sh)
    return {'scenario': sc, 'notes': notes, 'rows': rows, 'hash_sensitive_steps': hash_sensitive, 'facts': facts}


def self_test(py):
    root = tempfile.mkdtemp(prefix='wos-parity-selftest-')
    try:
        old_dir = os.path.join(root, '_v14')
        extract_v14(old_dir)
        sc = {'name': 'selftest-tue-max', 'seed': 2807, 'research_day': 'tuesday', 'scheme': 'max_slots',
              'players': 150}
        r = run_scenario(sc, py, old_dir, root, mutation='shared_winner')
    finally:
        shutil.rmtree(root, ignore_errors=True)
    caught = [x['step'] for x in r['rows'] if x['status'] == REGRESSION
              and any(l == '(unexplained)' for _, l in x['labels'])]
    print(f'self-test: injected shared-winner bug -> {len(caught)} unexplained regression step(s): {caught[:6]}')
    ok = any('shared_23:50' in s_ or 'auto_assign' in s_ for s_ in caught)
    print('SELF-TEST', 'PASSED (harness detects the bug)' if ok else 'FAILED (bug not detected)')
    return 0 if ok else 1


def extract_v14(dest):
    os.makedirs(dest, exist_ok=True)
    for f in ('app.py', 'database.py'):
        src = subprocess.run(['git', '-C', REPO, 'show', f'{V14_COMMIT}:backend/{f}'], capture_output=True,
                             text=True, check=True).stdout
        with open(os.path.join(dest, f), 'w') as fh:
            fh.write(src)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--python', default=DEFAULT_PY, help='interpreter with Flask/openpyxl/itsdangerous')
    ap.add_argument('--quick', action='store_true', help='4 scenarios instead of 15')
    ap.add_argument('--json', help='write the full report here')
    ap.add_argument('--keep', action='store_true', help='keep the temp dir (DBs + raw step dumps)')
    ap.add_argument('-v', '--verbose', action='store_true', help='list every non-OK step')
    ap.add_argument('--self-test', action='store_true',
                    help='inject a deliberate bug (shared 23:50 winner = LOWEST combined score) into the new app at '
                         'runtime and check the harness reports it as an unexplained regression')
    a = ap.parse_args()
    if a.self_test:
        return self_test(a.python)

    root = tempfile.mkdtemp(prefix='wos-parity-')
    old_dir = os.path.join(root, '_v14')
    extract_v14(old_dir)
    results = []
    try:
        for sc in scenarios(a.quick):
            print(f'... {sc["name"]}', file=sys.stderr, flush=True)
            results.append(run_scenario(sc, a.python, old_dir, root, a.verbose))
    finally:
        if not a.keep:
            shutil.rmtree(root, ignore_errors=True)
        else:
            print(f'kept: {root}', file=sys.stderr)

    # ---- summary table
    hdr = (f'{"scenario":<20} {"steps":>5} {"OK":>4} {"EXP":>4} {"BENIGN":>6} {"REGR":>4} {"pref-order*":>11} '
           f'{"hash-sens**":>11}  verdict (regression root causes: C=crystal truncation, F=FID whitespace, '
           f'?=unexplained)')
    print(hdr)
    print('-' * len(hdr))
    any_regr = False
    reasons = {EXPECTED: {}, BENIGN: {}, REGRESSION: {}}
    for r in results:
        c = {k: sum(1 for x in r['rows'] if x['status'] == k) for k in RANK}
        po = sum(1 for x in r['rows'] if x.get('pref_order'))
        verdict = 'REGRESSIONS' if c[REGRESSION] else ('expected diffs' if c[EXPECTED] + c[BENIGN] else 'OK')
        any_regr |= bool(c[REGRESSION])
        roots = {'C': 0, 'F': 0, '?': 0}
        for x in r['rows']:
            if x['status'] != REGRESSION:
                continue
            labs = [l for cl, l in x['labels'] if cl == REGRESSION]
            roots['C'] += any(l == CRYSTAL_REASON for l in labs)
            roots['F'] += any(l == FID_WS_REASON for l in labs)
            roots['?'] += any(l not in (CRYSTAL_REASON, FID_WS_REASON) for l in labs) or not labs
        rc = ' '.join(f'{k}:{v}' for k, v in roots.items() if v)
        print(f'{r["scenario"]["name"]:<20} {len(r["rows"]):>5} {c[OK]:>4} {c[EXPECTED]:>4} {c[BENIGN]:>6} '
              f'{c[REGRESSION]:>4} {po:>11} {r["hash_sensitive_steps"]:>11}  {verdict}{" (" + rc + ")" if rc else ""}')
        for x in r['rows']:
            for cls, lab in x['labels']:
                reasons[cls].setdefault(lab, []).append(f'{r["scenario"]["name"]}/{x["step"]}')
            if x.get('pref_order'):
                reasons[EXPECTED].setdefault('auto-assign walks preferences in sorted order (documented; live v1.4 '
                                             'used set hash order)', []).append(
                    f'{r["scenario"]["name"]}/{x["step"]}')
    print('\n*  pref-order: steps where live v1.4 (hash-ordered prefs, PYTHONHASHSEED=0) differs from new while v1.4')
    print('   with the documented sorted preference walk matches -> EXPECTED, counted in OK/EXP/BENIGN.')
    print('** hash-sens: steps whose v1.4 output itself changes between hash order and sorted order.')
    print('   Steps are counted once, under their worst class; a REGRESSION step may also carry BENIGN labels.')
    for r in results:
        for note in r['notes']:
            print(f'\nnote [{r["scenario"]["name"]}]: {note}')
    for cls in (EXPECTED, BENIGN, REGRESSION):
        if not reasons[cls]:
            continue
        print(f'\n== {cls} (root causes) ==')
        for lab, where in reasons[cls].items():
            print(f'  - {lab}\n      {len(where)} step(s), e.g. {", ".join(where[:3])}')
    shown = 0
    print('\n== regression details (first per root cause; -v for all) ==')
    seen = set()
    for r in results:
        for x in r['rows']:
            if x['status'] != REGRESSION:
                continue
            key = tuple(l for c, l in x['labels'] if c == REGRESSION)
            if not a.verbose and key in seen:
                continue
            seen.add(key)
            print(f'  {r["scenario"]["name"]}/{x["step"]}: {" | ".join(key)}')
            for d in x['diff']:
                print(f'      {d}')
            shown += 1
    print('\n== facts (new app) ==')
    for r in results:
        f = r['facts']
        print(f'  {r["scenario"]["name"]}: shared 23:50 per stage {f["shared_23:50_new"] or "n/a (no linked days)"}; '
              f'mirrored={f["shared_23:50_mirrored"]}; xlsx rows after S1 new={f.get("xlsx_new")}')
    if a.json:
        with open(a.json, 'w') as fh:
            json.dump(results, fh, indent=1, default=str)
    print(f'\nRESULT: {"REGRESSIONS FOUND" if any_regr else "no regressions"} '
          f'({len(results)} scenarios, {sum(len(r["rows"]) for r in results)} step comparisons)')
    return 1 if any_regr else 0


if __name__ == '__main__':
    sys.exit(main())
