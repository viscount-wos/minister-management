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

// Every locale file is bundled (eager), so no namespace ever loads late.
const modules = import.meta.glob('./locales/*/*.json', {
  eager: true,
  import: 'default',
}) as Record<string, Record<string, unknown>>;

const resources: Record<string, Record<string, Record<string, unknown>>> = {};
for (const [path, data] of Object.entries(modules)) {
  const match = path.match(/\.\/locales\/([^/]+)\/([^/]+)\.json$/);
  if (!match) continue;
  const [, lang, ns] = match;
  resources[lang] ??= {};
  resources[lang][ns] = data;
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
  void i18n.changeLanguage(code);
}

i18n
  .use(initReactI18next)
  .init({
    resources,
    // Saved choice > phone/browser language > English (./detect.ts). index.html has
    // already set <html dir/lang> the same way before the first paint.
    lng: detectLanguage(),
    fallbackLng: 'en',
    ns: [...NAMESPACES],
    defaultNS: 'common',
    interpolation: {
      escapeValue: false,
    },
  });

applyDirection(i18n.language);

export default i18n;
