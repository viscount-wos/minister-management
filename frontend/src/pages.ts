import { lazy, type ComponentType } from 'react';

// Every page except the home page and the layout is its own chunk, so a player
// only downloads the screens they open (the admin area, its drag-and-drop board
// and the guides never reach a player's phone unless they go there).
//
// preloadForPath() starts the current URL's chunk at startup, in parallel with
// the language chunk, instead of after the first render.

type Loader = () => Promise<{ default: ComponentType<any> }>;

const RELOAD_FLAG = 'chunk_reload_at';

/** A chunk that fails to load (usually an old file name after a new deploy) reloads the page once. */
function withReload(load: Loader): Loader {
  return () =>
    load().catch((err) => {
      let last = 0;
      try {
        last = Number(sessionStorage.getItem(RELOAD_FLAG) || 0);
      } catch {
        // storage blocked
      }
      if (Date.now() - last > 60_000) {
        try {
          sessionStorage.setItem(RELOAD_FLAG, String(Date.now()));
        } catch {
          // storage blocked
        }
        window.location.reload();
        return new Promise<never>(() => {});
      }
      throw err;
    });
}

function page(load: Loader) {
  let pending: ReturnType<Loader> | null = null;
  const once: Loader = () => (pending ??= withReload(load)());
  return { Component: lazy(once), preload: once };
}

export const PAGES = {
  changelog: page(() => import('./shell/Changelog')),
  ministryHome: page(() => import('./events/ministry/MinistryHome')),
  ministryApply: page(() => import('./events/ministry/ApplicationWizard')),
  ministrySchedule: page(() => import('./events/ministry/PublishedSchedule')),
  ministryGuide: page(() => import('./events/ministry/PlayerGuide')),
  tyrantHome: page(() => import('./events/tyrant/TyrantPage')),
  tyrantApply: page(() => import('./events/tyrant/TyrantWizard')),
  svs: page(() => import('./events/svs/SvsPage')),
  tal: page(() => import('./events/tal/TalPage')),
  adminLogin: page(() => import('./admin/AdminLogin')),
  adminShell: page(() => import('./admin/AdminShell')),
  adminGuide: page(() => import('./admin/AdminGuidePage')),
};

const BY_PATH: [RegExp, keyof typeof PAGES][] = [
  [/^\/changelog\/?$/, 'changelog'],
  [/^\/minist(?:er|ry)\/?$/, 'ministryHome'],
  [/^\/(?:minist(?:er|ry)\/)?(?:apply|submit|update)\/?$/, 'ministryApply'],
  [/^\/(?:minist(?:er|ry)\/)?schedule\//, 'ministrySchedule'],
  [/^\/(?:minist(?:er|ry)\/)?guide\/?$/, 'ministryGuide'],
  [/^\/tyrant\/?$/, 'tyrantHome'],
  [/^\/tyrant\/apply\/?$/, 'tyrantApply'],
  [/^\/admin\/dashboard/, 'adminShell'],
  [/^\/admin\/guide/, 'adminGuide'],
  [/^\/(?:minist(?:er|ry)\/)?admin\/?$/, 'adminLogin'],
];

export function preloadForPath(pathname: string): void {
  const hit = BY_PATH.find(([re]) => re.test(pathname));
  if (hit) void PAGES[hit[1]].preload().catch(() => undefined);
}
