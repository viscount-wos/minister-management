"""Hero library (foundation for the SVS planner): GET /api/heroes.

Data: ``gamedata/heroes.json`` (versioned, built by scripts/heroes/build_heroes.py): per hero slug, name, troop
(infantry|lancer|marksman), generation (1..17, or null for the rare/epic heroes that have none), rarity
(rare|epic|mythic) and image (``/heroes/<slug>.webp``, a static file of the SPA). Hero names and artwork are
(c) Century Games; every page that shows heroes carries a small credit line.

``max_gen`` defaults to the state's hero generation (global setting ``state_generation``): a state on generation 8
never sees generation 9+ heroes. Heroes without a generation (rare/epic) are always included and flagged
``has_generation: false``.
"""
import json
import os
from functools import lru_cache

from flask import Blueprint, jsonify, request

from core.errors import validation_error

bp = Blueprint('heroes', __name__)

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'gamedata', 'heroes.json')
TROOPS = ('infantry', 'lancer', 'marksman')


@lru_cache(maxsize=1)
def library():
    with open(DATA_FILE, encoding='utf-8') as fh:
        doc = json.load(fh)
    doc['max_generation'] = max((h['generation'] or 0) for h in doc['heroes'])
    return doc


def heroes(max_gen, troop=None):
    out = []
    for h in library()['heroes']:
        if h['generation'] is not None and h['generation'] > max_gen:
            continue
        if troop and h['troop'] != troop:
            continue
        out.append(dict(h, has_generation=h['generation'] is not None))
    return out


@bp.route('/api/heroes', methods=['GET'])
def get_heroes():
    """?max_gen=1..17 (default: the state's hero generation) &troop=infantry|lancer|marksman (optional)."""
    from core.settings import state_generation, validate_generation
    raw = request.args.get('max_gen')
    max_gen = state_generation() if raw in (None, '') else validate_generation(raw, 'max_gen')
    troop = (request.args.get('troop') or '').strip().lower() or None
    if troop is not None and troop not in TROOPS:
        raise validation_error('troop must be one of ' + ', '.join(TROOPS), 'troop')
    lib = library()
    items = heroes(max_gen, troop)
    return jsonify({
        'version': lib['version'],
        'state_generation': state_generation(),
        'max_gen': max_gen,
        'max_generation': lib['max_generation'],
        'attribution': lib['attribution'],
        'total': len(items),
        'heroes': items,
    })
