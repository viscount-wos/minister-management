"""SVS (State vs State castle battle) sign-up: answer, round-settings and troop validation (owner brief 2026-10-08).

Much less than Frost Dragon Tyrant: no gems, no furnace, no power, and NO role (owner: the planner assigns rally
leaders by hand; an old client that still sends ``role`` is not refused, the value is dropped).

Round settings: ``battle_start`` "HH:MM" UTC (default "11:00") and ``battle_hours`` 1-24 (default 5). The battle's
HOURS are derived: start, start+1h, ... (wrapping past midnight), e.g. 11:00 12:00 13:00 14:00 15:00 UTC.

Answers (per application):
  hours       list of hour starts "HH:MM" (UTC) the player will attend, a subset of the round's hours
  discord_vc  bool: can join Discord voice chat
  language    UI language at submit (or null)

Profile (shared per FID, also Frost Dragon Tyrant's): game_name, alliance (required for a NEW player only), troops =
per troop type its CAMP level (FC1-FC10) and tier. SVS offers tiers T10/T11 ONLY (owner: T8/T9 are never allowed in
SVS). On a player submit everything is required: >= 1 hour, the VC answer, and camp + tier (10/11) for all
three troop types. Admin create/edit ("add player") is lenient: every answer and troop value may be blank.

Troop merge rule (shared profile, see ``merge_troops``): per troop type and per field, a value sent replaces the
stored one, a blank never clears a stored one, and nothing SVS does not ask is touched.
"""
import re

from core.errors import validation_error
from core.furnace import validate_fc_level
from core.troops import merge_troops  # noqa: F401 (re-exported: the shared merge rule)
from core.validation import validate_bool

TROOP_TYPES = ('infantry', 'lancer', 'marksman')
TIERS = (10, 11)
LANGUAGES = ('en', 'es', 'fr', 'de', 'pl', 'ko', 'zh', 'tr', 'ar')
ANSWER_KEYS = ('hours', 'discord_vc', 'language')
# Asked until v2.2.0 drafts; accepted from old clients and dropped (never stored, never an error).
IGNORED_ANSWER_KEYS = ('role',)
DEFAULT_START = '11:00'
DEFAULT_HOURS = 5
MAX_HOURS = 24

_HHMM = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')


def default_settings():
    return {'battle_start': DEFAULT_START, 'battle_hours': DEFAULT_HOURS}


def battle_hours(settings):
    """The round's hour slots in battle order: ['11:00', '12:00', ...] (wraps past midnight)."""
    start = settings.get('battle_start') or DEFAULT_START
    n = settings.get('battle_hours') or DEFAULT_HOURS
    h, m = (int(x) for x in start.split(':'))
    return [f'{(h + i) % 24:02d}:{m:02d}' for i in range(n)]


def validate_settings(incoming, current):
    if not isinstance(incoming, dict):
        raise validation_error('settings must be an object', 'settings')
    unknown = set(incoming) - {'battle_start', 'battle_hours'}
    if unknown:
        raise validation_error(f'Unknown setting(s): {", ".join(sorted(unknown))}', 'settings')
    merged = default_settings()
    merged.update({k: v for k, v in (current or {}).items() if k in merged})
    if 'battle_start' in incoming:
        v = incoming['battle_start']
        if not isinstance(v, str) or not _HHMM.match(v.strip()):
            raise validation_error('battle_start must be a time HH:MM (UTC)', 'settings.battle_start')
        merged['battle_start'] = v.strip()
    if 'battle_hours' in incoming:
        v = incoming['battle_hours']
        if isinstance(v, bool) or not isinstance(v, (int, str)) or not re.fullmatch(r'\d{1,2}', str(v).strip()) \
                or not 1 <= int(v) <= MAX_HOURS:
            raise validation_error(f'battle_hours must be a whole number 1-{MAX_HOURS}', 'settings.battle_hours')
        merged['battle_hours'] = int(v)
    return merged


def validate_answers(answers, settings, existing=None, strict=True):
    """``strict`` (player submits): >= 1 hour and discord_vc required. Admin create/edit: all optional.
    ``existing`` = stored answers: an hour the admin has since removed from the round (start/duration changed) is
    kept when re-sent, so old applications stay editable; a NEW unknown hour is a VALIDATION_ERROR."""
    if answers is None:
        answers = {}
    if not isinstance(answers, dict):
        raise validation_error('answers must be an object', 'answers')
    answers = {k: v for k, v in answers.items() if k not in IGNORED_ANSWER_KEYS}
    unknown = set(answers) - set(ANSWER_KEYS)
    if unknown:
        raise validation_error(f'Unknown answer(s): {", ".join(sorted(unknown))}', 'answers.' + sorted(unknown)[0])
    existing = existing if isinstance(existing, dict) else {}
    hours = battle_hours(settings)
    legacy = [h for h in (existing.get('hours') or []) if isinstance(h, str) and h not in hours]
    allowed = hours + legacy
    raw = answers.get('hours')
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise validation_error('answers.hours must be a list', 'answers.hours')
    picked = set()
    for h in raw:
        if not isinstance(h, str) or h not in allowed:
            raise validation_error(f'answers.hours contains an hour that is not in this battle: {h!r}',
                                   'answers.hours')
        picked.add(h)
    out = {'hours': [h for h in allowed if h in picked]}
    if strict and not out['hours']:
        raise validation_error('Pick at least one battle hour', 'answers.hours')

    vc = answers.get('discord_vc')
    if vc is None or vc == '':
        if strict:
            raise validation_error('discord_vc is required (true or false)', 'answers.discord_vc')
        vc = None
    else:
        vc = validate_bool(vc, 'answers.discord_vc')
    out['discord_vc'] = vc

    lang = answers.get('language')
    if lang is not None and lang not in LANGUAGES:
        raise validation_error('language must be one of ' + ', '.join(LANGUAGES), 'answers.language')
    out['language'] = lang
    return out


def _tier(value, field):
    if value is None or value == '':
        return None
    s = str(value).strip().upper()
    s = s[1:] if s.startswith('T') else s
    if isinstance(value, bool) or not s.isdigit() or int(s) not in TIERS:
        raise validation_error(f'{field} must be T10 or T11 (SVS)', field)
    return int(s)


def validate_troops(value, field='profile.troops', strict=True):
    """SVS troops sent with an application: {infantry|lancer|marksman: {furnace_level: 'FC1'..'FC10', tier: 10|11}}.

    Returns only what was SENT (types/fields left out or blank are absent, see ``merge_troops``). ``strict``: all
    three types need both values (player submits)."""
    if value is None:
        if strict:
            raise validation_error('Troop camp levels and tiers are required', field)
        return {}
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
            entry = {}
        if not isinstance(entry, dict) or set(entry) - {'furnace_level', 'tier'}:
            raise validation_error('troop entry must be {furnace_level, tier}', f)
        camp = validate_fc_level(entry.get('furnace_level'), f + '.furnace_level')
        tier = _tier(entry.get('tier'), f + '.tier')
        if strict and camp is None:
            raise validation_error(f'{kind} camp level is required (FC1-FC10)', f + '.furnace_level')
        if strict and tier is None:
            raise validation_error(f'{kind} tier is required (T10 or T11)', f + '.tier')
        sent = {k: v for k, v in (('furnace_level', camp), ('tier', tier)) if v is not None}
        if sent:
            out[kind] = sent
    return out


def require_complete_troops(troops, field='profile.troops'):
    """Player submits: every troop type needs an FC camp level and a T10/T11 tier (after the merge)."""
    from core.furnace import is_fc
    for kind in TROOP_TYPES:
        entry = troops.get(kind) if isinstance(troops, dict) else None
        entry = entry if isinstance(entry, dict) else {}
        if not is_fc(entry.get('furnace_level')):
            raise validation_error(f'{kind} camp level is required (FC1-FC10)', f'{field}.{kind}.furnace_level')
        if entry.get('tier') not in TIERS:
            raise validation_error(f'{kind} tier is required (T10 or T11)', f'{field}.{kind}.tier')
