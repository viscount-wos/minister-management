import { FormEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Search } from 'lucide-react';
import { Field } from './fields';
import FidHelp from './FidHelp';

// "Enter your FID" step shared by every event: players never log in, the FID
// is how they find their profile and their application in the current round.

export const FID_RE = /^\d{1,20}$/;

interface FidLookupProps {
  onSubmit: (fid: string) => void;
  loading?: boolean;
  initialFid?: string;
  /** Text above the input, e.g. which round this is for. */
  intro?: string;
}

export default function FidLookup({ onSubmit, loading, initialFid = '', intro }: FidLookupProps) {
  const { t } = useTranslation();
  const [fid, setFid] = useState(initialFid);
  const [error, setError] = useState('');

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const clean = fid.trim();
    if (!clean) return setError(t('profile:enterPlayerID'));
    if (!FID_RE.test(clean)) return setError(t('profile:fidDigitsOnly'));
    setError('');
    onSubmit(clean);
  };

  return (
    <form onSubmit={submit} noValidate data-testid="fid-form">
      {intro && <p className="text-theme-dim text-center mb-6">{intro}</p>}
      <div className="flex flex-col sm:flex-row gap-4 sm:items-end">
        <Field
          id="fid-lookup"
          name="fid"
          testId="fid-input"
          className="flex-1"
          label={t('profile:playerID')}
          placeholder={t('profile:playerIDPlaceholder')}
          inputMode="numeric"
          autoComplete="off"
          value={fid}
          invalid={!!error}
          onChange={(e) => setFid(e.target.value)}
        />
        <button
          type="submit"
          disabled={loading}
          data-testid="fid-continue"
          className="flex items-center justify-center gap-2 px-6 py-3 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors disabled:opacity-50"
        >
          <Search className="w-5 h-5" aria-hidden="true" />
          {loading ? t('ministry:form.loading') : t('profile:continue')}
        </button>
      </div>
      <FidHelp />
      {error && (
        <p className="mt-3 text-sm text-danger" role="alert" data-testid="fid-error">
          {error}
        </p>
      )}
    </form>
  );
}
