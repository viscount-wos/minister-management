import { useTranslation } from 'react-i18next';
import { Globe } from 'lucide-react';
import { LANGUAGES, chooseLanguage } from '../i18n/index';
import CompactSelect from './CompactSelect';

// Language dropdown: globe icon + the current language in its own script; the
// list shows all 9 by native name. A choice is remembered (localStorage
// 'preferred_language'); <html dir/lang> follow via i18n/index.ts.
export default function LanguageSelector() {
  const { t, i18n } = useTranslation();
  const current = LANGUAGES.find((l) => l.code === i18n.language) ?? LANGUAGES[0];

  return (
    <CompactSelect
      icon={Globe}
      label={t('common:header.language')}
      display={current.name}
      displayLang={current.code}
      value={current.code}
      onChange={chooseLanguage}
      testId="language-select"
    >
      {LANGUAGES.map((lang) => (
        <option key={lang.code} value={lang.code} lang={lang.code}>
          {lang.name}
        </option>
      ))}
    </CompactSelect>
  );
}
