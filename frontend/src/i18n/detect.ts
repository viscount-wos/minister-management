// Which UI language to start in (SPEC "Phone-first header and auto-detect"):
//   1. the player's saved choice (localStorage 'preferred_language'),
//   2. else the first supported language in the phone/browser languages
//      (navigator.languages), matched on the base code: 'es-MX' -> es,
//      'zh-TW' / 'zh-Hant-HK' -> zh, 'ar-SA' -> ar,
//   3. else English.
// Never IP or geolocation: wrong for expats / VPN users and needs a third party.
//
// index.html carries an inline copy of this logic (it must run before the first
// paint so Arabic never flashes left-to-right). Keep the two in step.

export const SUPPORTED_LANGUAGES = ['en', 'es', 'fr', 'de', 'pl', 'ko', 'zh', 'tr', 'ar'] as const;
export type LanguageCode = (typeof SUPPORTED_LANGUAGES)[number];

export const LANGUAGE_STORAGE_KEY = 'preferred_language';

export function isSupportedLanguage(code: string | null | undefined): code is LanguageCode {
  return !!code && (SUPPORTED_LANGUAGES as readonly string[]).includes(code);
}

/** 'es-MX' -> 'es', 'zh_Hant_TW' -> 'zh', 'xx' -> null. */
export function matchLanguage(tag: string | null | undefined): LanguageCode | null {
  if (!tag) return null;
  const base = tag.trim().toLowerCase().split(/[-_]/)[0];
  return isSupportedLanguage(base) ? base : null;
}

export function getSavedLanguage(): LanguageCode | null {
  try {
    const saved = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    return isSupportedLanguage(saved) ? saved : null;
  } catch {
    return null;
  }
}

export function saveLanguage(code: string): void {
  if (!isSupportedLanguage(code)) return;
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, code);
  } catch {
    // Private mode / blocked storage: the choice just won't persist.
  }
}

/** First supported language in the browser's preference list, or null. */
export function browserLanguage(languages?: readonly string[]): LanguageCode | null {
  const list =
    languages ??
    (typeof navigator !== 'undefined'
      ? navigator.languages && navigator.languages.length
        ? navigator.languages
        : [navigator.language]
      : []);
  for (const tag of list) {
    const hit = matchLanguage(tag);
    if (hit) return hit;
  }
  return null;
}

export function detectLanguage(): LanguageCode {
  return getSavedLanguage() ?? browserLanguage() ?? 'en';
}
