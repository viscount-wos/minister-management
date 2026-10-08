import { useTranslation } from 'react-i18next';

// v1.4's numbered progress indicator (1 — 2 — 3 — 4 — 5). Like v1.4 it follows
// the page direction, so in Arabic step 1 sits on the right.
// Phone-first: the connectors stretch/shrink to the available width (circles
// never touch the card edge), circles are 32px on phones and 40px from sm up.

export default function WizardSteps({ step, total }: { step: number; total: number }) {
  const { t } = useTranslation();
  const nums = Array.from({ length: total }, (_, i) => i + 1);
  return (
    <ol
      className="flex items-center w-full max-w-md mx-auto mb-6 sm:mb-8 px-1"
      aria-label={t('ministry:wizard.progress')}
      data-testid="wizard-steps"
      data-step={step}
    >
      {nums.map((num) => {
        const state = num < step ? 'done' : num === step ? 'current' : 'todo';
        return (
          <li
            key={num}
            className={`flex items-center ${num < total ? 'flex-1' : ''}`}
            data-testid={`wizard-step-indicator-${num}`}
            data-state={state}
            aria-current={num === step ? 'step' : undefined}
          >
            <div
              className={`w-8 h-8 sm:w-10 sm:h-10 shrink-0 rounded-full flex items-center justify-center text-sm sm:text-base font-bold ${
                step >= num ? 'bg-accent text-dark-bg' : 'bg-dark-bg text-theme-dim border-2 border-theme-border'
              } ${num === step ? 'ring-2 ring-accent/40 ring-offset-2 ring-offset-dark-card' : ''}`}
              aria-hidden="true"
            >
              {num}
            </div>
            {num === step && <span className="sr-only">{t('ministry:wizard.stepOf', { current: step, total })}</span>}
            {num < total && (
              <div className={`flex-1 min-w-[0.5rem] h-1 mx-1 sm:mx-2 rounded ${step > num ? 'bg-accent' : 'bg-theme-border'}`} aria-hidden="true" />
            )}
          </li>
        );
      })}
    </ol>
  );
}
