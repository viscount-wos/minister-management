// Admin URLs. One login, one dashboard, one guide; the event is a query
// parameter so a reload (or a bookmark) stays on the same event:
//   /admin?event=tyrant             login, then the Tyrant dashboard
//   /admin/dashboard?event=tyrant   the dashboard of one event
//   /admin/guide?event=tyrant       that event's admin guide
//   /admin/guide?event=tyrant&topic=basics   Event Management basics (shared by every event)
// Without ?event= the last event administered on this device is used
// (localStorage), else the first registered event (ministry).
// Kept free of imports so public pages can link here without pulling in the
// admin screens.

const withEvent = (path: string, event?: string | null, extra = '') =>
  event ? `${path}?event=${encodeURIComponent(event)}${extra ? `&${extra}` : ''}` : extra ? `${path}?${extra}` : path;

export const ADMIN_PATHS = {
  login: (event?: string | null, expired = false) => withEvent('/admin', event, expired ? 'expired=1' : ''),
  dashboard: (event: string) => withEvent('/admin/dashboard', event),
  guide: (event: string) => withEvent('/admin/guide', event),
  /** The shared "Event Management basics" guide (rounds, closing times, Add player, links...). */
  basics: (event: string) => withEvent('/admin/guide', event, 'topic=basics'),
} as const;

const LAST_EVENT_KEY = 'adminLastEvent';

export const lastAdminEvent = {
  get: (): string | null => {
    try {
      return localStorage.getItem(LAST_EVENT_KEY);
    } catch {
      return null;
    }
  },
  set: (event: string) => {
    try {
      localStorage.setItem(LAST_EVENT_KEY, event);
    } catch {
      /* private mode: just don't remember */
    }
  },
};
