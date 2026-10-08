import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { BookOpen } from 'lucide-react';

/** Small "read the guide" link (wizard step 1, shared plan view). `label` = a common:guideLinks.* key. */
export default function GuideLink({ to, testId, label = 'common:guideLinks.wizardLink' }: { to: string; testId: string; label?: string }) {
  const { t } = useTranslation();
  return (
    <Link
      to={to}
      data-testid={testId}
      className="inline-flex items-center gap-1.5 min-h-[44px] text-sm text-accent hover:text-accent-dim underline-offset-2 hover:underline"
    >
      <BookOpen className="w-4 h-4 shrink-0" aria-hidden="true" />
      {t(label)}
    </Link>
  );
}
