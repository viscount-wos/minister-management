// Frost Dragon Tyrant routes.
export const TYRANT_PATHS = {
  home: '/tyrant',
  apply: '/tyrant/apply',
  /** Event Management login; lands on the Tyrant dashboard (straight there when logged in). */
  admin: '/admin?event=tyrant',
} as const;
