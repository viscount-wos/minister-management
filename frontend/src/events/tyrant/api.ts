// Frost Dragon Tyrant API types and admin endpoints (docs/API.md "Frost Dragon Tyrant").
// Player calls use the generic helpers in shared/api.ts with event 'tyrant'.

import api, { Round, apiRequest } from '../../shared/api';
import { isFurnaceCode } from '../../shared/furnace';

export const EVENT = 'tyrant' as const;

export const ROLES = ['rally_leader', 'joiner', 'gathering', 'battle_mgmt', 'event_prep'] as const;
export type Role = (typeof ROLES)[number];
export const TROOP_TYPES = ['infantry', 'lancer', 'marksman'] as const;
export type TroopType = (typeof TROOP_TYPES)[number];

/** Troop tiers offered (tyrantpoll: T8-T11). Furnace levels: shared/furnace.ts. */
export const TIERS = [8, 9, 10, 11];

export interface TyrantWindow {
  id: string;
  start: string;
  end: string;
  rush: boolean;
}

export interface TyrantSettings {
  windows: TyrantWindow[];
}

export interface TroopLevel {
  /** Furnace code 'FC1'..'FC10' / '1'..'30' or null. */
  furnace_level: string | null;
  tier: number | null;
}
export type Troops = Record<TroopType, TroopLevel>;

export interface TyrantAnswers {
  availability: string[];
  discord_vc: boolean;
  gem_spend: number | null;
  roles: Role[];
  language: string | null;
}

/** Public profile as the API returns it (tolerant: older rows may lack fields). */
export interface TyrantProfile {
  fid: string;
  game_name: string;
  alliance: string | null;
  discord_id?: string | null;
  furnace_level: string | null;
  power: number | null;
  troops: unknown;
  id?: number;
}

export interface TyrantProfileInput {
  game_name: string;
  alliance: string;
  discord_id: string | null;
  furnace_level: string | null;
  power: number | null;
  troops: Troops;
}

export interface TyrantApplication {
  fid: string;
  round_id: number;
  round_name?: string | null;
  answers: Partial<TyrantAnswers>;
  updated_at?: string | null;
}

export interface TyrantAdminApplication extends TyrantApplication {
  id: number;
  player_id: number;
  created_at: string;
  updated_at: string;
  profile: TyrantProfile;
  answers: TyrantAnswers;
}

export interface TyrantSummary {
  round_id: number;
  total: number;
  opening_rush: number;
  discord_vc: number;
  gem_spend_total: number;
  windows: (TyrantWindow & { count: number })[];
  alliances: { alliance: string | null; count: number }[];
  roles: Record<Role, number>;
  troop_tiers: Record<TroopType, Record<string, number>>;
  furnace_levels: Record<string, number>;
}

export type SortKey = 'submitted' | 'updated' | 'name' | 'alliance' | 'fid' | 'furnace' | 'power' | 'gems';

export interface ListQuery {
  q?: string;
  alliance?: string;
  sort?: SortKey;
  dir?: 'asc' | 'desc';
  /** Only players at this furnace level or higher (code). */
  min_furnace?: string;
  limit?: number;
  offset?: number;
}

/** Parses whatever is stored in profile.troops into the canonical shape (defensive: other events may write it). */
export function parseTroops(raw: unknown): Troops {
  const out = {} as Troops;
  const src = raw && typeof raw === 'object' && !Array.isArray(raw) ? (raw as Record<string, unknown>) : {};
  for (const k of TROOP_TYPES) {
    const e = src[k] && typeof src[k] === 'object' ? (src[k] as Record<string, unknown>) : {};
    const num = (v: unknown) => (typeof v === 'number' && Number.isInteger(v) ? v : null);
    out[k] = { furnace_level: isFurnaceCode(e.furnace_level) ? e.furnace_level : null, tier: num(e.tier) };
  }
  return out;
}

const enc = encodeURIComponent;

export const tyrantApi = {
  currentRound: () => api.currentRound<TyrantSettings>(EVENT),
  profile: (fid: string) => apiRequest<TyrantProfile>('GET', `/api/profile/${enc(fid)}`),
  currentApplication: (fid: string) => apiRequest<TyrantApplication>('GET', `/api/events/${EVENT}/current/application/${enc(fid)}`),
  previousApplication: (fid: string) =>
    apiRequest<TyrantApplication>('GET', `/api/events/${EVENT}/previous-application/${enc(fid)}`),
  putApplication: (fid: string, body: { profile: TyrantProfileInput; answers: TyrantAnswers }) =>
    apiRequest<{ created: boolean; profile_created: boolean; application: TyrantApplication; profile: TyrantProfile }>(
      'PUT',
      `/api/events/${EVENT}/current/application/${enc(fid)}`,
      { body },
    ),

  admin: {
    rounds: () => apiRequest<{ rounds: Round<TyrantSettings>[] }>('GET', `/api/admin/events/${EVENT}/rounds`, { admin: true }),
    updateRound: (id: number, body: { name?: string; closing_time?: string | null; settings?: Partial<TyrantSettings> }) =>
      apiRequest<Round<TyrantSettings>>('PUT', `/api/admin/rounds/${id}`, { admin: true, body }),
    applications: (roundId: number, q: ListQuery) =>
      apiRequest<{ round_id: number; total: number; applications: TyrantAdminApplication[] }>(
        'GET',
        `/api/admin/tyrant/rounds/${roundId}/applications`,
        {
          admin: true,
          query: {
            q: q.q,
            alliance: q.alliance,
            sort: q.sort,
            dir: q.dir,
            min_furnace: q.min_furnace,
            limit: q.limit != null ? String(q.limit) : undefined,
            offset: q.offset ? String(q.offset) : undefined,
          },
        },
      ),
    summary: (roundId: number, alliance?: string) =>
      apiRequest<TyrantSummary>('GET', `/api/admin/tyrant/rounds/${roundId}/summary`, { admin: true, query: { alliance } }),
    exportXlsx: (roundId: number) =>
      apiRequest<Blob>('GET', `/api/admin/tyrant/rounds/${roundId}/export`, { admin: true, blob: true }),
    exportCsv: (roundId: number) =>
      apiRequest<Blob>('GET', `/api/admin/tyrant/rounds/${roundId}/export.csv`, { admin: true, blob: true }),
    deleteApplication: (id: number) => api.admin.deleteApplication(id),
  },
};
