// Frost Dragon Tyrant routes.
export const TYRANT_PATHS = {
  home: '/tyrant',
  apply: '/tyrant/apply',
  /** Player guide (guide:tyrantPlayer.*). */
  guide: '/tyrant/guide',
  /** Event Management login; lands on the Tyrant dashboard (straight there when logged in). */
  admin: '/admin?event=tyrant',
} as const;
