import { useTranslation } from 'react-i18next';
import { useTimezone } from './TimezoneContext';
import { formatDateTime } from './datetime';

/** A moment in the header's display timezone and the UI language: "Sat 10 Oct, 15:06 (London)". */
export function useFormatDateTime() {
  const { i18n } = useTranslation();
  const { timezone } = useTimezone();
  return (iso: string | null | undefined, opts: { withZone?: boolean; weekday?: boolean; isolate?: boolean } = {}) =>
    formatDateTime(iso, { timezone, lang: i18n.language, ...opts });
}

export default function DateTime({ iso, testId, withZone }: { iso: string | null | undefined; testId?: string; withZone?: boolean }) {
  const fmt = useFormatDateTime();
  return (
    <bdi data-testid={testId} data-iso={iso ?? undefined}>
      {fmt(iso, { withZone, isolate: false })}
    </bdi>
  );
}
