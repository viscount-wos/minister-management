// Colour theme preference.
//
// Themes are palettes of CSS custom properties defined in index.css. Applying
// one stamps data-theme on <html>; the default theme stamps nothing and uses
// the bare :root tokens, so an unknown or missing preference degrades to the
// scheme the site has always had.

export type ThemeId = 'ministry-dark' | 'reading' | 'low-glare';

export const DEFAULT_THEME: ThemeId = 'ministry-dark';

export const THEMES: { id: ThemeId; labelKey: string }[] = [
  { id: 'ministry-dark', labelKey: 'theme.dark' },
  { id: 'reading', labelKey: 'theme.reading' },
  { id: 'low-glare', labelKey: 'theme.lowGlare' },
];

const STORAGE_KEY = 'preferred_theme';

function isThemeId(value: string | null): value is ThemeId {
  return !!value && THEMES.some((t) => t.id === value);
}

export function getSavedTheme(): ThemeId {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (isThemeId(stored)) return stored;
  } catch {
    // Private browsing or blocked storage - fall through to the default.
  }
  return DEFAULT_THEME;
}

export function saveTheme(id: ThemeId): void {
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    // Preference simply will not persist; the page still themes correctly.
  }
}

export function applyTheme(id: ThemeId): void {
  const root = document.documentElement;
  if (id === DEFAULT_THEME) {
    root.removeAttribute('data-theme');
  } else {
    root.setAttribute('data-theme', id);
  }
}
