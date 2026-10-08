"""Ministry input validation (answers + per-round settings). Numeric limits match v1.4."""
import re

from core.errors import validation_error
from core.validation import validate_bool, validate_number

SPEEDUP_FIELDS = ('construction_speedups_days', 'research_speedups_days',
                  'troop_training_speedups_days', 'general_speedups_days')
CRYSTAL_FIELDS = ('fire_crystals', 'refined_fire_crystals', 'fire_crystal_shards')
NUMERIC_FIELDS = SPEEDUP_FIELDS + CRYSTAL_FIELDS
DAY_TYPES = ('construction', 'research', 'troop')
SCHEMES = ('exact_alignment', 'max_slots')
RESEARCH_DAYS = ('tuesday', 'friday')
MAX_VALUE = 99999

_PREF_RE = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')

DEFAULT_SETTINGS = {
    'research_day': 'tuesday',
    'show_fire_crystals': False,
    'time_slot_scheme': 'exact_alignment',
    'published_days': [],
}


def _validate_slot_list(value, field):
    if value is None:
        return []
    if not isinstance(value, list):
        raise validation_error(f'{field} must be a list of HH:MM strings', field)
    out = []
    for v in value:
        if not isinstance(v, str) or not _PREF_RE.match(v.strip()):
            raise validation_error(f'{field} contains an invalid time {v!r} (expected HH:MM)', field)
        v = v.strip()
        if v not in out:
            out.append(v)
    if len(out) > 48:
        raise validation_error(f'{field} has too many entries', field)
    return sorted(out)  # HH:MM is zero-padded: lexical = chronological (v1.4 read them back sorted)


def _is_unchanged_fraction(value, stored):
    """A fractional crystal value imported from v1.4 (e.g. 12.5), re-sent unchanged."""
    if not isinstance(stored, float) or stored.is_integer() or isinstance(value, bool) or value is None:
        return False
    try:
        return float(value) == stored
    except (TypeError, ValueError):
        return False


def validate_answers(answers, existing=None):
    """Normalise ministry answers. Missing numbers default to 0 (as v1.4).

    Crystal counts must be whole numbers, except that a fractional value imported from v1.4
    (v1.4 accepted e.g. 12.5) is kept when re-sent unchanged (``existing`` = stored answers),
    so legacy players and admins can still save those applications.
    """
    if answers is None:
        answers = {}
    if not isinstance(answers, dict):
        raise validation_error('answers must be an object', 'answers')
    existing = existing if isinstance(existing, dict) else {}
    out = {}
    for f in SPEEDUP_FIELDS:
        out[f] = float(validate_number(answers.get(f), 'answers.' + f, maximum=MAX_VALUE))
    for f in CRYSTAL_FIELDS:
        if _is_unchanged_fraction(answers.get(f), existing.get(f)):
            out[f] = existing[f]
        else:
            out[f] = validate_number(answers.get(f), 'answers.' + f, maximum=MAX_VALUE, integer=True)
    by_day = answers.get('time_slots_by_day')
    legacy_list = answers.get('time_slots')
    if by_day is None and legacy_list is not None:
        # v1.4 legacy: one list applied to every day type
        slots = _validate_slot_list(legacy_list, 'answers.time_slots')
        by_day = {t: list(slots) for t in DAY_TYPES}
    if by_day is None:
        by_day = {}
    if not isinstance(by_day, dict):
        raise validation_error('time_slots_by_day must be an object', 'answers.time_slots_by_day')
    unknown = set(by_day) - set(DAY_TYPES)
    if unknown:
        raise validation_error(f'Unknown day type(s): {", ".join(sorted(unknown))}', 'answers.time_slots_by_day')
    out['time_slots_by_day'] = {t: _validate_slot_list(by_day.get(t), f'answers.time_slots_by_day.{t}')
                                for t in DAY_TYPES}
    return out


def validate_settings(incoming, current, valid_days_fn):
    if not isinstance(incoming, dict):
        raise validation_error('settings must be an object', 'settings')
    merged = dict(DEFAULT_SETTINGS)
    merged.update(current)
    unknown = set(incoming) - set(DEFAULT_SETTINGS) - {'legacy_closing_time_raw'}
    if unknown:
        raise validation_error(f'Unknown setting(s): {", ".join(sorted(unknown))}', 'settings')
    if 'research_day' in incoming:
        rd = str(incoming['research_day'] or '').lower()
        if rd not in RESEARCH_DAYS:
            raise validation_error('research_day must be "tuesday" or "friday"', 'settings.research_day')
        merged['research_day'] = rd
    if 'show_fire_crystals' in incoming:
        merged['show_fire_crystals'] = validate_bool(incoming['show_fire_crystals'], 'settings.show_fire_crystals')
    if 'time_slot_scheme' in incoming:
        if incoming['time_slot_scheme'] not in SCHEMES:
            raise validation_error('time_slot_scheme must be "exact_alignment" or "max_slots"',
                                   'settings.time_slot_scheme')
        merged['time_slot_scheme'] = incoming['time_slot_scheme']
    if 'published_days' in incoming:
        days = incoming['published_days']
        if not isinstance(days, list):
            raise validation_error('published_days must be a list', 'settings.published_days')
        valid = valid_days_fn(merged['research_day'])
        clean = []
        for d in days:
            d = str(d).lower()
            if d not in valid:
                raise validation_error(f'Invalid day {d!r}', 'settings.published_days')
            if d not in clean:
                clean.append(d)
        merged['published_days'] = clean
    return merged


def validate_day(day, research_day):
    d = str(day or '').lower()
    if d not in ('monday', research_day, 'thursday'):
        raise validation_error('Invalid day', 'day')
    return d
