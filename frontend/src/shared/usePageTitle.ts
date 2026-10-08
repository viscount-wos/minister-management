import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

/**
 * Sets the browser tab title: the given (already translated) parts, most
 * specific first, then the app name, joined with " · ".
 * usePageTitle(t('tyrant:name')) -> "Frost Dragon Tyrant · State Events".
 * Follows language changes because callers re-render with the new strings.
 */
export function usePageTitle(...parts: (string | null | undefined | false)[]) {
  const { t } = useTranslation();
  const title = [...parts.filter(Boolean), t('common:appTitle')].join(' · ');
  useEffect(() => {
    document.title = title;
  }, [title]);
}
