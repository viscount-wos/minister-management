// How the planner names groups, leaders and placements. Shared by the Battle plan (the "Already with …" badge) and the
// Players tab (Plan column, Add to rally), so both always say the same thing.
import type { TFunction } from 'i18next';
import { EXTRA_JOINERS, NAMED_JOINERS, leadersOf } from './model';
import type { Leader, Person, Placement, PlanDoc, PlanGroup, PlayerRef } from './model';

export type PlayerNameFn = (ref: PlayerRef | null | undefined) => string;

/** A player's display name from the plan's `people` (+ optional extra names, e.g. the planner's sign-ups). */
export function makePlayerName(people: Record<string, Person>, extra?: (fid: string) => string | undefined): PlayerNameFn {
  return (ref) => {
    if (!ref) return '';
    if (ref.fid) return extra?.(ref.fid) ?? people[ref.fid]?.game_name ?? ref.name ?? `FID ${ref.fid}`;
    return ref.name ?? '';
  };
}

export function groupLabel(t: TFunction, g: PlanGroup): string {
  return g.name || t(`svs:plan.defaultName.${g.kind}`);
}

/** Alias, else the leader's name, else "Rally leader N". */
export function leaderLabel(t: TFunction, d: PlanDoc, l: Leader, playerName: PlayerNameFn): string {
  if (l.disguise.alias) return l.disguise.alias;
  if (l.player) return playerName(l.player);
  const n = leadersOf(d, l.group_id).findIndex((x) => x.id === l.id) + 1;
  return t('svs:plan.leaderN', { n });
}

/** The planner's badge: "Leads a rally in Main alliance" / "Already with Rally Caller 01" / "Already in Turrets". */
export function placementLabel(t: TFunction, d: PlanDoc, p: Placement, playerName: PlayerNameFn): string {
  const g = d.groups.find((x) => x.id === p.groupId);
  const gl = g ? groupLabel(t, g) : '';
  if (p.kind === 'extraGroup') return t('svs:plan.placed.inGroup', { group: gl });
  const l = d.leaders.find((x) => x.id === p.leaderId);
  if (p.kind === 'leader') return t('svs:plan.placed.leads', { group: gl });
  return t('svs:plan.placed.with', { leader: l ? leaderLabel(t, d, l, playerName) : '?' });
}

/** The Players tab's Plan column: "Leader · Rally Caller 01 (Main)", "Joiner 2 · Rally Caller 01 (Main)",
 * "Extra · FrostHeart (Counter)", "Turrets". */
export function placementShort(t: TFunction, d: PlanDoc, p: Placement, playerName: PlayerNameFn): string {
  const g = d.groups.find((x) => x.id === p.groupId);
  const group = g ? groupLabel(t, g) : '';
  if (p.kind === 'extraGroup') return t('svs:players.place.group', { group });
  const l = d.leaders.find((x) => x.id === p.leaderId);
  const leader = l ? leaderLabel(t, d, l, playerName) : '?';
  if (p.kind === 'leader') return t('svs:players.place.leader', { leader, group });
  if (p.kind === 'joiner') return t('svs:players.place.joiner', { leader, group, n: p.index + 1 });
  return t('svs:players.place.extra', { leader, group });
}

export interface Capacity {
  named: number;
  extra: number;
  namedFree: number;
  extraFree: number;
}

export function capacity(l: Leader): Capacity {
  const named = l.named_joiners.filter((j) => j.player).length;
  const extra = l.extra_joiners.length;
  return { named, extra, namedFree: NAMED_JOINERS - named, extraFree: EXTRA_JOINERS - extra };
}
