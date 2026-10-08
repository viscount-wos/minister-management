import { FormEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Save, X, AlertCircle } from 'lucide-react';
import api, { Round } from '../shared/api';
import { errorText } from '../shared/apiErrors';

/**
 * Inline "Rename round" form in the Event Management header, for every event. Works on past (closed) rounds
 * too: the name is only a label (e.g. "Imported from previous system" -> "September 2026").
 */
export default function RenameRound({
  round,
  onCancel,
  onRenamed,
}: {
  round: Round;
  onCancel: () => void;
  onRenamed: (r: Round) => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState(round.name);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const clean = name.trim();
    if (!clean) return setError(t('admin:round.nameRequired'));
    setBusy(true);
    setError('');
    try {
      onRenamed(await api.admin.renameRound(round.id, clean));
    } catch (err) {
      setError(errorText(t, err, 'admin:round.renameError'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="mt-4 flex flex-wrap items-end gap-3" data-testid="rename-round-form">
      <div className="w-full sm:w-auto min-w-0 flex-1 sm:flex-none">
        <label htmlFor="rename-round-input" className="block text-sm font-medium text-theme-text mb-1">
          {t('admin:round.name')}
        </label>
        <input
          id="rename-round-input"
          data-testid="rename-round-input"
          value={name}
          maxLength={100}
          autoFocus
          onChange={(e) => setName(e.target.value)}
          className="w-full sm:w-80 max-w-full min-h-[44px] px-3 py-2 text-base bg-dark-input border border-theme-border rounded-lg text-theme-text focus:ring-2 focus:ring-accent focus:border-accent"
        />
      </div>
      <button
        type="submit"
        disabled={busy}
        data-testid="rename-round-save"
        className="flex items-center gap-2 min-h-[44px] px-4 py-2 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors disabled:opacity-50"
      >
        <Save className="w-4 h-4" aria-hidden="true" />
        {t('common:save')}
      </button>
      <button
        type="button"
        onClick={onCancel}
        data-testid="rename-round-cancel"
        className="flex items-center gap-2 min-h-[44px] px-4 py-2 border border-theme-border rounded-lg text-theme-text hover:bg-dark-card-hover transition-colors"
      >
        <X className="w-4 h-4" aria-hidden="true" />
        {t('common:cancel')}
      </button>
      {error && (
        <p className="w-full flex items-center gap-2 text-sm text-danger" role="alert" data-testid="rename-round-error">
          <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}
    </form>
  );
}
