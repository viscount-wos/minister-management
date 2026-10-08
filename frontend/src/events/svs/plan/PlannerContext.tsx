// Planner state shared by every part of the SVS battle planner (one context, no prop drilling).
import { createContext, useContext } from 'react';
import type { Hero } from '../../../shared/heroes/api';
import type { HeroSlot, Leader, PetBuff, Person, Placement, PlanDoc, PlanGroup, PlayerRef, PlayerTarget } from './model';
import type { TroopKey } from './model';

export interface SignupInfo {
  fid: string;
  name: string;
  alliance: string | null;
  /** Joiner strength (camp FC number + tier over the three troop types; 63 = FC10 T11 everywhere). No role: SVS
   * sign-up does not ask it (owner); leaders are picked by hand. */
  strength: number | null;
  hours: string[];
  vc: boolean | null;
  troops: Record<TroopKey, { furnace_level: string | null; tier: number | null }>;
}

export interface PlaceResult {
  ok: boolean;
  /** Set when the player is already elsewhere (ask for an explicit move). */
  already?: Placement;
}

export interface PlannerCtx {
  doc: PlanDoc;
  readOnly: boolean;
  update: (fn: (d: PlanDoc) => void) => void;
  /** Every hero in the library (incl. above the state's generation, to label plans saved before it was lowered). */
  heroes: Map<string, Hero>;
  stateGen: number;
  signups: Map<string, SignupInfo>;
  people: Record<string, Person>;
  placed: Map<string, Placement>;
  petTimes: Record<PetBuff, string>;
  battleHours: string[];
  armedSlot: HeroSlot | null;
  setArmedSlot: (s: HeroSlot | null) => void;
  armedHero: string | null;
  setArmedHero: (slug: string | null) => void;
  placeHero: (slot: HeroSlot, slug: string | null) => void;
  placePlayer: (target: PlayerTarget, ref: PlayerRef, move?: boolean) => PlaceResult;
  /** Quick add: with an FID the player gets an SVS sign-up (admin add-player); without, a plan-only name. */
  quickAdd: (name: string, fid: string) => Promise<PlayerRef>;
  playerName: (ref: PlayerRef | null | undefined) => string;
  placementLabel: (p: Placement) => string;
  leaderLabel: (l: Leader) => string;
  groupLabel: (g: PlanGroup) => string;
  moveLeader: (leaderId: string, groupId: string, beforeLeaderId?: string | null) => void;
  /** Sidebar tab to show (click-to-place switches to the heroes). */
  setSidebarTab: (tab: 'heroes' | 'players') => void;
  notify: (msg: string) => void;
}

export const PlannerContext = createContext<PlannerCtx | null>(null);

export function usePlanner(): PlannerCtx {
  const ctx = useContext(PlannerContext);
  if (!ctx) throw new Error('usePlanner outside the planner');
  return ctx;
}
