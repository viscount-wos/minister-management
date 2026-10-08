import { useTranslation } from 'react-i18next';
import { History, CheckCircle } from 'lucide-react';

// "Use my last answers": round-specific answers start blank in a new round;
// this copies them from the player's most recent earlier application.
// Rendered only when such an application exists.

interface UseLastAnswersProps {
  /** Name of the round the previous application belongs to; null = none (renders nothing). */
  previousRoundName: string | null | undefined;
  available: boolean;
  applied: boolean;
  onUse: () => void;
  disabled?: boolean;
}

export default function UseLastAnswers({ previousRoundName, available, applied, onUse, disabled }: UseLastAnswersProps) {
  const { t } = useTranslation();
  if (!available) return null;
  const round = previousRoundName || t('profile:lastAnswers.previousRound');

  return (
    <div className="p-4 rounded-lg border border-accent/30 bg-accent/10" data-testid="last-answers">
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:justify-between">
        <p className="text-sm text-theme-text">{t('profile:lastAnswers.hint', { round })}</p>
        <button
          type="button"
          onClick={onUse}
          disabled={disabled}
          data-testid="use-last-answers"
          className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors disabled:opacity-50 shrink-0"
        >
          <History className="w-4 h-4" aria-hidden="true" />
          {t('profile:lastAnswers.button')}
        </button>
      </div>
      {applied && (
        <p
          className="mt-3 flex items-center gap-2 text-sm font-medium text-success"
          role="status"
          data-testid="last-answers-applied"
        >
          <CheckCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
          {t('profile:lastAnswers.applied', { round })}
        </p>
      )}
    </div>
  );
}
