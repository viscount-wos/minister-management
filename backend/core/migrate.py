"""One-off schema migration / v1.4 import. Run from backend/:

    python -m core.migrate --check              # read-only: version, pending v1.4 import, row counts
    python -m core.migrate                      # migrate DATABASE_PATH (imports a v1.4 file explicitly)
    python -m core.migrate --db /data/minister.db

The app itself refuses to start on a v1.4 file; this command (or one boot with
MIGRATE_V14=1) is the only way the import runs. Stop every other instance first:
see docs/DEPLOY-CUTOVER.md. Exit status: 0 ok, 1 migration failed, 2 usage error.
"""
import argparse
import json
import logging
import os
import sys

from core import db as core_db


def _print_status(label, st):
    print(f'{label}: exists={st["exists"]} schema_version={st["version"]} '
          f'latest={st.get("latest_version", core_db.LATEST_VERSION)} v1.4_import_pending={st["legacy_v14"]}')
    for table, n in sorted(st.get('counts', {}).items()):
        print(f'  {table:<26} {n}')


def verify(before, after, results):
    """Cross-check row counts of a v1.4 import. Returns a list of problems (empty = OK)."""
    problems = []
    b, a = before.get('counts', {}), after.get('counts', {})
    imp = (results or {}).get(1, {})
    if 'players' in b:
        if a.get('profiles') != b['players']:
            problems.append(f'profiles {a.get("profiles")} != v1.4 players {b["players"]}')
        if a.get('applications') != b['players']:
            problems.append(f'applications {a.get("applications")} != v1.4 players {b["players"]}')
        if a.get('legacy_players') != b['players']:
            problems.append(f'legacy_players {a.get("legacy_players")} != v1.4 players {b["players"]}')
    if 'assignments' in b and imp:
        moved = a.get('ministry_assignments', 0) + imp.get('orphan_assignments_skipped', 0)
        if moved != b['assignments']:
            problems.append(f'ministry_assignments + orphans {moved} != v1.4 assignments {b["assignments"]}')
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m core.migrate', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--db', default=os.getenv('DATABASE_PATH', '/data/minister.db'),
                    help='SQLite file (default: $DATABASE_PATH or /data/minister.db)')
    ap.add_argument('--check', action='store_true', help='report only, never write')
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    before = core_db.status(a.db)
    _print_status('before', before)
    if a.check:
        return 0
    if not before['exists']:
        print(f'error: {a.db} does not exist (refusing to create an empty DB from the migration command)',
              file=sys.stderr)
        return 2
    try:
        results = core_db.migrate(a.db, allow_v14=True)
    except Exception as e:  # noqa: BLE001  (report and exit non-zero; the transaction was rolled back)
        print(f'MIGRATION FAILED (database unchanged, rolled back): {type(e).__name__}: {e}', file=sys.stderr)
        return 1
    after = core_db.status(a.db)
    _print_status('after', after)
    print('results: ' + json.dumps(results, default=str))
    problems = verify(before, after, results) if before['legacy_v14'] else []
    if problems:
        print('COUNT CHECK FAILED:\n  ' + '\n  '.join(problems), file=sys.stderr)
        return 1
    print('OK' + (' (v1.4 import verified: counts match)' if before['legacy_v14'] else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
