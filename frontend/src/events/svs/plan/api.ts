// SVS battle planner endpoints (docs/API.md "SVS battle planner").
import { apiRequest } from '../../../shared/api';
import type { PlanDoc, PlanResponse, PlanView, ShareInfo } from './model';

export type PlaceMode = 'auto' | 'named' | 'extra' | 'leader' | 'group';
export interface PlaceBody {
  fid?: string;
  fids?: string[];
  as: PlaceMode;
  leader_id?: string;
  group_id?: string;
  slot?: number;
  move?: boolean;
  expected_revision?: number;
}
export interface PlaceWhere {
  group_id: string;
  group_name: string | null;
  group_kind: 'main' | 'counter' | 'extra';
  leader_id: string | null;
  leader_label: string | null;
  position: 'leader' | 'named_joiner' | 'extra_joiner' | 'extra_group';
  slot: number | null;
}
export interface PlacedRecord {
  player: { fid?: string; name?: string };
  as: 'named' | 'extra' | 'leader' | 'group';
  group_id: string;
  leader_id: string | null;
  slot: number | null;
  from?: PlaceWhere;
}
export interface PlaceResult {
  placed: PlacedRecord[];
  moved: PlacedRecord[];
  unchanged: { player: { fid?: string }; where: PlaceWhere }[];
  skipped: { player: { fid?: string }; reason: string; where: PlaceWhere }[];
  overflow: { player: { fid?: string } }[];
  not_found: { player: { fid?: string } }[];
}
export type PlaceResponse = PlanResponse & { changed: boolean; result: PlaceResult };

export const planApi = {
  get: (roundId: number) => apiRequest<PlanResponse>('GET', `/api/admin/svs/rounds/${roundId}/plan`, { admin: true }),
  /** 409 PLAN_CONFLICT (stale revision), 422 DOUBLE_BOOKED, 400 VALIDATION_ERROR, 409 ROUND_CLOSED. */
  save: (roundId: number, revision: number, plan: PlanDoc) =>
    apiRequest<PlanResponse>('PUT', `/api/admin/svs/rounds/${roundId}/plan`, { admin: true, body: { revision, plan } }),
  /** "Add to rally": one atomic change on the server (docs/API.md). 409 PLAN_CONFLICT (stale expected_revision),
   * 422 DOUBLE_BOOKED / RALLY_FULL / GROUP_FULL / SLOT_TAKEN, 404 LEADER_NOT_FOUND / GROUP_NOT_FOUND. */
  place: (roundId: number, body: PlaceBody) =>
    apiRequest<PlaceResponse>('POST', `/api/admin/svs/rounds/${roundId}/plan/place`, { admin: true, body }),
  share: (roundId: number, action: 'create' | 'rotate' | 'disable') =>
    apiRequest<{ round_id: number; share: ShareInfo }>('POST', `/api/admin/svs/rounds/${roundId}/plan/share`, {
      admin: true,
      body: { action },
    }),
  /** Public, read-only; 404 PLAN_NOT_FOUND for a wrong / replaced / turned-off link. */
  shared: (token: string) => apiRequest<PlanView>('GET', `/api/svs/plan/${encodeURIComponent(token)}`),
};

/** The full shareable URL for a share path. */
export function shareUrl(path: string): string {
  return `${window.location.origin}${path}`;
}
