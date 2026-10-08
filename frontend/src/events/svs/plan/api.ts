// SVS battle planner endpoints (docs/API.md "SVS battle planner").
import { apiRequest } from '../../../shared/api';
import type { PlanDoc, PlanResponse, PlanView, ShareInfo } from './model';

export const planApi = {
  get: (roundId: number) => apiRequest<PlanResponse>('GET', `/api/admin/svs/rounds/${roundId}/plan`, { admin: true }),
  /** 409 PLAN_CONFLICT (stale revision), 422 DOUBLE_BOOKED, 400 VALIDATION_ERROR, 409 ROUND_CLOSED. */
  save: (roundId: number, revision: number, plan: PlanDoc) =>
    apiRequest<PlanResponse>('PUT', `/api/admin/svs/rounds/${roundId}/plan`, { admin: true, body: { revision, plan } }),
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
