// The ONE typed client for the wos-events HTTP API (docs/API.md). Every page
// talks to the backend through here; nothing else should call fetch('/api/...').
//
// - Success bodies are JSON objects; errors are always {error, code, field}.
//   Failures throw ApiError carrying the HTTP status, machine code and field.
// - 409 CONFLICT (two writes collided) is retried once automatically.
// - Admin calls send the signed token. Any 401 on an admin call clears the
//   stored token and fires the unauthorized handler (the admin pages send the
//   user back to the login page).

import type { TimeSlotScheme } from './timezone';

// ------------------------------------------------------------------ types

export type EventKey = 'ministry' | 'tyrant' | 'svs' | 'tal';
export type RoundStatus = 'draft' | 'open' | 'closed';
export type DayType = 'construction' | 'research' | 'troop';
export type ResearchDay = 'tuesday' | 'friday';
export type MinistryDay = 'monday' | 'tuesday' | 'thursday' | 'friday';

export type ErrorCode =
  | 'VALIDATION_ERROR'
  | 'INVALID_JSON'
  | 'EVENT_HAS_NO_ROUNDS'
  | 'EXPORT_NOT_SUPPORTED'
  | 'UNAUTHORIZED'
  | 'INVALID_TOKEN'
  | 'TOKEN_EXPIRED'
  | 'INVALID_PASSWORD'
  | 'APPLICATIONS_CLOSED'
  | 'NOT_FOUND'
  | 'UNKNOWN_EVENT'
  | 'NO_CURRENT_ROUND'
  | 'METHOD_NOT_ALLOWED'
  | 'ROUND_ALREADY_OPEN'
  | 'ROUND_CLOSED'
  | 'TOO_MANY_ATTEMPTS'
  | 'RETRY'
  | 'CONFLICT'
  | 'INTERNAL_ERROR'
  | 'NETWORK_ERROR'
  | string;

/** Public profiles have no id/created_at/updated_at; admin profile endpoints add them. */
export interface Profile {
  id?: number;
  fid: string;
  game_name: string;
  alliance: string | null;
  timezone: string | null;
  furnace_level: number | null;
  power: number | null;
  troops: unknown;
  avatar_image: string | null;
  stove_lv: number | null;
  stove_lv_content: string | null;
  created_at?: string;
  updated_at?: string;
}

/** Writable profile fields (partial on update). */
export interface ProfileInput {
  game_name?: string;
  alliance?: string;
  timezone?: string;
  furnace_level?: number | null;
  power?: number | null;
  troops?: unknown;
}

export interface MinistrySettings {
  research_day: ResearchDay;
  show_fire_crystals: boolean;
  time_slot_scheme: TimeSlotScheme;
  published_days: string[];
}

export interface Round<S = MinistrySettings> {
  id: number;
  event: EventKey;
  name: string;
  status: RoundStatus;
  closing_time: string | null;
  is_closed_for_new: boolean;
  settings: S;
  created_at: string;
  updated_at: string;
  /** Admin round list only. */
  application_count?: number;
  /** PUT round only, when the slot scheme changed. */
  remapped?: number;
}

export interface RoundSummary {
  id: number;
  name: string;
  status: RoundStatus;
  closing_time: string | null;
  is_closed_for_new: boolean;
}

export interface EventInfo {
  key: EventKey;
  has_rounds: boolean;
  current_round: RoundSummary | null;
}

export interface TimeSlotsByDay {
  construction: string[];
  research: string[];
  troop: string[];
}

export interface MinistryAnswers {
  construction_speedups_days: number;
  research_speedups_days: number;
  troop_training_speedups_days: number;
  general_speedups_days: number;
  fire_crystals: number;
  refined_fire_crystals: number;
  fire_crystal_shards: number;
  time_slots_by_day: TimeSlotsByDay;
}

/** Public application: {fid, event, round_id, round_name, answers, updated_at} (no internal ids). */
export interface Application<A = MinistryAnswers> {
  fid: string;
  round_id: number;
  answers: A;
  updated_at?: string | null;
  event?: EventKey;
  round_name?: string | null;
}

/** Admin application list entry: the full shape (ids, snapshot, timestamps) + ministry points. */
export interface AdminApplication extends Application {
  id: number;
  player_id: number;
  profile_snapshot: Partial<Profile>;
  created_at: string;
  updated_at: string;
  profile: Profile;
  monday_points: number;
  research_points: number;
  thursday_points: number;
  research_day: ResearchDay;
}

export interface PutApplicationResult<A = MinistryAnswers> {
  created: boolean;
  profile_created: boolean;
  application: Application<A>;
  profile: Profile;
}

export type Heatmap = Partial<Record<DayType, Record<string, number>>>;

export interface PublishedScheduleDay {
  published: boolean;
  day: string;
  round_id: number;
  day_label?: string;
  assignments?: Record<string, { game_name: string; alliance: string }[]>;
}

export interface PlayerAssignments {
  round_id: number;
  published_days: string[];
  assignments: Record<string, { time_slot: string }[]>;
}

export interface AssignmentCard {
  id: number;
  player_id: number;
  fid: string;
  game_name: string;
  points: number;
  preferred_times: string[];
  avatar_image: string;
  stove_lv: number | null;
  stove_lv_content: string;
  alliance: string;
  is_sticky: boolean;
  assignment_id?: number;
  position?: number;
  is_assigned?: boolean;
}

export interface DayAssignments {
  day: string;
  round_id: number;
  assignments: Record<string, AssignmentCard[]>;
  unassigned: AssignmentCard[];
}

export interface ImportResult {
  round_id: number;
  imported: number;
  updated: number;
  errors: number;
  error_details: { index: number; fid: string; error: string; field: string | null }[];
}

// ------------------------------------------------------------------ errors

export class ApiError extends Error {
  readonly status: number;
  readonly code: ErrorCode;
  readonly field: string | null;
  readonly details: unknown;

  constructor(status: number, code: ErrorCode, message: string, field: string | null = null, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.field = field;
    this.details = details;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isAuthError(): boolean {
    return this.status === 401;
  }
}

export function isApiError(err: unknown, code?: ErrorCode): err is ApiError {
  return err instanceof ApiError && (code === undefined || err.code === code);
}

// ------------------------------------------------------------------ admin token

const TOKEN_KEY = 'adminToken';
const ROLE_KEY = 'adminRole';

export const adminSession = {
  token: (): string | null => localStorage.getItem(TOKEN_KEY),
  role: (): string | null => localStorage.getItem(ROLE_KEY),
  save(token: string, role: string) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(ROLE_KEY, role);
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(ROLE_KEY);
  },
};

type UnauthorizedHandler = (err: ApiError) => void;
let unauthorizedHandler: UnauthorizedHandler | null = null;

/**
 * Called (after the token is cleared) when an admin call gets a 401: missing,
 * forged or expired token. Returns an unsubscribe function.
 */
export function onUnauthorized(handler: UnauthorizedHandler): () => void {
  unauthorizedHandler = handler;
  return () => {
    if (unauthorizedHandler === handler) unauthorizedHandler = null;
  };
}

// ------------------------------------------------------------------ core request

interface RequestOptions {
  body?: unknown;
  admin?: boolean;
  /** Return the response as a Blob (file downloads). */
  blob?: boolean;
  query?: Record<string, string | undefined>;
}

const enc = encodeURIComponent;

async function parseError(res: Response): Promise<ApiError> {
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    // not JSON (proxy error page etc.)
  }
  const code = (data && typeof data.code === 'string' && data.code) || `HTTP_${res.status}`;
  const message = (data && typeof data.error === 'string' && data.error) || res.statusText || 'Request failed';
  return new ApiError(res.status, code, message, data?.field ?? null, data?.details);
}

async function send(method: string, path: string, opts: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
  if (opts.admin) {
    const token = adminSession.token();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  let url = path;
  if (opts.query) {
    const qs = Object.entries(opts.query)
      .filter(([, v]) => v !== undefined && v !== '')
      .map(([k, v]) => `${enc(k)}=${enc(v as string)}`)
      .join('&');
    if (qs) url += `?${qs}`;
  }
  try {
    return await fetch(url, {
      method,
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch (e) {
    throw new ApiError(0, 'NETWORK_ERROR', e instanceof Error ? e.message : 'Network error');
  }
}

async function request<T>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
  let res = await send(method, path, opts);
  if (res.status === 409) {
    const err = await parseError(res.clone());
    if (err.code === 'CONFLICT') {
      // A concurrent write collided (e.g. two first submissions); one retry is enough.
      res = await send(method, path, opts);
    }
  }
  if (!res.ok) {
    const err = await parseError(res);
    if (opts.admin && err.status === 401) {
      adminSession.clear();
      unauthorizedHandler?.(err);
    }
    throw err;
  }
  if (opts.blob) return (await res.blob()) as T;
  return (await res.json()) as T;
}

/** Resolves to null instead of throwing on 404 (any 404 code). */
async function orNull<T>(p: Promise<T>): Promise<T | null> {
  try {
    return await p;
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

/** Saves a Blob as a download with the given filename. */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ------------------------------------------------------------------ endpoints

export const api = {
  orNull,

  // ---- public
  health: () => request<{ status: string }>('GET', '/health'),
  events: () => request<{ events: EventInfo[] }>('GET', '/api/events'),
  publicSettings: () => request<{ state_number: string }>('GET', '/api/settings/public'),

  profile: (fid: string) => request<Profile>('GET', `/api/profile/${enc(fid)}`),

  /** 404 NO_CURRENT_ROUND when the event has no open round. */
  currentRound: <S = MinistrySettings>(event: EventKey) =>
    request<Round<S>>('GET', `/api/events/${event}/current`),
  /** 404 NOT_FOUND = no application yet in the current round ("New application"). */
  currentApplication: <A = MinistryAnswers>(event: EventKey, fid: string) =>
    request<Application<A>>('GET', `/api/events/${event}/current/application/${enc(fid)}`),
  /** The player's application from the most recent EARLIER round; 404 if none. */
  previousApplication: <A = MinistryAnswers>(event: EventKey, fid: string) =>
    request<Application<A>>('GET', `/api/events/${event}/previous-application/${enc(fid)}`),
  /** Upserts profile + application. 403 APPLICATIONS_CLOSED for a NEW one after closing time. */
  putApplication: <A = MinistryAnswers>(event: EventKey, fid: string, body: { profile: ProfileInput; answers: A }) =>
    request<PutApplicationResult<A>>('PUT', `/api/events/${event}/current/application/${enc(fid)}`, { body }),

  ministry: {
    heatmap: () => request<Heatmap>('GET', '/api/events/ministry/current/heatmap'),
    publishedDays: () => request<{ round_id: number; published_days: string[] }>('GET', '/api/events/ministry/current/schedule'),
    scheduleDay: (day: string) => request<PublishedScheduleDay>('GET', `/api/events/ministry/current/schedule/${enc(day)}`),
    playerAssignments: (fid: string) =>
      request<PlayerAssignments>('GET', `/api/events/ministry/current/assignments/${enc(fid)}`),
  },

  // ---- admin
  admin: {
    login: (password: string) =>
      request<{ token: string; role: string; expires_in: number }>('POST', '/api/admin/login', { body: { password } }),
    me: () => request<{ role: string }>('GET', '/api/admin/me', { admin: true }),

    settings: () => request<{ state_number: string }>('GET', '/api/admin/settings', { admin: true }),
    updateSettings: (body: { state_number: string }) =>
      request<{ state_number: string }>('PUT', '/api/admin/settings', { admin: true, body }),

    rounds: (event: EventKey) => request<{ rounds: Round[] }>('GET', `/api/admin/events/${event}/rounds`, { admin: true }),
    round: (id: number) => request<Round>('GET', `/api/admin/rounds/${id}`, { admin: true }),
    createRound: (event: EventKey, body: { name: string; status?: RoundStatus; closing_time?: string | null; settings?: Partial<MinistrySettings> }) =>
      request<Round>('POST', `/api/admin/events/${event}/rounds`, { admin: true, body }),
    updateRound: (id: number, body: { name?: string; status?: RoundStatus; closing_time?: string | null; settings?: Partial<MinistrySettings> }) =>
      request<Round>('PUT', `/api/admin/rounds/${id}`, { admin: true, body }),
    startNewRound: (event: EventKey, body: { name: string; closing_time?: string | null; settings?: Partial<MinistrySettings> }) =>
      request<{ round: Round; closed_round: Round | null }>('POST', `/api/admin/events/${event}/start-new-round`, { admin: true, body }),

    applications: (roundId: number, alliance?: string) =>
      request<{ round_id: number; applications: AdminApplication[] }>('GET', `/api/admin/rounds/${roundId}/applications`, {
        admin: true,
        query: { alliance },
      }),
    application: (id: number) => request<AdminApplication>('GET', `/api/admin/applications/${id}`, { admin: true }),
    updateApplication: (id: number, body: { profile?: ProfileInput; answers?: Partial<MinistryAnswers> }) =>
      request<AdminApplication>('PUT', `/api/admin/applications/${id}`, { admin: true, body }),
    deleteApplication: (id: number) =>
      request<{ deleted: boolean; id: number }>('DELETE', `/api/admin/applications/${id}`, { admin: true }),
    exportRound: (roundId: number) => request<Blob>('GET', `/api/admin/rounds/${roundId}/export`, { admin: true, blob: true }),

    profiles: (query: { alliance?: string; q?: string } = {}) =>
      request<{ profiles: (Profile & { application_count: number })[] }>('GET', '/api/admin/profiles', { admin: true, query }),
    profile: (fid: string) => request<Profile>('GET', `/api/admin/profiles/${enc(fid)}`, { admin: true }),
    updateProfile: (fid: string, body: ProfileInput) =>
      request<{ profile: Profile; created: boolean }>('PUT', `/api/admin/profiles/${enc(fid)}`, { admin: true, body }),
    deleteProfile: (fid: string) =>
      request<{ deleted: boolean; fid: string; applications_deleted: number }>('DELETE', `/api/admin/profiles/${enc(fid)}`, { admin: true }),

    ministry: {
      autoAssign: (ref: number | 'current', day: string) =>
        request<DayAssignments>('POST', `/api/admin/ministry/rounds/${ref}/auto-assign`, { admin: true, body: { day } }),
      assignments: (ref: number | 'current', day: string) =>
        request<DayAssignments>('GET', `/api/admin/ministry/rounds/${ref}/assignments/${enc(day)}`, { admin: true }),
      saveAssignments: (ref: number | 'current', day: string, assignments: Record<string, { player_id: number; is_sticky: boolean }[]>) =>
        request<{ day: string; round_id: number; saved: number }>('PUT', `/api/admin/ministry/rounds/${ref}/assignments/${enc(day)}`, {
          admin: true,
          body: { assignments },
        }),
      publish: (ref: number | 'current', day: string) =>
        request<{ round_id: number; published_days: string[] }>('POST', `/api/admin/ministry/rounds/${ref}/publish`, { admin: true, body: { day } }),
      unpublish: (ref: number | 'current', day: string) =>
        request<{ round_id: number; published_days: string[] }>('POST', `/api/admin/ministry/rounds/${ref}/unpublish`, { admin: true, body: { day } }),
      exportExcel: (ref: number | 'current') =>
        request<Blob>('GET', `/api/admin/ministry/rounds/${ref}/export`, { admin: true, blob: true }),
      exportJson: (ref: number | 'current') =>
        request<Blob>('GET', `/api/admin/ministry/rounds/${ref}/export-json`, { admin: true, blob: true }),
      importJson: (ref: number | 'current', data: unknown) =>
        request<ImportResult>('POST', `/api/admin/ministry/rounds/${ref}/import`, { admin: true, body: data }),
    },
  },
};

export default api;
