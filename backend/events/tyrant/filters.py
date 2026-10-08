"""Frost Dragon Tyrant admin filters (owner rule, p2d): one parser shared by the list, summary and export routes
(and so by the MCP tools), so a filtered view, its summary counts and its download always agree.

Every filter is an optional query parameter; all of them combine with AND. The admin UI keeps the SAME keys in its
own URL, so a filtered view is shareable. Bad values -> VALIDATION_ERROR with ``field`` = the parameter name.

  q              text: FID, in-game name or Discord ID contains (case-insensitive)
  alliance       one tag or a comma list (any of them), case-insensitive
  min_power, max_power   absolute power (whole numbers; the UI converts from millions)
  min_gems, max_gems     per-player est. max gem spend (blank never matches a bound)
  windows        comma list of window ids: available in ALL of them
  rush           1/true: available in at least one opening-rush window
  vc             yes|no: can listen in Discord VC
  troop          infantry|lancer|marksman|all (default all): which troop types min_camp / min_tier apply to
  min_camp       FC1..FC10: camp level at least this (pre-FC and blank camps never match)
  min_tier       1..11 or T11: tier at least this
  <type>_camp    exact camp level of ONE troop type (infantry_camp, lancer_camp, marksman_camp): a code
                 (FC10, or a legacy pre-FC code such as 25) or 'none' (blank) -- the summary chips
  <type>_tier    exact tier of one troop type (infantry_tier ...): 1..11 / T11, or 'none'
  roles          comma list of role ids; roles_mode any (default: has any of them) | all
  submitted_from, submitted_to   YYYY-MM-DD (UTC, inclusive)
  days           submitted in the last N days (1-3650)

There is no main-furnace filter (owner decision p2e: Tyrant does not ask the furnace; camp levels + tiers are the
strength signal). An old URL's ``min_furnace`` is ignored like any unknown parameter.
"""
import re
from datetime import datetime, timedelta, timezone

from core.errors import validation_error
from core.furnace import fc_number, validate_fc_level, validate_furnace
from events.tyrant import validation as tv

TROOP_FILTERS = tv.TROOP_TYPES + ('all',)
EXACT_KEYS = tuple(f'{k}_{d}' for k in tv.TROOP_TYPES for d in ('camp', 'tier'))
FILTER_KEYS = ('q', 'alliance', 'min_power', 'max_power', 'min_gems', 'max_gems', 'windows', 'rush',
               'vc', 'troop', 'min_camp', 'min_tier') + EXACT_KEYS + (
               'roles', 'roles_mode', 'submitted_from', 'submitted_to', 'days')
_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_TRUE = ('1', 'true', 'yes', 'on')
_FALSE = ('0', 'false', 'no', 'off', '')


def _blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


def _csv(v):
    if _blank(v):
        return []
    items = v if isinstance(v, (list, tuple)) else str(v).split(',')
    return [str(x).strip() for x in items if str(x).strip()]


def _int(v, field, lo, hi):
    if _blank(v):
        return None
    s = str(v).strip()
    if not re.fullmatch(r'\d+', s) or not lo <= int(s) <= hi:
        raise validation_error(f'{field} must be a whole number {lo}-{hi}', field)
    return int(s)


def parse_tier(v, field):
    if _blank(v):
        return None
    s = str(v).strip().upper()
    s = s[1:] if s.startswith('T') else s
    lo, hi = tv.TROOP_TIER_RANGE
    if not s.isdigit() or not lo <= int(s) <= hi:
        raise validation_error(f'{field} must be a tier {lo}-{hi} (e.g. 11 or T11)', field)
    return int(s)


def _date(v, field):
    if _blank(v):
        return None
    s = str(v).strip()
    try:
        if not _DATE.match(s):
            raise ValueError
        datetime.strptime(s, '%Y-%m-%d')
    except ValueError:
        raise validation_error(f'{field} must be a date YYYY-MM-DD', field)
    return s


def parse_filters(args, settings):
    """``args``: a mapping (request.args or a dict). Returns a dict of the ACTIVE filters (canonical values)."""
    get = (lambda k: args.get(k)) if hasattr(args, 'get') else (lambda k: None)
    f = {}
    if not _blank(get('q')):
        f['q'] = str(get('q')).strip()
    alliances = [a.casefold() for a in _csv(get('alliance'))]
    if alliances:
        f['alliance'] = alliances
    for key, hi in (('min_power', 10 ** 13), ('max_power', 10 ** 13), ('min_gems', tv.MAX_GEMS),
                    ('max_gems', tv.MAX_GEMS)):
        n = _int(get(key), key, 0, hi)
        if n is not None:
            f[key] = n
    window_ids = {w['id'] for w in settings.get('windows') or []}
    wins = _csv(get('windows'))
    for w in wins:
        if w not in window_ids:
            raise validation_error(f'windows contains an unknown window id {w!r}', 'windows')
    if wins:
        f['windows'] = wins
    rush = str(get('rush') or '').strip().lower()
    if rush not in _TRUE + _FALSE:
        raise validation_error('rush must be 1 or 0', 'rush')
    if rush in _TRUE:
        f['rush'] = True
    vc = str(get('vc') or '').strip().lower()
    if vc not in ('', 'any', 'yes', 'no'):
        raise validation_error('vc must be yes, no or any', 'vc')
    if vc in ('yes', 'no'):
        f['vc'] = vc == 'yes'
    troop = str(get('troop') or 'all').strip().lower() or 'all'
    if troop not in TROOP_FILTERS:
        raise validation_error('troop must be one of ' + ', '.join(TROOP_FILTERS), 'troop')
    if not _blank(get('min_camp')):
        f['min_camp'] = validate_fc_level(get('min_camp'), 'min_camp')
    tier = parse_tier(get('min_tier'), 'min_tier')
    if tier is not None:
        f['min_tier'] = tier
    if 'min_camp' in f or 'min_tier' in f:
        f['troop'] = troop
    for kind in tv.TROOP_TYPES:
        key = f'{kind}_camp'
        v = get(key)
        if not _blank(v):
            f[key] = 'none' if str(v).strip().lower() == 'none' else validate_furnace(v, key)
        key = f'{kind}_tier'
        v = get(key)
        if not _blank(v):
            f[key] = 'none' if str(v).strip().lower() == 'none' else parse_tier(v, key)
    roles = _csv(get('roles'))
    for r in roles:
        if r not in tv.ROLES:
            raise validation_error(f'roles contains an unknown role {r!r}', 'roles')
    mode = str(get('roles_mode') or 'any').strip().lower() or 'any'
    if mode not in ('any', 'all'):
        raise validation_error('roles_mode must be any or all', 'roles_mode')
    if roles:
        f['roles'] = roles
        f['roles_mode'] = mode
    for key in ('submitted_from', 'submitted_to'):
        d = _date(get(key), key)
        if d:
            f[key] = d
    days = _int(get('days'), 'days', 1, 3650)
    if days:
        f['days'] = days
    return f


def _troop(profile, kind, key):
    from events.tyrant.logic import _troop as t
    return t(profile, kind, key)


def _norm_ts(ts):
    return (ts or '').replace(' ', 'T')


def matches(app, f, settings):
    ans, prof = app['answers'], app['profile']
    if 'q' in f:
        needle = f['q'].casefold()
        if not (needle in (app['fid'] or '').casefold() or needle in (prof.get('game_name') or '').casefold()
                or needle in (prof.get('discord_id') or '').casefold()):
            return False
    if 'alliance' in f and (prof.get('alliance') or '').strip().casefold() not in f['alliance']:
        return False
    power, gems = prof.get('power'), ans.get('gem_spend')
    for key, val, op in (('min_power', power, '>='), ('max_power', power, '<='), ('min_gems', gems, '>='),
                         ('max_gems', gems, '<=')):
        if key in f and (val is None or (val < f[key] if op == '>=' else val > f[key])):
            return False
    avail = set(ans.get('availability') or [])
    if 'windows' in f and not set(f['windows']) <= avail:
        return False
    if f.get('rush') and not avail & {w['id'] for w in settings.get('windows') or [] if w.get('rush')}:
        return False
    if 'vc' in f and bool(ans.get('discord_vc')) != f['vc']:
        return False
    kinds = tv.TROOP_TYPES if f.get('troop', 'all') == 'all' else (f['troop'],)
    for kind in kinds:
        if 'min_camp' in f and fc_number(_troop(prof, kind, 'furnace_level')) < fc_number(f['min_camp']):
            return False
        if 'min_tier' in f and (_troop(prof, kind, 'tier') or 0) < f['min_tier']:
            return False
    for kind in tv.TROOP_TYPES:
        want = f.get(f'{kind}_camp')
        if want is not None and (_troop(prof, kind, 'furnace_level') or 'none') != want:
            return False
        want = f.get(f'{kind}_tier')
        if want is not None and (_troop(prof, kind, 'tier') or 'none') != want:
            return False
    if 'roles' in f:
        have = set(ans.get('roles') or [])
        if f['roles_mode'] == 'all' and not set(f['roles']) <= have:
            return False
        if f['roles_mode'] == 'any' and not have & set(f['roles']):
            return False
    created = _norm_ts(app.get('created_at'))
    if 'submitted_from' in f and created[:10] < f['submitted_from']:
        return False
    if 'submitted_to' in f and created[:10] > f['submitted_to']:
        return False
    if 'days' in f:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=f['days'])).replace(microsecond=0)
        if created < cutoff.isoformat().replace('+00:00', 'Z'):
            return False
    return True


def apply_filters(apps, f, settings):
    return [a for a in apps if matches(a, f, settings)] if f else list(apps)
