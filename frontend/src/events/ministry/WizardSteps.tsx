import { useTranslation } from 'react-i18next';

// v1.4's numbered progress indicator (1 — 2 — 3 — 4 — 5). Like v1.4 it follows
// the page direction, so in Arabic step 1 sits on the right.

export default function WizardSteps({ step, total }: { step: number; total: number }) {
  const { t } = useTranslation();
  const nums = Array.from({ length: total }, (_, i) => i + 1);
  return (
    <ol
      className="flex items-center justify-center mb-8"
      aria-label={t('ministry:wizard.progress')}
      data-testid="wizard-steps"
      data-step={step}
    >
      {nums.map((num) => {
        const state = num < step ? 'done' : num === step ? 'current' : 'todo';
        return (
          <li
            key={num}
            className="flex items-center"
            data-testid={`wizard-step-indicator-${num}`}
            data-state={state}
            aria-current={num === step ? 'step' : undefined}
          >
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${
                step >= num ? 'bg-accent text-dark-bg' : 'bg-dark-bg text-theme-dim border-2 border-theme-border'
              }`}
              aria-hidden="true"
            >
              {num}
            </div>
            {num === step && <span className="sr-only">{t('ministry:wizard.stepOf', { current: step, total })}</span>}
            {num < total && (
              <div className={`w-8 h-1 mx-1 ${step > num ? 'bg-accent' : 'bg-theme-border'}`} aria-hidden="true" />
            )}
          </li>
        );
      })}
    </ol>
  );
}
