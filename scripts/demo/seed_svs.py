#!/usr/bin/env python3
"""Seed an SVS round with realistic DUMMY sign-ups (and optionally a sample battle plan) through the public API.

For the owner's LOCAL test copy only (never the live site). Stdlib only.

    python3 scripts/demo/seed_svs.py --base-url http://127.0.0.1:8095 --password <admin password> [--plan]
    (or BASE_URL / ADMIN_PASSWORD in the environment)

What it does
- Logs in once (the admin login is rate limited: one token is reused for everything).
- Uses the OPEN SVS round, or starts one ("SVS demo <date>", battle 11:00 UTC for 5 hours) if there is none.
  ``--new-round`` always starts a fresh one (this CLOSES the current SVS round; asks first unless --yes).
- Submits ~60 dummy players across 8 alliances through the PUBLIC player route
  (PUT /api/events/svs/current/application/<fid>): varied hours, camps FC5-FC10, T10/T11, Discord VC yes/no.
  No role: SVS sign-up does not ask it (the planner assigns leaders). FIDs are fixed (990001..), so re-running
  just updates the same sign-ups (idempotent-ish); the random choices are seeded too.
- ``--plan``: saves a sample main + counter plan with 4 leaders (disguises, split garrison, pet buffs, named and
  extra joiners) if the round's plan is still empty (revision 0); ``--force-plan`` overwrites it.

Rate limits: player submits are limited per IP (RATE_LIMIT_SUBMITS_PER_MIN, default 10/min). This script sends the
ADMIN token with every request, and admin-authenticated requests are not throttled, so it runs at full speed. If
that ever changes, start the stack with RATE_LIMIT_SUBMITS_PER_MIN=0 RATE_LIMIT_LOOKUPS_PER_MIN=0, or use
``--delay 6.5``.
"""
import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import date

ALLIANCES = ['WOO', 'ICE', 'FRS', 'BLZ', 'NRT', 'WLF', 'SNO', 'AUR']
FIRST = ['Frost', 'Ice', 'Snow', 'Polar', 'Storm', 'Winter', 'Glacier', 'Blizzard', 'North', 'Aurora', 'Tundra',
         'Hail', 'Sleet', 'Rime', 'Boreal', 'Crystal']
SECOND = ['Wolf', 'Bear', 'Hawk', 'Fox', 'Lynx', 'Raven', 'Knight', 'Queen', 'King', 'Blade', 'Fang', 'Heart',
          'Viking', 'Rider', 'Hunter', 'Smith']
FID_BASE = 990001
COUNT = 60
CAMPS = ['FC10', 'FC9', 'FC9', 'FC8', 'FC8', 'FC7', 'FC6', 'FC5']


class Api:
    def __init__(self, base, password, delay=0.0):
        self.base = base.rstrip('/')
        self.delay = delay
        _, res = self.call('POST', '/api/admin/login', {'password': password}, admin=False)
        self.token = res['token']

    def call(self, method, path, body=None, admin=True, ok=(200, 201)):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header('Accept', 'application/json')
        if data is not None:
            req.add_header('Content-Type', 'application/json')
        if admin:
            req.add_header('Authorization', f'Bearer {self.token}')
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                status, payload = r.status, json.loads(r.read() or b'{}')
        except urllib.error.HTTPError as e:
            status, payload = e.code, json.loads(e.read() or b'{}')
        if ok and status not in ok:
            raise SystemExit(f'{method} {path} -> {status} {payload}')
        return status, payload


def players(rng, hours):
    out = []
    used = set()
    for i in range(COUNT):
        while True:
            name = f'{rng.choice(FIRST)}{rng.choice(SECOND)}'
            if rng.random() < 0.35:
                name += str(rng.randint(1, 99))
            if name not in used:
                used.add(name)
                break
        alliance = ALLIANCES[i % len(ALLIANCES)] if i < 48 else rng.choice(ALLIANCES[:3])
        # the first dozen are the strong ones (likely rally leaders): FC9-FC10, mostly T11
        strong = i < 12
        troops = {}
        for kind in ('infantry', 'lancer', 'marksman'):
            camp = rng.choice(['FC10', 'FC10', 'FC9']) if strong else rng.choice(CAMPS)
            fc = int(camp[2:])
            tier = 11 if (strong and rng.random() < 0.85) or (fc >= 8 and rng.random() < 0.5) else 10
            troops[kind] = {'furnace_level': camp, 'tier': tier}
        start = rng.randrange(len(hours))
        span = rng.choice([1, 2, 2, 3, 3, 4, 5])
        mine = hours[start:start + span] or hours[:1]
        if strong:
            mine = hours[:]  # leaders tend to be there the whole battle
        out.append({'fid': str(FID_BASE + i), 'name': name, 'alliance': alliance, 'troops': troops,
                    'hours': mine, 'vc': strong or rng.random() < 0.6})
    return out


def sample_plan(seeded):
    f = [p['fid'] for p in seeded]

    def leader(lid, gid, fid, heroes, ratio, pet, alias=None, pfp=None, joiners=(), extras=(), others=(), split=None):
        ld = {'id': lid, 'group_id': gid, 'order': 0, 'player': {'fid': fid},
              'disguise': {'pfp_hero': pfp, 'alias': alias}, 'split': bool(split),
              'rally': {'heroes': heroes, 'ratio': ratio}, 'garrison': split, 'pet_buff': pet,
              'named_joiners': [{'player': {'fid': j}, 'rally': {'lead_hero': h}, 'garrison': {'lead_hero': g}}
                                for j, h, g in joiners],
              'other_joiner_heroes': {'rally': list(others), 'garrison': list(others[:1])},
              'extra_joiners': [{'player': {'fid': e}} for e in extras]}
        return ld
    r1 = {'inf': 50, 'lan': 20, 'mks': 30}
    return {
        'strategy': 'main_counter', 'show_real_names': True,
        'groups': [
            {'id': 'main', 'kind': 'main', 'name': 'Main rallies', 'alliance_tag': 'WOO',
             'min_requirements': {'infantry': {'min_camp': 'FC8', 'min_tier': 11},
                                  'lancer': {'min_camp': 'FC8', 'min_tier': None},
                                  'marksman': {'min_camp': 'FC8', 'min_tier': None}},
             'notes': 'Join within 10 seconds of the call. Voice chat on Discord.'},
            {'id': 'counter', 'kind': 'counter', 'name': 'Counter rallies', 'alliance_tag': 'ICE',
             'min_requirements': {'infantry': {'min_camp': 'FC7', 'min_tier': 10}}},
            {'id': 'turrets', 'kind': 'extra', 'name': 'Turrets', 'notes': 'Hold the north-east turret.',
             'players': [{'fid': f[40]}, {'fid': f[41]}, {'name': 'Walk-in helper'}]},
        ],
        'leaders': [
            leader('L1', 'main', f[0], ['jeronimo', 'molly', 'zinman'], r1, 'open', 'Rally Caller 01', 'flint',
                   joiners=[(f[12], 'jessie', None), (f[13], 'jessie', None), (f[14], 'sergey', None),
                            (f[15], 'patrick', None)], extras=[f[20], f[21], f[22]], others=['jessie', 'jessie']),
            leader('L2', 'main', f[1], ['natalia', 'philly', 'alonso'], {'inf': 60, 'lan': 20, 'mks': 20}, 'two_hours',
                   'Rally Caller 02', 'logan', joiners=[(f[16], 'jessie', 'sergey'), (f[17], 'jessie', 'sergey')],
                   extras=[f[23], f[24]], others=['jessie', 'patrick'],
                   split={'heroes': ['logan', 'mia', 'greg'], 'ratio': {'inf': 70, 'lan': 15, 'mks': 15}}),
            leader('L3', 'counter', f[2], ['ahmose', 'reina', 'lynn'], {'inf': 40, 'lan': 30, 'mks': 30}, 'last_hour',
                   joiners=[(f[18], 'jessie', None)], extras=[f[25]], others=['jessie']),
            leader('L4', 'counter', f[3], ['hector', 'norah', 'gwen'], r1, 'two_hours',
                   joiners=[(f[19], 'sergey', None)]),
        ],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base-url', default=os.getenv('BASE_URL'))
    ap.add_argument('--password', default=os.getenv('ADMIN_PASSWORD'))
    ap.add_argument('--new-round', action='store_true', help='start a fresh SVS round (closes the open one)')
    ap.add_argument('--yes', action='store_true', help='do not ask before closing the open SVS round')
    ap.add_argument('--plan', action='store_true', help='also save a sample plan (2 groups, 4 leaders) if empty')
    ap.add_argument('--force-plan', action='store_true', help='overwrite the plan with the sample one')
    ap.add_argument('--delay', type=float, default=0.0, help='seconds between submits (if rate limits bite)')
    ap.add_argument('--seed', type=int, default=2807)
    args = ap.parse_args()
    if not args.base_url or not args.password:
        ap.error('--base-url and --password (or BASE_URL / ADMIN_PASSWORD) are required')
    if 'hunterisadonkey.com' in args.base_url:
        raise SystemExit('Refusing to seed dummy data into the live site.')
    api = Api(args.base_url, args.password, args.delay)

    status, cur = api.call('GET', '/api/events/svs/current', admin=False, ok=None)
    if args.new_round or status != 200:
        if status == 200 and not args.yes:
            if input(f'Close the open SVS round "{cur["name"]}" and start a new one? [y/N] ').lower() != 'y':
                raise SystemExit('Nothing done.')
        _, res = api.call('POST', '/api/admin/events/svs/start-new-round',
                          {'name': f'SVS demo {date.today().isoformat()}',
                           'settings': {'battle_start': '11:00', 'battle_hours': 5}})
        cur = res['round']
        print(f'Started round {cur["id"]} "{cur["name"]}"')
        _, cur = api.call('GET', '/api/events/svs/current', admin=False)
    else:
        print(f'Using open round {cur["id"]} "{cur["name"]}"')
    hours = cur['settings']['hours']

    rng = random.Random(args.seed)
    seeded = players(rng, hours)
    created = updated = 0
    for p in seeded:
        body = {'profile': {'game_name': p['name'], 'alliance': p['alliance'], 'troops': p['troops']},
                'answers': {'hours': p['hours'], 'discord_vc': p['vc'], 'language': 'en'}}
        _, res = api.call('PUT', f'/api/events/svs/current/application/{p["fid"]}', body)  # admin token: no throttle
        created += res.get('created', False)
        updated += not res.get('created', False)
        if args.delay:
            time.sleep(args.delay)
    print(f'Sign-ups: {created} created, {updated} updated ({len(seeded)} players, {len(ALLIANCES)} alliances)')

    if args.plan or args.force_plan:
        _, plan = api.call('GET', f'/api/admin/svs/rounds/{cur["id"]}/plan')
        if plan['revision'] and not args.force_plan:
            print(f'Plan already has revision {plan["revision"]}: left alone (use --force-plan to overwrite)')
        else:
            _, res = api.call('PUT', f'/api/admin/svs/rounds/{cur["id"]}/plan',
                              {'revision': plan['revision'], 'plan': sample_plan(seeded)})
            print(f'Sample plan saved (revision {res["revision"]}): 2 groups + turrets, 4 leaders')
    print('Open Event Management -> SVS -> Battle plan.')


if __name__ == '__main__':
    sys.exit(main())
