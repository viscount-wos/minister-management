// SVS battle planner: plan document types (docs/SPEC.md "SVS battle planner", backend events/svs/plan.py) and pure
// helpers shared by the planner (admin) and the shared plan view.

import type { Hero, HeroTroop } from '../../../shared/heroes/api';

export type Strategy = 'single' | 'main_counter';
export type GroupKind = 'main' | 'counter' | 'extra';
export type PetBuff = 'open' | 'two_hours' | 'last_hour';
export type Side = 'rally' | 'garrison';
export type TroopKey = HeroTroop;
export const PET_BUFFS: PetBuff[] = ['open', 'two_hours', 'last_hour'];
export const TROOPS: TroopKey[] = ['infantry', 'lancer', 'marksman'];
export const RATIO_KEYS = ['inf', 'lan', 'mks'] as const;
export type RatioKey = (typeof RATIO_KEYS)[number];
export const RATIO_TROOP: Record<RatioKey, TroopKey> = { inf: 'infantry', lan: 'lancer', mks: 'marksman' };
export const NAMED_JOINERS = 4;
export const OTHER_HEROES = 4;
export const EXTRA_JOINERS = 14;
export const MAX_EXTRA_GROUPS = 5;

export interface Ratio {
  inf: number;
  lan: number;
  mks: number;
}

/** {fid} = a profile / sign-up; {name} = a quick-add kept in the plan only ("not signed up"). */
export interface PlayerRef {
  fid?: string;
  name?: string;
}

export interface MinReq {
  min_camp: string | null;
  min_tier: number | null;
}

export interface PlanGroup {
  id: string;
  kind: GroupKind;
  name: string | null;
  alliance_tag: string | null;
  notes: string | null;
  min_requirements?: Record<TroopKey, MinReq>;
  players?: PlayerRef[];
}

export interface March {
  heroes: (string | null)[];
  ratio: Ratio | null;
}

export interface JoinerSide {
  lead_hero: string | null;
  ratio_override: Ratio | null;
}

export interface NamedJoiner {
  player: PlayerRef | null;
  rally: JoinerSide;
  garrison: JoinerSide;
}

export interface Leader {
  id: string;
  group_id: string;
  order: number;
  player: PlayerRef | null;
  disguise: { pfp_hero: string | null; alias: string | null };
  split: boolean;
  rally: March;
  garrison: March | null;
  pet_buff: PetBuff | null;
  named_joiners: NamedJoiner[];
  other_joiner_heroes: { rally: string[]; garrison: string[] };
  extra_joiners: { player: PlayerRef }[];
}

export interface PlanDoc {
  strategy: Strategy;
  show_real_names: boolean;
  groups: PlanGroup[];
  leaders: Leader[];
}

export interface ShareInfo {
  enabled: boolean;
  token: string | null;
  path: string | null;
  created_at: string | null;
}

export interface Person {
  game_name: string;
  alliance: string | null;
  signed_up: boolean;
}

export interface PlanResponse {
  round_id: number;
  round_name: string;
  revision: number;
  updated_at: string | null;
  plan: PlanDoc;
  share: ShareInfo;
  battle: { start: string; hours: number; end: string };
  pet_buff_times: Record<PetBuff, string>;
  state_generation: number;
  people: Record<string, Person>;
}

// ------------------------------------------------------------------ shared view (GET /api/svs/plan/<token>)

export type ViewHero = Pick<Hero, 'slug' | 'name' | 'image' | 'generation'> & { troop: HeroTroop | null; rarity?: string };
export interface ViewPerson {
  name: string;
  fid: string | null;
  alliance: string | null;
}
export interface ViewSide {
  heroes: (ViewHero | null)[];
  ratio: Ratio | null;
  other_joiner_heroes: (ViewHero | null)[];
}
export interface ViewJoinerSide {
  lead_hero: ViewHero | null;
  ratio: Ratio | null;
  ratio_overridden: boolean;
}
export interface ViewLeader {
  id: string;
  number: number;
  player: ViewPerson | null;
  alias: string | null;
  pfp_hero: ViewHero | null;
  split: boolean;
  pet_buff: PetBuff | null;
  pet_buff_time: string | null;
  rally: ViewSide;
  garrison: ViewSide | null;
  named_joiners: { player: ViewPerson; rally: ViewJoinerSide; garrison?: ViewJoinerSide }[];
  extra_joiners: ViewPerson[];
}
export interface ViewGroup {
  id: string;
  kind: GroupKind;
  name: string | null;
  alliance_tag: string | null;
  notes: string | null;
  min_requirements?: Record<TroopKey, MinReq>;
  leaders?: ViewLeader[];
  players?: ViewPerson[];
}
export interface PlanView {
  round_name: string;
  revision: number;
  updated_at: string | null;
  attribution: string;
  strategy: Strategy;
  show_real_names: boolean;
  battle: { start: string; hours: number; end: string };
  pet_buff_times: Record<PetBuff, string>;
  groups: ViewGroup[];
}

// ------------------------------------------------------------------ constructors

export function newId(prefix: string): string {
  const rnd = Math.random().toString(36).slice(2, 8);
  return `${prefix}${Date.now().toString(36)}${rnd}`;
}

const blankSide = (): JoinerSide => ({ lead_hero: null, ratio_override: null });
export const blankJoiner = (): NamedJoiner => ({ player: null, rally: blankSide(), garrison: blankSide() });
export const blankMarch = (): March => ({ heroes: [null, null, null], ratio: null });

export function blankMinReq(): Record<TroopKey, MinReq> {
  return { infantry: { min_camp: null, min_tier: null }, lancer: { min_camp: null, min_tier: null }, marksman: { min_camp: null, min_tier: null } };
}

export function blankGroup(kind: GroupKind, id?: string): PlanGroup {
  const g: PlanGroup = { id: id ?? newId('g'), kind, name: null, alliance_tag: null, notes: null };
  if (kind === 'extra') g.players = [];
  else g.min_requirements = blankMinReq();
  return g;
}

export function blankLeader(groupId: string, player: PlayerRef | null = null): Leader {
  return {
    id: newId('L'),
    group_id: groupId,
    order: 9999,
    player,
    disguise: { pfp_hero: null, alias: null },
    split: false,
    rally: blankMarch(),
    garrison: null,
    pet_buff: null,
    named_joiners: Array.from({ length: NAMED_JOINERS }, blankJoiner),
    other_joiner_heroes: { rally: [], garrison: [] },
    extra_joiners: [],
  };
}

/** Fill gaps a stored plan may have (older shapes, server normalisation), so the editor can rely on them. */
export function normalizeDoc(doc: PlanDoc): PlanDoc {
  const d = structuredClone(doc);
  d.show_real_names = d.show_real_names !== false;
  for (const g of d.groups) {
    if (g.kind === 'extra') g.players = g.players ?? [];
    else g.min_requirements = { ...blankMinReq(), ...(g.min_requirements ?? {}) };
  }
  for (const l of d.leaders) {
    l.disguise = l.disguise ?? { pfp_hero: null, alias: null };
    l.rally = l.rally ?? blankMarch();
    while (l.rally.heroes.length < 3) l.rally.heroes.push(null);
    if (l.garrison) while (l.garrison.heroes.length < 3) l.garrison.heroes.push(null);
    l.named_joiners = l.named_joiners ?? [];
    while (l.named_joiners.length < NAMED_JOINERS) l.named_joiners.push(blankJoiner());
    for (const j of l.named_joiners) {
      j.rally = j.rally ?? blankSide();
      j.garrison = j.garrison ?? blankSide();
    }
    l.other_joiner_heroes = { rally: l.other_joiner_heroes?.rally ?? [], garrison: l.other_joiner_heroes?.garrison ?? [] };
    l.extra_joiners = l.extra_joiners ?? [];
  }
  return renumber(d);
}

/** Leaders sorted by group order then `order`, with `order` renumbered 0.. per group (what the server stores). */
export function renumber(d: PlanDoc): PlanDoc {
  const rank: Record<GroupKind, number> = { main: 0, counter: 1, extra: 2 };
  d.groups.sort((a, b) => rank[a.kind] - rank[b.kind]);
  const gpos = new Map(d.groups.map((g, i) => [g.id, i]));
  d.leaders = d.leaders
    .map((l, i) => ({ l, i }))
    .sort((a, b) => (gpos.get(a.l.group_id) ?? 99) - (gpos.get(b.l.group_id) ?? 99) || a.l.order - b.l.order || a.i - b.i)
    .map(({ l }) => l);
  const count = new Map<string, number>();
  for (const l of d.leaders) {
    const n = count.get(l.group_id) ?? 0;
    l.order = n;
    count.set(l.group_id, n + 1);
  }
  return d;
}

export function leadersOf(d: PlanDoc, groupId: string): Leader[] {
  return d.leaders.filter((l) => l.group_id === groupId).sort((a, b) => a.order - b.order);
}

// ------------------------------------------------------------------ players

export function playerKey(ref: PlayerRef | null | undefined): string | null {
  if (!ref) return null;
  if (ref.fid) return `fid:${ref.fid}`;
  if (ref.name) return `name:${ref.name.trim().split(/\s+/).join(' ').toLowerCase()}`;
  return null;
}

/** Where a player is placed. */
export type Placement =
  | { kind: 'leader'; leaderId: string; groupId: string }
  | { kind: 'joiner'; leaderId: string; groupId: string; index: number }
  | { kind: 'extra'; leaderId: string; groupId: string; index: number }
  | { kind: 'extraGroup'; groupId: string; index: number };

/** Where a player can be put. */
export type PlayerTarget =
  | { kind: 'leader'; leaderId: string }
  | { kind: 'joiner'; leaderId: string; index: number }
  | { kind: 'extra'; leaderId: string }
  | { kind: 'extraGroup'; groupId: string }
  | { kind: 'newLeader'; groupId: string };

export function placements(d: PlanDoc): Map<string, Placement> {
  const out = new Map<string, Placement>();
  const add = (ref: PlayerRef | null, p: Placement) => {
    const k = playerKey(ref);
    if (k && !out.has(k)) out.set(k, p);
  };
  for (const l of d.leaders) {
    add(l.player, { kind: 'leader', leaderId: l.id, groupId: l.group_id });
    l.named_joiners.forEach((j, index) => add(j.player, { kind: 'joiner', leaderId: l.id, groupId: l.group_id, index }));
    l.extra_joiners.forEach((e, index) => add(e.player, { kind: 'extra', leaderId: l.id, groupId: l.group_id, index }));
  }
  for (const g of d.groups) (g.players ?? []).forEach((p, index) => add(p, { kind: 'extraGroup', groupId: g.id, index }));
  return out;
}

/** Remove a player from wherever they are (an explicit move). Leader cards stay (their player becomes empty). */
export function removePlacement(d: PlanDoc, p: Placement): void {
  if (p.kind === 'extraGroup') {
    d.groups.find((g) => g.id === p.groupId)?.players?.splice(p.index, 1);
    return;
  }
  const l = d.leaders.find((x) => x.id === p.leaderId);
  if (!l) return;
  if (p.kind === 'leader') l.player = null;
  else if (p.kind === 'joiner') l.named_joiners[p.index].player = null;
  else l.extra_joiners.splice(p.index, 1);
}

/** Put `ref` at `target` (mutates `d`). Returns false if the target is full. The caller handles double booking. */
export function applyPlayer(d: PlanDoc, target: PlayerTarget, ref: PlayerRef): boolean {
  if (target.kind === 'newLeader') {
    const l = blankLeader(target.groupId, ref);
    d.leaders.push(l);
    renumber(d);
    return true;
  }
  if (target.kind === 'extraGroup') {
    const g = d.groups.find((x) => x.id === target.groupId);
    if (!g) return false;
    g.players = [...(g.players ?? []), ref];
    return true;
  }
  const l = d.leaders.find((x) => x.id === target.leaderId);
  if (!l) return false;
  if (target.kind === 'leader') l.player = ref;
  else if (target.kind === 'joiner') l.named_joiners[target.index].player = ref;
  else {
    if (l.extra_joiners.length >= EXTRA_JOINERS) return false;
    l.extra_joiners.push({ player: ref });
  }
  return true;
}

// ------------------------------------------------------------------ hero slots

export type HeroSlot =
  | { kind: 'march'; leaderId: string; side: Side; index: number }
  | { kind: 'pfp'; leaderId: string }
  | { kind: 'joiner'; leaderId: string; side: Side; index: number }
  | { kind: 'other'; leaderId: string; side: Side; index: number };

export function slotId(s: HeroSlot): string {
  switch (s.kind) {
    case 'march':
    case 'joiner':
    case 'other':
      return `hs-${s.kind}-${s.leaderId}-${s.side}-${s.index}`;
    case 'pfp':
      return `hs-pfp-${s.leaderId}`;
  }
}

export function sameSlot(a: HeroSlot | null, b: HeroSlot | null): boolean {
  return !!a && !!b && slotId(a) === slotId(b);
}

export function getSlotHero(d: PlanDoc, s: HeroSlot): string | null {
  const l = d.leaders.find((x) => x.id === s.leaderId);
  if (!l) return null;
  switch (s.kind) {
    case 'pfp':
      return l.disguise.pfp_hero;
    case 'march':
      return (s.side === 'rally' ? l.rally : l.garrison)?.heroes[s.index] ?? null;
    case 'joiner':
      return l.named_joiners[s.index]?.[s.side].lead_hero ?? null;
    case 'other':
      return l.other_joiner_heroes[s.side][s.index] ?? null;
  }
}

/** Set (slug) or clear (null) a slot (mutates). A hero already in the same march is swapped out (no duplicates). */
export function setSlotHero(d: PlanDoc, s: HeroSlot, slug: string | null): void {
  const l = d.leaders.find((x) => x.id === s.leaderId);
  if (!l) return;
  switch (s.kind) {
    case 'pfp':
      l.disguise.pfp_hero = slug;
      return;
    case 'march': {
      if (s.side === 'garrison' && !l.garrison) l.garrison = blankMarch();
      const m = s.side === 'rally' ? l.rally : l.garrison!;
      if (slug) {
        const dup = m.heroes.indexOf(slug);
        if (dup >= 0 && dup !== s.index) m.heroes[dup] = m.heroes[s.index];
      }
      m.heroes[s.index] = slug;
      return;
    }
    case 'joiner':
      l.named_joiners[s.index][s.side].lead_hero = slug;
      return;
    case 'other': {
      const list = [...l.other_joiner_heroes[s.side]];
      if (slug === null) list.splice(s.index, 1);
      else if (s.index < list.length) list[s.index] = slug;
      else if (list.length < OTHER_HEROES) list.push(slug);
      l.other_joiner_heroes[s.side] = list;
      return;
    }
  }
}

/** The next empty slot after `s` in the same row (click-to-place keeps going: 3 rally heroes in 3 clicks). */
export function nextEmptySlot(d: PlanDoc, s: HeroSlot): HeroSlot | null {
  if (s.kind === 'march') {
    for (let i = s.index + 1; i < 3; i++) {
      const n = { ...s, index: i };
      if (!getSlotHero(d, n)) return n;
    }
  }
  if (s.kind === 'other') {
    const l = d.leaders.find((x) => x.id === s.leaderId);
    const len = l?.other_joiner_heroes[s.side].length ?? OTHER_HEROES;
    if (len < OTHER_HEROES) return { ...s, index: len };
  }
  return null;
}

export function ratioTotal(r: Partial<Record<RatioKey, number | string>>): number {
  return RATIO_KEYS.reduce((sum, k) => sum + (Number(r[k]) || 0), 0);
}

// ------------------------------------------------------------------ minimums

const fcNum = (code: string | null | undefined): number | null => {
  const m = /^FC(\d{1,2})$/.exec(code ?? '');
  return m ? Number(m[1]) : null;
};

export interface Shortfall {
  troop: TroopKey;
  what: 'camp' | 'tier';
  have: string;
  need: string;
}

/** Ways a joiner's troops fall below a group's minimums (unknown values count as below). */
export function shortfalls(
  troops: Record<TroopKey, { furnace_level: string | null; tier: number | null }> | null,
  mins: Record<TroopKey, MinReq> | undefined,
): Shortfall[] {
  if (!mins) return [];
  const out: Shortfall[] = [];
  for (const k of TROOPS) {
    const m = mins[k];
    if (!m) continue;
    const have = troops?.[k];
    if (m.min_camp) {
      const need = fcNum(m.min_camp)!;
      const got = fcNum(have?.furnace_level);
      if (got === null || got < need) out.push({ troop: k, what: 'camp', have: have?.furnace_level || '?', need: m.min_camp });
    }
    if (m.min_tier) {
      const got = have?.tier ?? null;
      if (got === null || got < m.min_tier) out.push({ troop: k, what: 'tier', have: got ? `T${got}` : '?', need: `T${m.min_tier}` });
    }
  }
  return out;
}

export function hasMinimums(mins: Record<TroopKey, MinReq> | undefined): boolean {
  return !!mins && TROOPS.some((k) => mins[k]?.min_camp || mins[k]?.min_tier);
}

/** "11:00" + N hours (UTC) -> "HH:MM". */
export function addHours(hhmm: string, n: number): string {
  const [h, m] = hhmm.split(':').map(Number);
  return `${String((((h + n) % 24) + 24) % 24).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}
