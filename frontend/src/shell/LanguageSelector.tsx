import { useTranslation } from 'react-i18next';
import { LANGUAGES } from '../i18n/index';

export default function LanguageSelector() {
  const { i18n } = useTranslation();

  const handleLanguageChange = (langCode: string) => {
    // <html dir> follows via the languageChanged listener in i18n/index.ts
    i18n.changeLanguage(langCode);
  };

  return (
    <div className="flex items-center gap-2 flex-wrap justify-end">
      {LANGUAGES.map((lang) => (
        <button
          key={lang.code}
          onClick={() => handleLanguageChange(lang.code)}
          className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
            i18n.language === lang.code
              ? 'bg-accent text-dark-bg'
              : 'bg-dark-card border border-theme-border text-theme-dim hover:border-accent hover:text-theme-text'
          }`}
        >
          {lang.name}
        </button>
      ))}
    </div>
  );
}
