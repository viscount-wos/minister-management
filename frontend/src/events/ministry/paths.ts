// Ministry routes. Everything ministry lives under /ministry; the pre-v2
// top-level URLs (/submit, /update, /schedule/:day, /guide, /apply) and the
// v2-shell /ministry/submit and /ministry/update redirect from App.tsx so
// bookmarks keep working. Admin stays at /admin.

export const MINISTRY_PATHS = {
  home: '/ministry',
  /** The application wizard (v1.4 steps); step 1's FID decides new or edit for the current round. */
  apply: '/ministry/apply',
  guide: '/ministry/guide',
  schedule: (day: string) => `/ministry/schedule/${day}`,
} as const;
