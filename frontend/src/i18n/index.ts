import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { detectLanguage, saveLanguage } from './detect';

export { saveLanguage } from './detect';

// Translations live in ./locales/<lang>/<namespace>.json. English is the
// reference: `npm run check:i18n` fails if any other language is missing a key,
// has an extra one, has an empty value, or uses different {{placeholders}}.
//
// Keys are addressed as "<namespace>:<key>", e.g. t('ministry:form.next').

export const LANGUAGES = [
  { code: 'en', name: 'English', flag: '🇬🇧' },
  { code: 'es', name: 'Español', flag: '🇪🇸' },
  { code: 'fr', name: 'Français', flag: '🇫🇷' },
  { code: 'de', name: 'Deutsch', flag: '🇩🇪' },
  { code: 'pl', name: 'Polski', flag: '🇵🇱' },
  { code: 'ko', name: '한국어', flag: '🇰🇷' },
  { code: 'zh', name: '中文', flag: '🇨🇳' },
  { code: 'tr', name: 'Türkçe', flag: '🇹🇷' },
  { code: 'ar', name: 'العربية', flag: '🇸🇦' },
] as const;

export const NAMESPACES = [
  'common',
  'profile',
  'ministry',
  'tyrant',
  'svs',
  'tal',
  'admin',
  'guide',
  'changelog',
] as const;

const RTL_LANGUAGES = ['ar'];

export function isRtl(lang: string): boolean {
  return RTL_LANGUAGES.includes(lang);
}

// Locale files are NOT in the main bundle: vite.config.ts groups each language's
// namespaces into one chunk (locale-<lang>), and only the active language is
// fetched (main.tsx waits for it before the first render, so no key flashes).
// Switching language loads that chunk first, then switches.
const loaders = import.meta.glob('./locales/*/*.json', { import: 'default' }) as Record<
  string,
  () => Promise<Record<string, unknown>>
>;

const loaded = new Map<string, Promise<void>>();

// The guides (namespace 'guide': long help text) are a separate lazy chunk per language (guide-<lang>, see
// vite.config.ts): players opening a sign-up page never download them. A guide page calls useGuidesReady()
// (shared/guide/useGuidesReady.ts), which loads them; from then on a language switch loads that language's
// guides too, before switching, so a guide never shows raw keys.
const LAZY_NAMESPACES = new Set(['guide']);
const nsOf = (path: string) => path.match(/\/([^/]+)\.json$/)![1];
let guidesWanted = false;
const guidesLoaded = new Map<string, Promise<void>>();

/** Fetch (once) the guide namespace of a language. */
export function loadGuides(lang: string): Promise<void> {
  guidesWanted = true;
  let p = guidesLoaded.get(lang);
  if (!p) {
    const load = loaders[`./locales/${lang}/guide.json`];
    p = load ? load().then((data) => void i18n.addResourceBundle(lang, 'guide', data, true, true)) : Promise.resolve();
    p.catch(() => guidesLoaded.delete(lang));
    guidesLoaded.set(lang, p);
  }
  return p;
}

/** Fetch (once) every eager namespace of a language into i18next (plus its guides once a guide page asked). */
export function loadLanguage(lang: string): Promise<void> {
  let p = loaded.get(lang);
  if (!p) {
    const files = Object.entries(loaders).filter(([path]) => path.startsWith(`./locales/${lang}/`) && !LAZY_NAMESPACES.has(nsOf(path)));
    p = Promise.all(
      files.map(async ([path, load]) => {
        i18n.addResourceBundle(lang, nsOf(path), await load(), true, true);
      }),
    ).then(() => undefined);
    p.catch(() => loaded.delete(lang)); // a failed fetch (offline / new deploy) may be retried
    loaded.set(lang, p);
  }
  return guidesWanted ? Promise.all([p, loadGuides(lang)]).then(() => undefined) : p;
}

/** Sets <html dir> (and lang) for the given language. */
export function applyDirection(lang: string): void {
  document.documentElement.dir = isRtl(lang) ? 'rtl' : 'ltr';
  document.documentElement.lang = lang;
}

i18n.on('languageChanged', applyDirection);

/** Switch language because the player chose it: applied AND remembered. */
export function chooseLanguage(code: string): void {
  saveLanguage(code);
  void loadLanguage(code)
    .catch(() => undefined)
    .then(() => i18n.changeLanguage(code));
}

const initialLanguage = detectLanguage();

i18n
  .use(initReactI18next)
  .init({
    resources: {},
    partialBundledLanguages: true,
    // Saved choice > phone/browser language > English (./detect.ts). index.html has
    // already set <html dir/lang> the same way before the first paint.
    lng: initialLanguage,
    fallbackLng: 'en',
    ns: [...NAMESPACES],
    defaultNS: 'common',
    interpolation: {
      escapeValue: false,
    },
  });

applyDirection(i18n.language);

/** Resolves once the starting language (and English, if that fails) is loaded. */
export const i18nReady: Promise<void> = loadLanguage(initialLanguage).catch(() => loadLanguage('en'));

export default i18n;
