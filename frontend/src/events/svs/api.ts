// SVS API types and admin endpoints (docs/API.md "SVS"). Player calls use the generic endpoints with event 'svs'.

import api, { Round, apiRequest } from '../../shared/api';
import { toFcCode } from '../../shared/furnace';
import { TROOP_TYPES, TroopType, parseTroops } from '../tyrant/api';

export { TROOP_TYPES, parseTroops };
export type { TroopType };

export const EVENT = 'svs' as const;

// No role: SVS sign-up does not ask it (owner); the battle planner assigns rally leaders.
/** SVS tiers: T11 and T10 ONLY (owner: T8/T9 are never allowed in SVS). Highest first. */
export const SVS_TIERS = [11, 10] as const;

export interface SvsSettings {
  /** "HH:MM" UTC, default "11:00". */
  battle_start: string;
  /** 1-24, default 5. */
  battle_hours: number;
  /** Public round only: the derived hour starts, e.g. ["11:00", ..., "15:00"]. */
  hours?: string[];
}

/** The battle's hour starts in battle order (wraps past midnight): 11:00 + 5 -> 11:00 .. 15:00. */
export function battleHours(s: Pick<SvsSettings, 'battle_start' | 'battle_hours'> | null | undefined): string[] {
  const start = /^([01]\d|2[0-3]):([0-5]\d)$/.test(s?.battle_start ?? '') ? s!.battle_start : '11:00';
  const n = Math.min(24, Math.max(1, Number(s?.battle_hours) || 5));
  const [h, m] = start.split(':').map(Number);
  return Array.from({ length: n }, (_, i) => `${String((h + i) % 24).padStart(2, '0')}:${String(m).padStart(2, '0')}`);
}

/** "15:00" -> "16:00": end of an hour slot. */
export function hourEnd(hhmm: string): string {
  const [h, m] = hhmm.split(':').map(Number);
  return `${String((h + 1) % 24).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

export interface SvsTroop {
  furnace_level: string | null;
  tier: number | null;
}
export type SvsTroops = Record<TroopType, SvsTroop>;

/** Stored profile troops -> what the SVS form offers: FC camps only, tiers 10/11 only (a T8/T9 shows unselected). */
export function svsTroops(raw: unknown): SvsTroops {
  const tr = parseTroops(raw);
  const out = {} as SvsTroops;
  for (const k of TROOP_TYPES) {
    const tier = tr[k].tier;
    out[k] = {
      furnace_level: toFcCode(tr[k].furnace_level) || null,
      tier: tier != null && (SVS_TIERS as readonly number[]).includes(tier) ? tier : null,
    };
  }
  return out;
}

export interface SvsAnswers {
  hours: string[];
  discord_vc: boolean | null;
  language: string | null;
}

export interface SvsProfile {
  fid: string;
  game_name: string;
  alliance: string | null;
  troops: unknown;
}

export interface SvsApplication {
  fid: string;
  round_id: number;
  round_name?: string | null;
  answers: Partial<SvsAnswers>;
  updated_at?: string | null;
}

export interface SvsAdminApplication extends SvsApplication {
  id: number;
  player_id: number;
  created_at: string;
  updated_at: string;
  profile: SvsProfile;
  answers: SvsAnswers;
  joiner_strength?: number | null;
}

export interface SvsSummary {
  round_id: number;
  total: number;
  /** Battle hours per player (1 decimal). */
  avg_hours: number;
  /** Players with T11 in all three troop types. */
  all_t11: number;
  discord_vc: number;
  round_total: number;
  alliance_options: string[];
  hours: { hour: string; count: number }[];
  alliances: { alliance: string | null; count: number }[];
  troop_tiers: Record<TroopType, Record<string, number>>;
  camp_levels: Record<TroopType, Record<string, number>>;
}

export type SortKey = 'submitted' | 'updated' | 'name' | 'alliance' | 'fid' | 'strength' | 'hours';

/** Admin filters: the API's query params; the admin URL uses the same keys. */
export const FILTER_KEYS = [
  'q',
  'alliance',
  'hours',
  'vc',
  'troop',
  'min_camp',
  'min_tier',
  'infantry_camp',
  'infantry_tier',
  'lancer_camp',
  'lancer_tier',
  'marksman_camp',
  'marksman_tier',
  'submitted_from',
  'submitted_to',
  'days',
] as const;
export type FilterKey = (typeof FILTER_KEYS)[number];
export type FilterQuery = Partial<Record<FilterKey, string>>;

export interface ListQuery extends FilterQuery {
  sort?: SortKey;
  dir?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

const enc = encodeURIComponent;

function pickFilters(q: FilterQuery): Record<string, string | undefined> {
  const out: Record<string, string | undefined> = {};
  for (const k of FILTER_KEYS) if (q[k]) out[k] = q[k];
  return out;
}

export const svsApi = {
  currentRound: () => api.currentRound<SvsSettings>(EVENT),
  profile: (fid: string) => apiRequest<SvsProfile>('GET', `/api/profile/${enc(fid)}`),
  currentApplication: (fid: string) => apiRequest<SvsApplication>('GET', `/api/events/${EVENT}/current/application/${enc(fid)}`),
  previousApplication: (fid: string) => apiRequest<SvsApplication>('GET', `/api/events/${EVENT}/previous-application/${enc(fid)}`),
  putApplication: (
    fid: string,
    body: { profile: { game_name: string; alliance?: string; troops: SvsTroops }; answers: SvsAnswers },
  ) =>
    apiRequest<{ created: boolean; profile_created: boolean; application: SvsApplication; profile: SvsProfile }>(
      'PUT',
      `/api/events/${EVENT}/current/application/${enc(fid)}`,
      { body },
    ),

  admin: {
    updateRound: (id: number, body: { closing_time?: string | null; settings?: Partial<SvsSettings> }) =>
      apiRequest<Round<SvsSettings>>('PUT', `/api/admin/rounds/${id}`, { admin: true, body }),
    applications: (roundId: number, q: ListQuery) =>
      apiRequest<{ round_id: number; total: number; applications: SvsAdminApplication[] }>(
        'GET',
        `/api/admin/svs/rounds/${roundId}/applications`,
        {
          admin: true,
          query: {
            ...pickFilters(q),
            sort: q.sort,
            dir: q.dir,
            limit: q.limit != null ? String(q.limit) : undefined,
            offset: q.offset ? String(q.offset) : undefined,
          },
        },
      ),
    summary: (roundId: number, filters: FilterQuery = {}) =>
      apiRequest<SvsSummary>('GET', `/api/admin/svs/rounds/${roundId}/summary`, { admin: true, query: pickFilters(filters) }),
    exportXlsx: (roundId: number, filters: FilterQuery = {}) =>
      apiRequest<Blob>('GET', `/api/admin/svs/rounds/${roundId}/export`, { admin: true, blob: true, query: pickFilters(filters) }),
    exportCsv: (roundId: number, filters: FilterQuery = {}) =>
      apiRequest<Blob>('GET', `/api/admin/svs/rounds/${roundId}/export.csv`, { admin: true, blob: true, query: pickFilters(filters) }),
    deleteApplication: (id: number) => api.admin.deleteApplication(id),
  },
};
