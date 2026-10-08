// Ministry routes. Everything ministry lives under /ministry; the pre-v2
// top-level URLs (/submit, /update, /schedule/:day, /guide, /apply) redirect
// here from App.tsx so bookmarks keep working. Admin stays at /admin.

export const MINISTRY_PATHS = {
  home: '/ministry',
  submit: '/ministry/submit',
  update: '/ministry/update',
  guide: '/ministry/guide',
  schedule: (day: string) => `/ministry/schedule/${day}`,
} as const;

