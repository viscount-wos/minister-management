import type { AdminEventModule } from './types';
import { lastAdminEvent } from './paths';
import ministryAdmin from '../events/ministry/admin/adminModule';
import tyrantAdmin from '../events/tyrant/admin/adminModule';

// Events that have an admin, in switch order. To add one (e.g. SVS once it
// has rounds): write events/<key>/admin/adminModule.tsx (label, subtitle,
// icon, public page, tabs, guide) and list it here. The shell, the event
// switch, login landing, guide page and page titles pick it up.
// Tundra Arms League joins when it has rounds; SVS when its module is built.
export const ADMIN_EVENTS: readonly AdminEventModule[] = [ministryAdmin, tyrantAdmin];

export const DEFAULT_ADMIN_EVENT = ADMIN_EVENTS[0].key;

export function findAdminEvent(key: string | null | undefined): AdminEventModule | undefined {
  return ADMIN_EVENTS.find((e) => e.key === key);
}

/** The event to administer: the URL's ?event= if known, else the last one used here, else ministry. */
export function resolveAdminEvent(param: string | null | undefined): AdminEventModule {
  return findAdminEvent(param) ?? findAdminEvent(lastAdminEvent.get()) ?? ADMIN_EVENTS[0];
}
