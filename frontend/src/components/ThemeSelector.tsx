import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Palette } from 'lucide-react';
import { THEMES, ThemeId, applyTheme, getSavedTheme, saveTheme } from '../utils/theme';

export default function ThemeSelector() {
  const { t } = useTranslation();
  const [theme, setTheme] = useState<ThemeId>(getSavedTheme);

  const handleThemeChange = (id: ThemeId) => {
    applyTheme(id);
    saveTheme(id);
    setTheme(id);
  };

  return (
    <div className="flex items-center gap-2 flex-wrap justify-end">
      <Palette className="w-4 h-4 text-theme-dim shrink-0" aria-hidden="true" />
      <span className="sr-only">{t('common:theme.title')}</span>
      {THEMES.map((option) => (
        <button
          key={option.id}
          onClick={() => handleThemeChange(option.id)}
          aria-pressed={theme === option.id}
          className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
            theme === option.id
              ? 'bg-accent text-dark-bg'
              : 'bg-dark-card border border-theme-border text-theme-dim hover:border-accent hover:text-theme-text'
          }`}
        >
          {t(option.labelKey)}
        </button>
      ))}
    </div>
  );
}
