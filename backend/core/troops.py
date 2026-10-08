"""Shared per-FID troop data (profile ``troops``): one merge rule for every event that writes it.

Shape: {infantry|lancer|marksman: {furnace_level: CAMP level code or null, tier: int or null}} (the key name
``furnace_level`` is kept for compatibility: it is the troop type's CAMP level, see docs/SPEC.md).
"""

TROOP_TYPES = ('infantry', 'lancer', 'marksman')


def stored_troops(row):
    """The ``troops`` of a stored profile row (JSON text) as a dict, or {}."""
    import json
    if row is None:
        return {}
    try:
        raw = row['troops']
    except (KeyError, IndexError, TypeError):
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        val = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}
    return val if isinstance(val, dict) else {}


def merge_troops(stored, sent):
    """The shared-profile troop merge rule (SVS, and Frost Dragon Tyrant since v2.2.0).

    Per troop type and per field (camp ``furnace_level``, ``tier``): a value that was sent replaces the stored one
    (the player's latest statement, as for every profile field); a blank/missing value never clears a stored one;
    troop types, fields and extra keys that were not sent stay exactly as stored. So an SVS sign-up (T10/T11 only)
    or an admin "add player" with half the troops filled in never wipes the richer data another event saved.
    """
    base = stored if isinstance(stored, dict) else {}
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    for kind in TROOP_TYPES:
        sent_entry = (sent or {}).get(kind)
        if not isinstance(sent_entry, dict):
            if kind not in out:
                out[kind] = {'furnace_level': None, 'tier': None}
            continue
        entry = out.get(kind) if isinstance(out.get(kind), dict) else {}
        entry = {'furnace_level': entry.get('furnace_level'), 'tier': entry.get('tier'),
                 **{k: v for k, v in entry.items() if k not in ('furnace_level', 'tier')}}
        for key in ('furnace_level', 'tier'):
            if sent_entry.get(key) is not None:
                entry[key] = sent_entry[key]
        out[kind] = entry
    return out
