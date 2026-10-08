"""Small, reusable input validators. All raise VALIDATION_ERROR with a field name."""
import json
import re
from datetime import datetime, timezone

from core.errors import validation_error

FID_RE = re.compile(r'^\d{1,20}$')


def now_iso():
    """Current UTC time as ISO-8601 with a trailing Z (second precision)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def parse_iso_utc(value):
    """Parse an ISO datetime string to an aware UTC datetime. Naive => UTC. Raises ValueError."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError('empty datetime')
    dt = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_iso_utc(dt):
    return dt.replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def normalize_legacy_timestamp(value):
    """'2026-03-01 12:00:00' (SQLite CURRENT_TIMESTAMP, UTC) -> '2026-03-01T12:00:00Z'."""
    if not value:
        return None
    try:
        return to_iso_utc(parse_iso_utc(str(value)))
    except ValueError:
        return str(value)


def validate_closing_time(value, field='closing_time'):
    """None/'' clears; otherwise must be an ISO datetime. Returns normalized UTC string or None."""
    if value is None or value == '':
        return None
    try:
        return to_iso_utc(parse_iso_utc(value))
    except (ValueError, TypeError):
        raise validation_error('Invalid datetime format (expected ISO-8601, e.g. 2026-10-13T18:00:00Z)', field)


def is_past(iso_value):
    if not iso_value:
        return False
    try:
        return datetime.now(timezone.utc) >= parse_iso_utc(iso_value)
    except ValueError:
        return False


def validate_fid(value, field='fid'):
    fid = str(value if value is not None else '').strip()
    if not fid:
        raise validation_error('FID is required', field)
    if not FID_RE.match(fid):
        raise validation_error('FID must contain digits only (max 20)', field)
    return fid


def validate_str(value, field, max_len, required=False, upper=False):
    if value is None:
        if required:
            raise validation_error(f'{field} is required', field)
        return None
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise validation_error(f'{field} must be a string', field)
    s = str(value).strip()
    if not s:
        if required:
            raise validation_error(f'{field} is required', field)
        return None
    if len(s) > max_len:
        raise validation_error(f'{field} must be at most {max_len} characters', field)
    return s.upper() if upper else s


def validate_number(value, field, minimum=0, maximum=99999, integer=False, nullable=False, default=0):
    """Numbers per v1.4 rules: non-negative, <= 99999 by default. Accepts numeric strings."""
    if value is None or value == '':
        if nullable:
            return None
        return default
    if isinstance(value, bool):
        raise validation_error(f'Invalid value for {field}', field)
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise validation_error(f'Invalid value for {field}', field)
    if num != num or num in (float('inf'), float('-inf')):
        raise validation_error(f'Invalid value for {field}', field)
    if integer:
        if num != int(num):
            raise validation_error(f'{field} must be a whole number', field)
        num = int(num)
    if num < minimum:
        raise validation_error(f'{field} cannot be negative' if minimum == 0 else f'{field} must be >= {minimum}', field)
    if num > maximum:
        raise validation_error(f'{field} exceeds maximum allowed value ({maximum})', field)
    return num


def validate_bool(value, field):
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.lower() in ('true', 'false'):
        return value.lower() == 'true'
    raise validation_error(f'{field} must be true or false', field)


def validate_json_blob(value, field, max_bytes=20000):
    """Free-form JSON object/array (e.g. troops). Returns the value (stored as JSON text by caller)."""
    if value is None:
        return None
    if not isinstance(value, (dict, list)):
        raise validation_error(f'{field} must be a JSON object or array', field)
    if len(json.dumps(value)) > max_bytes:
        raise validation_error(f'{field} is too large', field)
    return value
