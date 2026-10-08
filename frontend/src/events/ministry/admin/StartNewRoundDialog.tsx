import { FormEvent, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import api, { EventKey, Round } from '../../../shared/api';
import { errorText } from '../../../shared/apiErrors';
import { localInputToIso } from '../../../shared/datetime';

// "Start new round" replaces v1.4's "Remove all players": it closes the
// current round (nothing is deleted) and opens a new one. Settings carry over;
// published days reset.

interface StartNewRoundDialogProps {
  currentRound: Round | null;
  onClose: () => void;
  onStarted: (round: Round) => void;
  /** Which event's round to start (default ministry). */
  event?: EventKey;
  /** Suggested name; default "Ministry <date>". */
  defaultName?: string;
}

export default function StartNewRoundDialog({ currentRound, onClose, onStarted, event = 'ministry', defaultName }: StartNewRoundDialogProps) {
  const { t, i18n } = useTranslation();
  const [name, setName] = useState(() => defaultName ?? t('admin:round.defaultName', { date: new Date().toLocaleDateString(i18n.language) }));
  const [closing, setClosing] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    nameRef.current?.select();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && !busy && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, busy]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return setError(t('admin:round.nameRequired'));
    setBusy(true);
    setError('');
    try {
      const res = await api.admin.startNewRound(event, { name: name.trim(), closing_time: localInputToIso(closing) });
      onStarted(res.round);
    } catch (err) {
      setError(errorText(t, err, 'admin:round.startError'));
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <form
        onSubmit={submit}
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-round-title"
        data-testid="new-round-dialog"
        className="bg-dark-card rounded-xl p-6 max-w-lg w-full border border-theme-border space-y-4"
      >
        <div className="flex items-center gap-3">
          <AlertTriangle className="w-8 h-8 text-warning shrink-0" aria-hidden="true" />
          <h3 id="new-round-title" className="text-xl font-bold text-theme-text">
            {t('admin:round.startTitle')}
          </h3>
        </div>
        <p className="text-theme-dim text-sm" data-testid="new-round-warning">
          {currentRound
            ? t('admin:round.startWarning', { round: currentRound.name, n: currentRound.application_count ?? 0 })
            : t('admin:round.startFirst')}
        </p>
        <div>
          <label htmlFor="new-round-name" className="block text-sm font-medium text-theme-text mb-2">
            {t('admin:round.name')}
          </label>
          <input
            ref={nameRef}
            id="new-round-name"
            data-testid="new-round-name"
            value={name}
            maxLength={100}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-4 py-2 bg-dark-input border border-theme-border rounded-lg text-theme-text focus:ring-2 focus:ring-accent focus:border-accent"
          />
        </div>
        <div>
          <label htmlFor="new-round-closing" className="block text-sm font-medium text-theme-text mb-2">
            {t('admin:closingTime')} ({t('profile:optional')})
          </label>
          <input
            id="new-round-closing"
            data-testid="new-round-closing"
            type="datetime-local"
            value={closing}
            onChange={(e) => setClosing(e.target.value)}
            className="px-4 py-2 bg-dark-input border border-theme-border rounded-lg text-theme-text focus:ring-2 focus:ring-accent focus:border-accent"
          />
        </div>
        {error && (
          <p className="text-danger text-sm" role="alert" data-testid="new-round-error">
            {error}
          </p>
        )}
        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={busy}
            data-testid="confirm-new-round"
            className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium disabled:opacity-50"
          >
            <RefreshCw className="w-4 h-4" aria-hidden="true" />
            {busy ? t('ministry:form.loading') : t('admin:round.startConfirm')}
          </button>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            data-testid="cancel-new-round"
            className="flex-1 px-4 py-3 bg-dark-bg text-theme-text rounded-lg hover:bg-dark-card-hover font-medium border border-theme-border"
          >
            {t('common:cancel')}
          </button>
        </div>
      </form>
    </div>
  );
}
