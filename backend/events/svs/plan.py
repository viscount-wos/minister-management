"""SVS battle planner (phase 2): one plan per SVS round, a validated JSON document with a revision number.

Owner brief + decisions: catalogue/SVS-battle-setup-brief.md; contract: docs/SPEC.md "SVS battle planner".

Document (what ``PUT /api/admin/svs/rounds/<ref>/plan`` takes and ``validate_plan`` returns, normalised)::

    {strategy: 'single' | 'main_counter',
     show_real_names: bool (default true; the shared view shows a disguised leader's real name too),
     groups: [{id, kind: 'main'|'counter'|'extra', name, alliance_tag, notes,
               min_requirements (main/counter): {infantry|lancer|marksman: {min_camp: 'FC1'..'FC10'|null,
                                                                          min_tier: 10|11|null}},
               players (extra only): [player ref]}],
     leaders: [{id, group_id (a main/counter group), order, player: ref|null,
                disguise: {pfp_hero: slug|null, alias: str|null},
                split: bool,
                rally: {heroes: [slug|null x3], ratio: {inf, lan, mks}|null},
                garrison: {heroes, ratio} | null   (kept while split is off so toggling back loses nothing;
                                                     only SHOWN when split),
                pet_buff: 'open'|'two_hours'|'last_hour'|null,
                named_joiners: [x4 {player: ref|null, rally: {lead_hero, ratio_override},
                                    garrison: {lead_hero, ratio_override}}],
                other_joiner_heroes: {rally: [<=4 slugs, repeats allowed], garrison: [<=4]},
                extra_joiners: [<=14 {player: ref}]}]}

A player ref is ``{fid}`` (a profile / sign-up) or a quick-add ``{name}`` (plan only, "not signed up"); a ref may
carry both (the name is then only a display fallback). Ratios are whole percentages summing to 100. Joiners inherit
the leader's ratio for that side unless ``ratio_override`` is set.

Rules enforced here: a hero must exist and have generation <= the state's hero generation (rare/epic heroes have
none and are always allowed); a hero ALREADY in the stored plan stays allowed after the generation is lowered, so
an old plan stays editable. A player (by FID, or the same quick-add name) may appear only ONCE in the whole plan
(leader, named joiner, extra joiner or an extra group's list): 422 DOUBLE_BOOKED names where they already are.
"""
import hashlib
import json
import re
import secrets

from core.errors import ApiError, validation_error
from core.furnace import validate_fc_level
from events.svs import validation as sv

STRATEGIES = ('single', 'main_counter')
GROUP_KINDS = ('main', 'counter', 'extra')
PET_BUFFS = ('open', 'two_hours', 'last_hour')
RATIO_KEYS = ('inf', 'lan', 'mks')
TROOPS = sv.TROOP_TYPES
HERO_SLOTS = 3
NAMED_JOINERS = 4
OTHER_HEROES = 4
EXTRA_JOINERS = 14
MAX_EXTRA_GROUPS = 5
MAX_LEADERS = 300          # "no limit" in practice; a sanity cap on the document size
MAX_EXTRA_GROUP_PLAYERS = 150
MAX_DOC_BYTES = 400_000
NAME_MAX = 40
ALIAS_MAX = 30
TAG_MAX = 10
NOTES_MAX = 2000

_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,40}$')
_FID_RE = re.compile(r'^[0-9A-Za-z_-]{1,32}$')
TOKEN_RE = re.compile(r'^[A-Za-z0-9_-]{16,64}$')


# ---------------------------------------------------------------- helpers

def pet_buff_times(settings):
    """{'open': '11:00', 'two_hours': '13:00', 'last_hour': '15:00'} from the round's battle start + hours (UTC)."""
    start = settings.get('battle_start') or sv.DEFAULT_START
    n = int(settings.get('battle_hours') or sv.DEFAULT_HOURS)
    h, m = (int(x) for x in start.split(':'))

    def at(plus):
        return f'{(h + plus) % 24:02d}:{m:02d}'
    return {'open': at(0), 'two_hours': at(2), 'last_hour': at(max(0, n - 1))}


def battle_window(settings):
    start = settings.get('battle_start') or sv.DEFAULT_START
    n = int(settings.get('battle_hours') or sv.DEFAULT_HOURS)
    h, m = (int(x) for x in start.split(':'))
    return {'start': start, 'hours': n, 'end': f'{(h + n) % 24:02d}:{m:02d}'}


def empty_plan():
    return {'strategy': 'main_counter', 'show_real_names': True,
            'groups': [_blank_group('main', 'main'), _blank_group('counter', 'counter')], 'leaders': []}


def _blank_group(gid, kind):
    g = {'id': gid, 'kind': kind, 'name': None, 'alliance_tag': None, 'notes': None}
    if kind == 'extra':
        g['players'] = []
    else:
        g['min_requirements'] = {t: {'min_camp': None, 'min_tier': None} for t in TROOPS}
    return g


def player_key(ref):
    """Double-booking identity: 'fid:<fid>' or 'name:<casefolded quick-add name>'."""
    if not ref:
        return None
    if ref.get('fid'):
        return 'fid:' + ref['fid']
    return 'name:' + ' '.join(ref['name'].split()).casefold()


def _obj(v, field):
    if v is None:
        return {}
    if not isinstance(v, dict):
        raise validation_error(f'{field} must be an object', field)
    return v


def _list(v, field, max_len):
    if v is None:
        return []
    if not isinstance(v, list):
        raise validation_error(f'{field} must be a list', field)
    if len(v) > max_len:
        raise validation_error(f'{field} has more than {max_len} entries', field)
    return v


def _text(v, field, max_len):
    if v is None:
        return None
    if not isinstance(v, str):
        raise validation_error(f'{field} must be text', field)
    v = v.strip()
    if len(v) > max_len:
        raise validation_error(f'{field} is longer than {max_len} characters', field)
    return v or None


def _id(v, field):
    if not isinstance(v, str) or not _ID_RE.match(v):
        raise validation_error(f'{field} must be an id (letters, digits, _ or -, up to 40)', field)
    return v


def _bool(v, field, default):
    if v is None:
        return default
    if not isinstance(v, bool):
        raise validation_error(f'{field} must be true or false', field)
    return v


def player_ref(v, field, allow_none=True):
    if v is None:
        if allow_none:
            return None
        raise validation_error(f'{field} is required', field)
    if not isinstance(v, dict):
        raise validation_error(f'{field} must be {{fid}} or {{name}}', field)
    fid = v.get('fid')
    name = _text(v.get('name'), field + '.name', NAME_MAX)
    if fid not in (None, ''):
        fid = str(fid).strip() if isinstance(fid, (str, int)) and not isinstance(fid, bool) else None
        if not fid or not _FID_RE.match(fid):
            raise validation_error(f'{field}.fid is not a valid FID', field + '.fid')
        out = {'fid': fid}
        if name:
            out['name'] = name
        return out
    if not name:
        raise validation_error(f'{field} needs an FID or a name', field)
    return {'name': name}


def ratio(v, field):
    if v is None:
        return None
    if not isinstance(v, dict) or set(v) - set(RATIO_KEYS):
        raise validation_error(f'{field} must be {{inf, lan, mks}}', field)
    out = {}
    for k in RATIO_KEYS:
        n = v.get(k, 0)
        if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= 100:
            raise validation_error(f'{field}.{k} must be a whole number 0-100', f'{field}.{k}')
        out[k] = n
    if sum(out.values()) != 100:
        raise validation_error(f'{field} must add up to 100 (now {sum(out.values())})', field,
                               details={'total': sum(out.values())})
    return out


class HeroCheck:
    """Validates hero slugs against the library and the state's generation (stored heroes stay allowed)."""

    def __init__(self, library_heroes, max_gen, allowed_legacy=()):
        self.by_slug = {h['slug']: h for h in library_heroes}
        self.max_gen = max_gen
        self.legacy = set(allowed_legacy)

    def __call__(self, v, field):
        if v in (None, ''):
            return None
        if not isinstance(v, str) or v not in self.by_slug:
            raise validation_error(f'{field}: unknown hero {v!r}', field)
        gen = self.by_slug[v]['generation']
        if gen is not None and gen > self.max_gen and v not in self.legacy:
            raise validation_error(
                f'{field}: {self.by_slug[v]["name"]} is generation {gen}, above the state\'s hero generation '
                f'{self.max_gen}', field, details={'hero': v, 'generation': gen, 'state_generation': self.max_gen})
        return v


def plan_heroes(plan):
    """Every hero slug used anywhere in a (normalised) plan."""
    out = set()
    for ld in plan.get('leaders') or []:
        out.add((ld.get('disguise') or {}).get('pfp_hero'))
        for side in ('rally', 'garrison'):
            out.update(((ld.get(side) or {}).get('heroes')) or [])
            out.update(((ld.get('other_joiner_heroes') or {}).get(side)) or [])
        for j in ld.get('named_joiners') or []:
            for side in ('rally', 'garrison'):
                out.add((j.get(side) or {}).get('lead_hero'))
    out.discard(None)
    return out


# ---------------------------------------------------------------- validation

def _min_requirements(v, field):
    v = _obj(v, field)
    if set(v) - set(TROOPS):
        raise validation_error(f'{field}: unknown troop type', field)
    out = {}
    for t in TROOPS:
        e = _obj(v.get(t), f'{field}.{t}')
        camp = validate_fc_level(e.get('min_camp'), f'{field}.{t}.min_camp')
        tier = e.get('min_tier')
        if tier in (None, ''):
            tier = None
        else:
            s = str(tier).strip().upper().lstrip('T')
            if isinstance(tier, bool) or not s.isdigit() or int(s) not in sv.TIERS:
                raise validation_error(f'{field}.{t}.min_tier must be 10 or 11', f'{field}.{t}.min_tier')
            tier = int(s)
        out[t] = {'min_camp': camp, 'min_tier': tier}
    return out


def _group(v, field):
    v = _obj(v, field)
    kind = v.get('kind')
    if kind not in GROUP_KINDS:
        raise validation_error(f'{field}.kind must be main, counter or extra', field + '.kind')
    g = {'id': _id(v.get('id'), field + '.id'), 'kind': kind,
         'name': _text(v.get('name'), field + '.name', NAME_MAX),
         'alliance_tag': _text(v.get('alliance_tag'), field + '.alliance_tag', TAG_MAX),
         'notes': _text(v.get('notes'), field + '.notes', NOTES_MAX)}
    if kind == 'extra':
        g['players'] = [player_ref(p, f'{field}.players[{i}]', allow_none=False)
                        for i, p in enumerate(_list(v.get('players'), field + '.players', MAX_EXTRA_GROUP_PLAYERS))]
    else:
        g['min_requirements'] = _min_requirements(v.get('min_requirements'), field + '.min_requirements')
    return g


def _side(v, field, hero):
    v = _obj(v, field)
    raw = _list(v.get('heroes'), field + '.heroes', HERO_SLOTS)
    heroes = [hero(h, f'{field}.heroes[{i}]') for i, h in enumerate(raw)]
    heroes += [None] * (HERO_SLOTS - len(heroes))
    seen = [h for h in heroes if h]
    if len(seen) != len(set(seen)):
        raise validation_error(f'{field}.heroes: the same hero twice in one march', field + '.heroes')
    return {'heroes': heroes, 'ratio': ratio(v.get('ratio'), field + '.ratio')}


def _joiner_side(v, field, hero):
    v = _obj(v, field)
    return {'lead_hero': hero(v.get('lead_hero'), field + '.lead_hero'),
            'ratio_override': ratio(v.get('ratio_override'), field + '.ratio_override')}


def _leader(v, field, hero, group_ids):
    v = _obj(v, field)
    gid = v.get('group_id')
    if gid not in group_ids:
        raise validation_error(f'{field}.group_id must name a main or counter group', field + '.group_id')
    order = v.get('order', 0)
    if isinstance(order, bool) or not isinstance(order, int):
        raise validation_error(f'{field}.order must be a whole number', field + '.order')
    disguise = _obj(v.get('disguise'), field + '.disguise')
    split = _bool(v.get('split'), field + '.split', False)
    garrison = v.get('garrison')
    joiners_raw = _list(v.get('named_joiners'), field + '.named_joiners', NAMED_JOINERS)
    joiners = []
    for i, j in enumerate(joiners_raw):
        jf = f'{field}.named_joiners[{i}]'
        j = _obj(j, jf)
        joiners.append({'player': player_ref(j.get('player'), jf + '.player'),
                        'rally': _joiner_side(j.get('rally'), jf + '.rally', hero),
                        'garrison': _joiner_side(j.get('garrison'), jf + '.garrison', hero)})
    while len(joiners) < NAMED_JOINERS:
        joiners.append({'player': None, 'rally': {'lead_hero': None, 'ratio_override': None},
                        'garrison': {'lead_hero': None, 'ratio_override': None}})
    other = _obj(v.get('other_joiner_heroes'), field + '.other_joiner_heroes')
    other_out = {}
    for side in ('rally', 'garrison'):
        sf = f'{field}.other_joiner_heroes.{side}'
        other_out[side] = [h for h in (hero(x, f'{sf}[{i}]') for i, x in
                                       enumerate(_list(other.get(side), sf, OTHER_HEROES))) if h]
    extras = []
    for i, e in enumerate(_list(v.get('extra_joiners'), field + '.extra_joiners', EXTRA_JOINERS)):
        ef = f'{field}.extra_joiners[{i}]'
        e = _obj(e, ef)
        ref = player_ref(e.get('player'), ef + '.player')
        if ref:
            extras.append({'player': ref})
    pet = v.get('pet_buff')
    if pet in ('', None):
        pet = None
    elif pet not in PET_BUFFS:
        raise validation_error(f'{field}.pet_buff must be open, two_hours or last_hour', field + '.pet_buff')
    return {
        'id': _id(v.get('id'), field + '.id'),
        'group_id': gid,
        'order': order,
        'player': player_ref(v.get('player'), field + '.player'),
        'disguise': {'pfp_hero': hero(disguise.get('pfp_hero'), field + '.disguise.pfp_hero'),
                     'alias': _text(disguise.get('alias'), field + '.disguise.alias', ALIAS_MAX)},
        'split': split,
        'rally': _side(v.get('rally'), field + '.rally', hero),
        'garrison': _side(garrison, field + '.garrison', hero) if (garrison is not None or split) else None,
        'pet_buff': pet,
        'named_joiners': joiners,
        'other_joiner_heroes': other_out,
        'extra_joiners': extras,
    }


def validate_plan(doc, hero):
    """Normalise + validate a plan document (structure, sizes, ratios, heroes). Double booking: ``check_double``."""
    if not isinstance(doc, dict):
        raise validation_error('plan must be an object', 'plan')
    if len(json.dumps(doc)) > MAX_DOC_BYTES:
        raise validation_error('plan is too large', 'plan')
    strategy = doc.get('strategy')
    if strategy not in STRATEGIES:
        raise validation_error('plan.strategy must be single or main_counter', 'plan.strategy')
    groups = [_group(g, f'plan.groups[{i}]') for i, g in
              enumerate(_list(doc.get('groups'), 'plan.groups', 2 + MAX_EXTRA_GROUPS))]
    ids = [g['id'] for g in groups]
    if len(ids) != len(set(ids)):
        raise validation_error('plan.groups: duplicate group id', 'plan.groups')
    kinds = [g['kind'] for g in groups]
    want_counter = 1 if strategy == 'main_counter' else 0
    if kinds.count('main') != 1 or kinds.count('counter') != want_counter:
        raise validation_error('plan.groups: a single plan has one main group; main + counter has one of each',
                               'plan.groups')
    if kinds.count('extra') > MAX_EXTRA_GROUPS:
        raise validation_error(f'plan.groups: at most {MAX_EXTRA_GROUPS} extra groups', 'plan.groups')
    # main, counter, then extras (in their own order)
    rank = {'main': 0, 'counter': 1, 'extra': 2}
    groups.sort(key=lambda g: rank[g['kind']])
    battle_ids = {g['id'] for g in groups if g['kind'] != 'extra'}
    leaders = [_leader(ld, f'plan.leaders[{i}]', hero, battle_ids)
               for i, ld in enumerate(_list(doc.get('leaders'), 'plan.leaders', MAX_LEADERS))]
    lids = [ld['id'] for ld in leaders]
    if len(lids) != len(set(lids)):
        raise validation_error('plan.leaders: duplicate leader id', 'plan.leaders')
    # Stable order: group order, then the given order, then position; renumbered 0.. per group.
    gpos = {g['id']: i for i, g in enumerate(groups)}
    leaders = [ld for _, ld in sorted(enumerate(leaders), key=lambda p: (gpos[p[1]['group_id']], p[1]['order'], p[0]))]
    counters = {}
    for ld in leaders:
        ld['order'] = counters.get(ld['group_id'], 0)
        counters[ld['group_id']] = ld['order'] + 1
    return {'strategy': strategy, 'show_real_names': _bool(doc.get('show_real_names'), 'plan.show_real_names', True),
            'groups': groups, 'leaders': leaders}


# ---------------------------------------------------------------- double booking

def iter_placements(plan):
    """(ref, field path, where) for every placed player, in plan order. ``where`` = {group_id, leader_id, position,
    slot}. Paths use the NORMALISED order (leaders sorted by group then order)."""
    for i, ld in enumerate(plan['leaders']):
        base = {'group_id': ld['group_id'], 'leader_id': ld['id']}
        if ld['player']:
            yield ld['player'], f'plan.leaders[{i}].player', dict(base, position='leader', slot=None)
        for j, nj in enumerate(ld['named_joiners']):
            if nj['player']:
                yield nj['player'], f'plan.leaders[{i}].named_joiners[{j}].player', \
                    dict(base, position='named_joiner', slot=j)
        for j, ej in enumerate(ld['extra_joiners']):
            yield ej['player'], f'plan.leaders[{i}].extra_joiners[{j}].player', dict(base, position='extra_joiner', slot=j)
    for gi, g in enumerate(plan['groups']):
        for j, p in enumerate(g.get('players') or []):
            yield p, f'plan.groups[{gi}].players[{j}]', {'group_id': g['id'], 'leader_id': None,
                                                         'position': 'extra_group', 'slot': j}


def leader_labels(plan, names):
    """leader id -> how the planner names a leader: alias, else the player's name, else 'Leader N'."""
    out = {}
    numbers = {}
    for ld in plan['leaders']:
        numbers[ld['group_id']] = numbers.get(ld['group_id'], 0) + 1
        alias = ld['disguise']['alias']
        out[ld['id']] = alias or (display_name(ld['player'], names) if ld['player'] else None) \
            or f'Leader {numbers[ld["group_id"]]}'
    return out


def display_name(ref, names):
    if not ref:
        return None
    if ref.get('fid'):
        prof = names.get(ref['fid'])
        if prof and prof.get('game_name'):
            return prof['game_name']
        return ref.get('name') or f'FID {ref["fid"]}'
    return ref['name']


def check_double(plan, names):
    seen = {}
    labels = None
    groups = {g['id']: g for g in plan['groups']}
    for ref, path, where in iter_placements(plan):
        key = player_key(ref)
        if key in seen:
            labels = labels or leader_labels(plan, names)
            first = seen[key]
            g = groups[first['group_id']]
            details = dict(first, group_name=g['name'], group_kind=g['kind'],
                           leader_label=labels.get(first['leader_id']) if first['leader_id'] else None,
                           player=ref, player_name=display_name(ref, names))
            who = details['player_name']
            place = details['leader_label'] or g['name'] or g['kind']
            raise ApiError(422, 'DOUBLE_BOOKED', f'{who} is already in this plan ({place}); move them instead',
                           field=path, details=details)
        seen[key] = where


# ---------------------------------------------------------------- views

def _hero_obj(slug, by_slug):
    if not slug:
        return None
    h = by_slug.get(slug)
    if not h:
        return {'slug': slug, 'name': slug, 'troop': None, 'generation': None, 'image': None}
    return {'slug': h['slug'], 'name': h['name'], 'troop': h['troop'], 'generation': h['generation'],
            'rarity': h['rarity'], 'image': h['image']}


def _person(ref, names, hide=False):
    if not ref or hide:
        return None
    prof = names.get(ref['fid']) if ref.get('fid') else None
    return {'name': display_name(ref, names), 'fid': ref.get('fid'),
            'alliance': (prof or {}).get('alliance')}


def resolve_view(plan, settings, names, by_slug, public=True):
    """The read-only plan: groups in order, each with its leaders in order, heroes as objects, effective ratios
    (joiners inherit the leader's side ratio unless overridden), pet-buff times. ``public`` + show_real_names off:
    a disguised leader (alias set) is shown by alias only (no real name, no FID)."""
    times = pet_buff_times(settings)
    hide_real = public and not plan.get('show_real_names', True)
    out_groups = []
    for g in plan['groups']:
        og = {'id': g['id'], 'kind': g['kind'], 'name': g['name'], 'alliance_tag': g['alliance_tag'],
              'notes': g['notes']}
        if g['kind'] == 'extra':
            og['players'] = [_person(p, names) for p in g.get('players') or []]
        else:
            og['min_requirements'] = g['min_requirements']
            og['leaders'] = []
        out_groups.append(og)
    by_id = {g['id']: g for g in out_groups}
    for ld in plan['leaders']:
        g = by_id[ld['group_id']]
        alias = ld['disguise']['alias']
        sides = ['rally', 'garrison'] if ld['split'] else ['rally']
        entry = {
            'id': ld['id'],
            'number': len(g['leaders']) + 1,
            'player': _person(ld['player'], names, hide=hide_real and bool(alias)),
            'alias': alias,
            'pfp_hero': _hero_obj(ld['disguise']['pfp_hero'], by_slug),
            'split': ld['split'],
            'pet_buff': ld['pet_buff'],
            'pet_buff_time': times.get(ld['pet_buff']) if ld['pet_buff'] else None,
            'named_joiners': [],
            'extra_joiners': [_person(e['player'], names) for e in ld['extra_joiners']],
        }
        for side in sides:
            s = ld[side] or {'heroes': [None] * HERO_SLOTS, 'ratio': None}
            entry[side] = {'heroes': [_hero_obj(h, by_slug) for h in s['heroes']], 'ratio': s['ratio'],
                           'other_joiner_heroes': [_hero_obj(h, by_slug) for h in ld['other_joiner_heroes'][side]]}
        if not ld['split']:
            entry['garrison'] = None
        for nj in ld['named_joiners']:
            if not nj['player']:
                continue
            j = {'player': _person(nj['player'], names)}
            for side in sides:
                js = nj[side]
                lead_ratio = (ld[side] or {}).get('ratio')
                j[side] = {'lead_hero': _hero_obj(js['lead_hero'], by_slug),
                           'ratio': js['ratio_override'] or lead_ratio,
                           'ratio_overridden': bool(js['ratio_override'])}
            entry['named_joiners'].append(j)
        g['leaders'].append(entry)
    return {'strategy': plan['strategy'], 'show_real_names': plan.get('show_real_names', True),
            'battle': battle_window(settings), 'pet_buff_times': times, 'groups': out_groups}


# ---------------------------------------------------------------- storage

def token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def new_token():
    return secrets.token_urlsafe(16)  # 128 random bits, 22 URL-safe characters


def load_row(db, round_id):
    return db.execute('SELECT * FROM svs_plans WHERE round_id = ?', (round_id,)).fetchone()


def stored_plan(row):
    if not row:
        return empty_plan()
    try:
        doc = json.loads(row['plan'] or '{}')
    except ValueError:
        doc = {}
    return doc if doc.get('strategy') in STRATEGIES else empty_plan()


def share_info(row):
    token = row['share_token'] if row else None
    return {'enabled': bool(token), 'token': token, 'path': f'/svs/plan/{token}' if token else None,
            'created_at': row['share_created_at'] if row and token else None}


def plan_fids(plan):
    return sorted({ref['fid'] for ref, _, _ in iter_placements(plan) if ref.get('fid')})


def people(db, fids, round_id):
    """fid -> {game_name, alliance, signed_up} for the FIDs a plan names (one query each way)."""
    if not fids:
        return {}
    out = {}
    marks = ','.join('?' * len(fids))
    for r in db.execute(f'SELECT p.fid, p.game_name, p.alliance, '
                        f'EXISTS(SELECT 1 FROM applications a WHERE a.player_id = p.id AND a.round_id = ?) AS su '
                        f'FROM profiles p WHERE p.fid IN ({marks})', [round_id, *fids]).fetchall():
        out[r['fid']] = {'game_name': r['game_name'], 'alliance': r['alliance'], 'signed_up': bool(r['su'])}
    return out
