"""Furnace levels, shared by every event (owner rule, phase 2).

Two kinds: pre-FC furnaces 1-30 and Fire Crystal furnaces FC1-FC10 (nothing above FC10).
Stored everywhere as a canonical STRING code: 'FC1'..'FC10' or '1'..'30'.
Order (UI dropdowns, sorting, stats): FC10 highest, FC9 ... FC1, then 30, 29 ... 1.
"""
import re

from core.errors import validation_error

FC_MAX = 10
PRE_FC_MAX = 30
# Display / dropdown order, highest first.
FURNACE_LEVELS = tuple([f'FC{n}' for n in range(FC_MAX, 0, -1)] + [str(n) for n in range(PRE_FC_MAX, 0, -1)])
_CODE_RE = re.compile(r'^(?:FC([1-9]|10)|([1-9]|[12]\d|30))$')


def normalize_furnace(value):
    """Canonical code for ``value`` ('fc5' -> 'FC5', 30 -> '30', ' 7 ' -> '7') or None if not a valid level."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value) if 1 <= value <= PRE_FC_MAX else None
    if isinstance(value, float):
        return normalize_furnace(int(value)) if value.is_integer() else None
    if not isinstance(value, str):
        return None
    s = value.strip().upper().replace(' ', '')
    return s if _CODE_RE.match(s) else None


def validate_furnace(value, field='furnace_level'):
    """None/'' -> None; otherwise a valid code (FC1-FC10, 1-30) or VALIDATION_ERROR."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    code = normalize_furnace(value)
    if code is None:
        raise validation_error(f'{field} must be one of FC1-FC10 or 1-30', field)
    return code


def furnace_ordinal(code):
    """Sort/compare key: '1' -> 1 ... '30' -> 30, 'FC1' -> 31 ... 'FC10' -> 40. None/invalid -> 0."""
    c = normalize_furnace(code)
    if c is None:
        return 0
    return PRE_FC_MAX + int(c[2:]) if c.startswith('FC') else int(c)
