import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { loadGuides } from '../../i18n';

/**
 * Guide pages only: loads the lazy 'guide' namespace of the current language (i18n/index.ts) and says when it is
 * there. Until then the page shows "Loading…" instead of raw keys. If the language's guides can't be fetched, the
 * English ones are used (i18next falls back to en).
 */
export function useGuidesReady(): boolean {
  const { i18n } = useTranslation();
  const lang = i18n.resolvedLanguage || i18n.language;
  const [doneFor, setDoneFor] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    loadGuides(lang)
      .catch(() => loadGuides('en'))
      .catch(() => undefined)
      .then(() => live && setDoneFor(lang));
    return () => {
      live = false;
    };
  }, [lang]);

  return i18n.hasResourceBundle(lang, 'guide') || doneFor === lang;
}

/** Small placeholder while the guide text loads. */
export function GuideLoading() {
  const { t } = useTranslation();
  return (
    <p className="text-center text-theme-dim py-16" data-testid="guide-loading">
      {t('common:loading')}
    </p>
  );
}
