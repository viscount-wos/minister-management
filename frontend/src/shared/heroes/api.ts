// Hero library (GET /api/heroes): the foundation of the SVS planner. Hero names and art (c) Century Games.
import { apiRequest } from '../api';

export type HeroTroop = 'infantry' | 'lancer' | 'marksman';
export type HeroRarity = 'rare' | 'epic' | 'mythic';

export interface Hero {
  slug: string;
  name: string;
  troop: HeroTroop;
  /** 1..17; null for rare/epic heroes, which have no generation (always offered). */
  generation: number | null;
  has_generation: boolean;
  rarity: HeroRarity;
  /** Static path, e.g. /heroes/jeronimo.webp */
  image: string;
}

export interface HeroLibrary {
  version: number;
  state_generation: number;
  max_gen: number;
  max_generation: number;
  attribution: string;
  total: number;
  heroes: Hero[];
}

export const HERO_TROOPS: HeroTroop[] = ['infantry', 'lancer', 'marksman'];

/** max_gen: default = the state's hero generation (admin setting). */
export function fetchHeroes(query: { max_gen?: number; troop?: HeroTroop } = {}) {
  return apiRequest<HeroLibrary>('GET', '/api/heroes', {
    query: {
      max_gen: query.max_gen != null ? String(query.max_gen) : undefined,
      troop: query.troop,
    },
  });
}
