import { useTranslation } from 'react-i18next';
import { HelpCircle } from 'lucide-react';

/** "Where do I find my ID?" under every player-ID input: a native, tappable <details> (no images, no JS). */
export default function FidHelp() {
  const { t } = useTranslation();
  return (
    <details className="mt-1 text-sm group" data-testid="fid-help">
      <summary
        className="inline-flex items-center gap-1.5 min-h-[44px] cursor-pointer select-none text-accent hover:text-accent-dim list-none [&::-webkit-details-marker]:hidden"
        data-testid="fid-help-toggle"
      >
        <HelpCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
        {t('common:fidHelp.question')}
      </summary>
      <p className="mt-1 mb-2 p-3 rounded-lg bg-dark-input border border-theme-border text-theme-text leading-relaxed" data-testid="fid-help-text">
        {t('common:fidHelp.answer')}
      </p>
    </details>
  );
}
