import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, ArrowRight, CheckCircle, Save } from 'lucide-react';

// Chrome shared by the event wizards (Minister, Frost Dragon Tyrant): the page
// wrapper + card, the result/status card and the Back/Next bar. Phone-first:
// small paddings below sm, and the Back/Next bar sticks to the bottom of the
// screen on phones so it is always in reach (SPEC "Phone-first").

/** Outer page wrapper of a wizard or status card. */
export const WIZARD_PAGE = 'min-h-[70vh] flex items-start sm:items-center justify-center px-2 py-3 sm:p-4';
/** The wizard card itself (the Back/Next bar's negative margins match its padding). */
export const WIZARD_CARD = 'bg-dark-card rounded-2xl px-4 pt-5 pb-0 sm:p-8 border border-theme-border w-full';
/** A step's big title. */
export const STEP_TITLE = 'text-2xl sm:text-3xl font-bold text-accent text-center break-words';

export function StatusCard({
  icon,
  tone,
  title,
  body,
  testId,
  children,
}: {
  icon: ReactNode;
  tone: 'danger' | 'success' | 'dim';
  title: string;
  body?: string;
  testId: string;
  children?: ReactNode;
}) {
  const titleClass = tone === 'danger' ? 'text-danger' : tone === 'success' ? 'text-accent' : 'text-theme-text';
  return (
    <div className="min-h-[70vh] flex items-center justify-center p-3 sm:p-4">
      <div
        className="bg-dark-card rounded-2xl px-5 py-8 sm:p-12 border border-theme-border max-w-md w-full text-center"
        data-testid={testId}
      >
        <div className="flex justify-center mb-5 sm:mb-6 [&>svg]:w-16 [&>svg]:h-16 sm:[&>svg]:w-20 sm:[&>svg]:h-20">{icon}</div>
        <h2 className={`text-2xl sm:text-3xl font-bold mb-4 break-words ${titleClass}`}>{title}</h2>
        {body && <p className="text-theme-dim mb-6 break-words">{body}</p>}
        {children}
      </div>
    </div>
  );
}

/** "Back to ..." link button on status cards: 44px tall. */
export function BackLink({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center justify-center gap-2 mx-auto min-h-[44px] px-3 text-accent hover:text-accent-dim transition-colors"
    >
      <ArrowLeft className="w-5 h-5 rtl:rotate-180 shrink-0" aria-hidden="true" />
      {children}
    </button>
  );
}

const NAV_BUTTON =
  'flex flex-1 sm:flex-none items-center justify-center gap-2 min-h-[48px] px-4 sm:px-6 py-3 rounded-lg font-medium transition-colors';

/**
 * Back / Next (or Submit/Update on the last step). Sticky at the bottom of the
 * screen on phones; a plain row from sm up. Test ids: wizard-back, wizard-next,
 * wizard-submit (data-mode).
 */
export function WizardNav({
  isLast,
  busy,
  mode,
  onBack,
  onNext,
  onSubmit,
}: {
  isLast: boolean;
  busy: boolean;
  mode: 'new' | 'edit';
  onBack: () => void;
  onNext: () => void;
  onSubmit: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div
      className="sticky bottom-0 z-20 -mx-4 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] mt-6 bg-dark-card/95 backdrop-blur border-t border-theme-border rounded-b-2xl flex gap-3 justify-between sm:static sm:mx-0 sm:px-0 sm:pt-0 sm:pb-0 sm:mt-8 sm:bg-transparent sm:backdrop-blur-none sm:border-0 sm:rounded-none"
      data-testid="wizard-nav"
    >
      <button
        type="button"
        onClick={onBack}
        data-testid="wizard-back"
        className={`${NAV_BUTTON} border-2 border-theme-border hover:bg-dark-card-hover text-theme-text`}
      >
        <ArrowLeft className="w-5 h-5 rtl:rotate-180 shrink-0" aria-hidden="true" />
        {t('ministry:form.back')}
      </button>
      {!isLast ? (
        <button
          type="button"
          onClick={onNext}
          disabled={busy}
          data-testid="wizard-next"
          className={`${NAV_BUTTON} bg-accent text-dark-bg hover:bg-accent-dim disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          {busy ? t('ministry:form.loading') : t('ministry:form.next')}
          <ArrowRight className="w-5 h-5 rtl:rotate-180 shrink-0" aria-hidden="true" />
        </button>
      ) : (
        <button
          type="button"
          onClick={onSubmit}
          disabled={busy}
          data-testid="wizard-submit"
          data-mode={mode}
          className={`${NAV_BUTTON} bg-accent text-dark-bg hover:bg-accent-dim disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          {busy ? t('ministry:form.loading') : mode === 'edit' ? t('ministry:form.update') : t('ministry:form.submit')}
          {mode === 'edit' ? (
            <Save className="w-5 h-5 shrink-0" aria-hidden="true" />
          ) : (
            <CheckCircle className="w-5 h-5 shrink-0" aria-hidden="true" />
          )}
        </button>
      )}
    </div>
  );
}
