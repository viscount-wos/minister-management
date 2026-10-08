import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Palette } from 'lucide-react';
import { THEMES, ThemeId, applyTheme, getSavedTheme, saveTheme } from '../shared/theme';
import CompactSelect from './CompactSelect';

// Theme dropdown: palette icon + theme name (icon only on phones; the name is
// still the select's value for screen readers). Remembered in localStorage.
export default function ThemeSelector() {
  const { t } = useTranslation();
  const [theme, setTheme] = useState<ThemeId>(getSavedTheme);

  const handleThemeChange = (value: string) => {
    const option = THEMES.find((x) => x.id === value);
    if (!option) return;
    applyTheme(option.id);
    saveTheme(option.id);
    setTheme(option.id);
  };
  const current = THEMES.find((x) => x.id === theme) ?? THEMES[0];

  return (
    <CompactSelect
      icon={Palette}
      label={t('common:theme.title')}
      display={t(current.labelKey)}
      value={theme}
      onChange={handleThemeChange}
      testId="theme-select"
      textFromSm
    >
      {THEMES.map((option) => (
        <option key={option.id} value={option.id}>
          {t(option.labelKey)}
        </option>
      ))}
    </CompactSelect>
  );
}
