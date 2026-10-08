// SVS routes.
export const SVS_PATHS = {
  home: '/svs',
  apply: '/svs/apply',
  /** Shared battle plan (secret token). */
  plan: (token: string) => `/svs/plan/${token}`,
  /** Event Management login; lands on the SVS dashboard (straight there when logged in). */
  admin: '/admin?event=svs',
} as const;
