"""Frost Dragon Tyrant: answer, round-settings and troop-level validation.

Option lists are the ones of the live tyrantpoll app (templates/poll.html):
- availability windows (UTC) 11:01-11:15 "Opening Rush", 11:15-13:00, 13:00-15:00, 15:00-16:30, 16:30-18:00,
  now per-round settings (``windows``) with these as defaults;
- "can listen in Discord VC" (bool);
- estimated max gem spend: tyrantpoll had a free-text box ("e.g. 10000"); here a whole number of gems;
- roles: Rally Leader, Joiner, Gathering/Looting, Battle Management, Event Preparation;
- troops (PROFILE field ``troops``): per troop type a fire-crystal level FC1-FC10 and a tier T8-T11, each optional.

Furnace level is the shared profile integer ``furnace_level``: 1-30 are plain furnace levels and FCn is stored
as 30 + n (FC1 = 31 ... FC10 = 40).
"""
import re

from core.errors import validation_error
from core.validation import validate_bool, validate_number

ROLES = ('rally_leader', 'joiner', 'gathering', 'battle_mgmt', 'event_prep')
TROOP_TYPES = ('infantry', 'lancer', 'marksman')
TROOP_FC_RANGE = (1, 10)
TROOP_TIER_RANGE = (1, 11)
FC_OFFSET = 30  # profile furnace_level: FCn = 30 + n
LANGUAGES = ('en', 'es', 'fr', 'de', 'pl', 'ko', 'zh', 'tr', 'ar')
MAX_GEMS = 1_000_000_000
MAX_WINDOWS = 12

ANSWER_KEYS = ('availability', 'discord_vc', 'gem_spend', 'roles', 'language')

DEFAULT_WINDOWS = [
    {'id': 'w1', 'start': '11:01', 'end': '11:15', 'rush': True},
    {'id': 'w2', 'start': '11:15', 'end': '13:00', 'rush': False},
    {'id': 'w3', 'start': '13:00', 'end': '15:00', 'rush': False},
    {'id': 'w4', 'start': '15:00', 'end': '16:30', 'rush': False},
    {'id': 'w5', 'start': '16:30', 'end': '18:00', 'rush': False},
]

_HHMM = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
_WINDOW_ID = re.compile(r'^[a-z0-9_]{1,24}$')


def default_settings():
    return {'windows': [dict(w) for w in DEFAULT_WINDOWS]}


def _hhmm(value, field):
    if not isinstance(value, str) or not _HHMM.match(value.strip()):
        raise validation_error(f'{field} must be a time HH:MM (UTC)', field)
    return value.strip()


def validate_windows(value, field='settings.windows'):
    if not isinstance(value, list):
        raise validation_error('windows must be a list', field)
    if not 1 <= len(value) <= MAX_WINDOWS:
        raise validation_error(f'windows must have 1 to {MAX_WINDOWS} entries', field)
    out, seen = [], set()
    for i, w in enumerate(value):
        f = f'{field}.{i}'
        if not isinstance(w, dict):
            raise validation_error('each window must be an object', f)
        unknown = set(w) - {'id', 'start', 'end', 'rush'}
        if unknown:
            raise validation_error(f'Unknown window key(s): {", ".join(sorted(unknown))}', f)
        wid = w.get('id')
        if not isinstance(wid, str) or not _WINDOW_ID.match(wid):
            raise validation_error('window id must be 1-24 chars of a-z, 0-9, _', f + '.id')
        if wid in seen:
            raise validation_error(f'duplicate window id {wid!r}', f + '.id')
        seen.add(wid)
        start = _hhmm(w.get('start'), f + '.start')
        end = _hhmm(w.get('end'), f + '.end')
        if end <= start:
            raise validation_error('window end must be after its start', f + '.end')
        rush = validate_bool(w.get('rush', False), f + '.rush')
        out.append({'id': wid, 'start': start, 'end': end, 'rush': rush})
    out.sort(key=lambda w: (w['start'], w['end']))
    return out


def validate_settings(incoming, current):
    if not isinstance(incoming, dict):
        raise validation_error('settings must be an object', 'settings')
    unknown = set(incoming) - {'windows'}
    if unknown:
        raise validation_error(f'Unknown setting(s): {", ".join(sorted(unknown))}', 'settings')
    merged = default_settings()
    merged.update({k: v for k, v in (current or {}).items() if k == 'windows'})
    if 'windows' in incoming:
        merged['windows'] = validate_windows(incoming['windows'])
    return merged


def _id_list(value, field, allowed, order):
    if value is None:
        return []
    if not isinstance(value, list):
        raise validation_error(f'{field} must be a list', field)
    picked = set()
    for v in value:
        if not isinstance(v, str) or v not in allowed:
            raise validation_error(f'{field} contains an unknown value {v!r}', field)
        picked.add(v)
    return [x for x in order if x in picked]


def validate_answers(answers, settings, existing=None):
    """Strict tyrant answers. ``existing`` = stored answers: a window id the admin has since removed
    from the round is kept when re-sent (so old applications stay editable), new ones must exist."""
    if answers is None:
        answers = {}
    if not isinstance(answers, dict):
        raise validation_error('answers must be an object', 'answers')
    unknown = set(answers) - set(ANSWER_KEYS)
    if unknown:
        raise validation_error(f'Unknown answer(s): {", ".join(sorted(unknown))}', 'answers.' + sorted(unknown)[0])
    existing = existing if isinstance(existing, dict) else {}
    window_ids = [w['id'] for w in settings.get('windows') or []]
    legacy = [w for w in (existing.get('availability') or []) if isinstance(w, str) and w not in window_ids]
    out = {
        'availability': _id_list(answers.get('availability'), 'answers.availability',
                                 set(window_ids) | set(legacy), window_ids + legacy),
        'discord_vc': (False if answers.get('discord_vc') is None
                       else validate_bool(answers['discord_vc'], 'answers.discord_vc')),
        'gem_spend': validate_number(answers.get('gem_spend'), 'answers.gem_spend', maximum=MAX_GEMS,
                                     integer=True, nullable=True),
        'roles': _id_list(answers.get('roles'), 'answers.roles', set(ROLES), ROLES),
    }
    lang = answers.get('language')
    if lang is not None and lang not in LANGUAGES:
        raise validation_error('language must be one of ' + ', '.join(LANGUAGES), 'answers.language')
    out['language'] = lang
    return out


def _troop_level(value, field, lo, hi):
    if value is None or value == '':
        return None
    return validate_number(value, field, minimum=lo, maximum=hi, integer=True)


def validate_troops(value, field='profile.troops'):
    """Canonical troop levels: {infantry|lancer|marksman: {fc: 1-10|null, tier: 1-11|null}}."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise validation_error('troops must be an object', field)
    unknown = set(value) - set(TROOP_TYPES)
    if unknown:
        raise validation_error(f'Unknown troop type(s): {", ".join(sorted(unknown))}', field)
    out = {}
    for kind in TROOP_TYPES:
        entry = value.get(kind)
        f = f'{field}.{kind}'
        if entry is None:
            out[kind] = {'fc': None, 'tier': None}
            continue
        if not isinstance(entry, dict) or set(entry) - {'fc', 'tier'}:
            raise validation_error('troop entry must be {fc, tier}', f)
        out[kind] = {'fc': _troop_level(entry.get('fc'), f + '.fc', *TROOP_FC_RANGE),
                     'tier': _troop_level(entry.get('tier'), f + '.tier', *TROOP_TIER_RANGE)}
    return out


def furnace_label(level):
    """30 -> '30', 35 -> 'FC5'. None -> None."""
    if level is None:
        return None
    return f'FC{level - FC_OFFSET}' if level > FC_OFFSET else str(level)
