// Minister routes (the event key stays 'ministry' in the API/DB; players see
// "Minister", the in-game term). Canonical URLs live under /minister. Older
// URLs redirect from App.tsx keeping the query string and hash: the v2
// /ministry/... routes, the pre-v2 top-level ones (/submit, /update,
// /schedule/:day, /guide, /apply) and /ministry/submit|update.
// Admin stays at /admin (?event=ministry).

export const MINISTRY_PATHS = {
  home: '/minister',
  /** The application wizard (v1.4 steps); step 1's FID decides new or edit for the current round. */
  apply: '/minister/apply',
  guide: '/minister/guide',
  schedule: (day: string) => `/minister/schedule/${day}`,
  /** Event Management login; lands on the minister dashboard. */
  admin: '/admin?event=ministry',
} as const;
