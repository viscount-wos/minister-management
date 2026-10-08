"""SVS admin filters: ONE parser shared by the list, summary and export routes (and so by the MCP tools), exactly like
Frost Dragon Tyrant's (events/tyrant/filters.py, whose helpers it reuses). All optional, combined with AND; the admin
URL uses the same keys.

  q              text: FID or in-game name contains (case-insensitive)
  alliance       one tag or a comma list (any of them)
  hours          comma list of hour starts ("11:00,12:00"): attends ALL of them
  role           call | join  ("none" = no role given, admin-added players)
  vc             yes | no  (Discord voice chat; "none" = not answered)
  troop          infantry|lancer|marksman|all (default all): which troop types min_camp / min_tier apply to
  min_camp       FC1..FC10: camp level at least this
  min_tier       10 / 11 (or T11): tier at least this
  <type>_camp    exact camp level of one troop type (FC10, a legacy code, or 'none') -- the summary chips
  <type>_tier    exact tier of one troop type (1..11 / T11, or 'none')
  submitted_from, submitted_to   YYYY-MM-DD (UTC, inclusive)
  days           submitted in the last N days
"""
from datetime import datetime, timedelta, timezone

from core.errors import validation_error
from core.furnace import fc_number, validate_fc_level, validate_furnace
from events.svs import validation as sv
from events.tyrant.filters import _blank, _csv, _date, _int, _norm_ts, parse_tier

TROOP_FILTERS = sv.TROOP_TYPES + ('all',)
EXACT_KEYS = tuple(f'{k}_{d}' for k in sv.TROOP_TYPES for d in ('camp', 'tier'))
FILTER_KEYS = ('q', 'alliance', 'hours', 'role', 'vc', 'troop', 'min_camp', 'min_tier') + EXACT_KEYS + (
    'submitted_from', 'submitted_to', 'days')


def _troop(profile, kind, key):
    from events.tyrant.logic import _troop as t
    return t(profile, kind, key)


def parse_filters(args, settings):
    """``args``: request.args or a dict. Returns the ACTIVE filters (canonical values)."""
    get = (lambda k: args.get(k)) if hasattr(args, 'get') else (lambda k: None)
    f = {}
    if not _blank(get('q')):
        f['q'] = str(get('q')).strip()
    alliances = [a.casefold() for a in _csv(get('alliance'))]
    if alliances:
        f['alliance'] = alliances
    known = set(sv.battle_hours(settings))
    hours = _csv(get('hours'))
    for h in hours:
        if h not in known:
            raise validation_error(f'hours contains an hour that is not in this battle: {h!r}', 'hours')
    if hours:
        f['hours'] = hours
    role = str(get('role') or '').strip().lower()
    if role not in ('', 'any') + sv.ROLES + ('none',):
        raise validation_error('role must be call, join or none', 'role')
    if role and role != 'any':
        f['role'] = role
    vc = str(get('vc') or '').strip().lower()
    if vc not in ('', 'any', 'yes', 'no', 'none'):
        raise validation_error('vc must be yes, no or none', 'vc')
    if vc in ('yes', 'no', 'none'):
        f['vc'] = vc
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
    for kind in sv.TROOP_TYPES:
        key = f'{kind}_camp'
        v = get(key)
        if not _blank(v):
            f[key] = 'none' if str(v).strip().lower() == 'none' else validate_furnace(v, key)
        key = f'{kind}_tier'
        v = get(key)
        if not _blank(v):
            f[key] = 'none' if str(v).strip().lower() == 'none' else parse_tier(v, key)
    for key in ('submitted_from', 'submitted_to'):
        d = _date(get(key), key)
        if d:
            f[key] = d
    days = _int(get('days'), 'days', 1, 3650)
    if days:
        f['days'] = days
    return f


def matches(app, f):
    ans, prof = app['answers'], app['profile']
    if 'q' in f:
        needle = f['q'].casefold()
        if not (needle in (app['fid'] or '').casefold() or needle in (prof.get('game_name') or '').casefold()):
            return False
    if 'alliance' in f and (prof.get('alliance') or '').strip().casefold() not in f['alliance']:
        return False
    if 'hours' in f and not set(f['hours']) <= set(ans.get('hours') or []):
        return False
    if 'role' in f and (ans.get('role') or 'none') != f['role']:
        return False
    if 'vc' in f:
        vc = ans.get('discord_vc')
        if (('none' if vc is None else 'yes' if vc else 'no')) != f['vc']:
            return False
    kinds = sv.TROOP_TYPES if f.get('troop', 'all') == 'all' else (f['troop'],)
    for kind in kinds:
        if 'min_camp' in f and fc_number(_troop(prof, kind, 'furnace_level')) < fc_number(f['min_camp']):
            return False
        if 'min_tier' in f and (_troop(prof, kind, 'tier') or 0) < f['min_tier']:
            return False
    for kind in sv.TROOP_TYPES:
        want = f.get(f'{kind}_camp')
        if want is not None and (_troop(prof, kind, 'furnace_level') or 'none') != want:
            return False
        want = f.get(f'{kind}_tier')
        if want is not None and (_troop(prof, kind, 'tier') or 'none') != want:
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


def apply_filters(apps, f):
    return [a for a in apps if matches(a, f)] if f else list(apps)
