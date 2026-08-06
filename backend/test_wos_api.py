#!/usr/bin/env python3
"""Diagnostic probe for the Whiteout Survival gift-code API.

The "Load from WOS" button used ``POST /api/player`` on the gift-code API to
resolve a FID into nickname / avatar / furnace level. Century Games reworked
the Gift Code Center in July 2026: the site no longer logs the player in and
shows a captcha, it just takes a Player ID plus a State and redeems in one POST.
The player-lookup and captcha endpoints were removed along with that flow.

This script talks to the live API so the claim can be re-checked at any time --
run it if someone reports the button is broken, or to find out whether Century
Games has restored a lookup endpoint.

Usage:
    python backend/test_wos_api.py [FID] [STATE]

Exit status is 0 if a usable player-lookup endpoint was found, 1 if not.
"""
import hashlib
import json
import sys
import time
import urllib.parse

import requests

BASE_URL = 'https://wos-giftcode-api.centurygame.com/api'
# Same shared secret the Gift Code Center's JS bundle uses to sign requests.
WOS_API_SECRET = 'tB87#kPtkxqOS2'

DEFAULT_FID = '432170285'
DEFAULT_STATE = '2694'

HEADERS = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Accept': 'application/json',
    'Origin': 'https://wos-giftcode.centurygame.com',
    'Referer': 'https://wos-giftcode.centurygame.com/',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
}


def append_sign(params):
    """Sign a payload the way the Gift Code Center's ``appendSign()`` does.

    Keys sorted, values URL-encoded, joined as ``k=v&k=v``, then
    ``md5(canonical + secret)`` prepended as ``sign``.
    """
    canonical = '&'.join(
        '{}={}'.format(key, urllib.parse.quote(str(params[key]), safe=''))
        for key in sorted(params)
    )
    sign = hashlib.md5((canonical + WOS_API_SECRET).encode()).hexdigest()
    return dict(params, sign=sign)


def post(path, params):
    """POST a signed payload; returns (status_code, parsed_json_or_None, raw_text)."""
    try:
        response = requests.post(
            BASE_URL + path,
            data=append_sign(params),
            headers=HEADERS,
            timeout=15,
        )
    except requests.exceptions.RequestException as exc:
        print('    transport error: {}'.format(exc))
        return None, None, ''

    try:
        return response.status_code, response.json(), response.text
    except ValueError:
        return response.status_code, None, response.text


def check_signing_still_works():
    """Sanity check: prove the secret and signing scheme are still valid.

    ``/api/gift_code_config`` needs no player data, so a ``code: 0`` reply means
    our signature was accepted -- which rules out "the signature is wrong" as an
    explanation for failures on the other endpoints.
    """
    print('1. Signature check via /gift_code_config')
    status, body, raw = post('/gift_code_config', {'time': int(time.time())})
    print('   HTTP {}'.format(status))
    if body and body.get('code') == 0:
        print('   OK - the request signature is accepted, secret is still valid.')
        return True
    print('   Signature REJECTED: {}'.format(raw[:200]))
    print('   The signing scheme or the secret has changed.')
    return False


def check_player_lookup(fid):
    """The endpoint that "Load from WOS" depended on."""
    print('\n2. Player lookup via /player (what "Load from WOS" used)')
    for label, timestamp in (
        ('nanosecond timestamp (original implementation)', int(time.time() * 1e9)),
        ('millisecond timestamp (Gift Code Center JS)', int(time.time() * 1000)),
        ('second timestamp', int(time.time())),
    ):
        status, body, raw = post('/player', {'fid': fid, 'time': timestamp})
        print('   {}: HTTP {}'.format(label, status))
        if status == 404:
            continue
        if body and body.get('code') == 0:
            data = body.get('data', {})
            print('   WORKS. Player data returned:')
            print('   ' + json.dumps(data, indent=2)[:600].replace('\n', '\n   '))
            return True
        print('   unexpected reply: {}'.format(raw[:200]))
    print('   All variants return HTTP 404 - the route no longer exists.')
    return False


def check_route_exists(path):
    """A removed route 404s on every method; a live POST-only route 405s on GET."""
    try:
        get = requests.get(BASE_URL + path, headers=HEADERS, timeout=15)
    except requests.exceptions.RequestException as exc:
        print('   {:<20} transport error: {}'.format(path, exc))
        return None
    exists = get.status_code != 404
    print('   {:<20} GET -> HTTP {}  ({})'.format(
        path, get.status_code, 'route exists' if exists else 'route REMOVED'))
    return exists


def check_surviving_routes():
    """Distinguish "endpoint removed" from "whole API down"."""
    print('\n3. Which routes still exist on the API')
    results = {path: check_route_exists(path)
               for path in ('/player', '/captcha', '/gift_code', '/gift_code_config')}
    return results


def check_giftcode_returns_profile(fid, state):
    """Last resort: does the surviving redemption endpoint leak profile data?

    Uses a deliberately invalid gift code, so nothing can be redeemed. If this
    ever returned nickname/avatar/furnace level it would be a (rate-limited,
    ugly) fallback for the lookup.
    """
    print('\n4. Does /gift_code return any player profile data?')
    print('   (invalid code "ZZZZINVALIDZZZZ" - nothing can be redeemed)')
    status, body, raw = post('/gift_code', {
        'fid': fid,
        'kid': state,
        'cdk': 'ZZZZINVALIDZZZZ',
        'time': int(time.time()),
    })
    print('   HTTP {}: {}'.format(status, raw[:200]))
    if not body:
        return False

    err_code = body.get('err_code')
    if err_code == 40020:
        print('   err_code 40020 (USER INFO ERROR) - the API rejects this')
        print('   FID/State pair. State {} may be wrong for FID {}.'.format(state, fid))
    data = body.get('data')
    if isinstance(data, dict) and any(
            key in data for key in ('nickname', 'avatar_image', 'stove_lv')):
        print('   Profile data IS present in the response.')
        return True
    print('   No nickname / avatar / furnace level in the response.')
    return False


def main():
    fid = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FID
    state = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_STATE

    print('WOS gift-code API probe')
    print('  base:  {}'.format(BASE_URL))
    print('  fid:   {}'.format(fid))
    print('  state: {}\n'.format(state))

    signing_ok = check_signing_still_works()
    lookup_ok = check_player_lookup(fid)
    routes = check_surviving_routes()
    profile_from_giftcode = check_giftcode_returns_profile(fid, state)

    print('\n' + '=' * 60)
    print('RESULT')
    print('=' * 60)
    if lookup_ok:
        print('/api/player works - "Load from WOS" can be restored.')
        return 0
    if profile_from_giftcode:
        print('/api/player is gone, but /api/gift_code returns profile data,')
        print('so the lookup could be rebuilt on top of it.')
        return 0

    if not signing_ok:
        print('Request signing was rejected - investigate the secret/scheme')
        print('before concluding the lookup endpoint is gone.')
    elif routes.get('/gift_code'):
        print('The API is up (/gift_code and /gift_code_config still answer),')
        print('but /player and /captcha have been removed. There is no public')
        print('endpoint left that resolves a FID into nickname / avatar /')
        print('furnace level, so "Load from WOS" cannot be made to work.')
    else:
        print('The whole API looks unreachable - this may be a transient')
        print('outage rather than a removed endpoint. Re-run later.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
