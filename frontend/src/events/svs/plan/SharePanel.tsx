// Share the plan: a secret read-only link (128-bit token) for the whole state; "New link" replaces it (the old one
// stops working), "Turn off sharing" kills it. "Show real names to the state" is a plan setting (autosaved).
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Copy, Eye, EyeOff, Link2, RefreshCw, Share2, ExternalLink, Check } from 'lucide-react';
import { errorText } from '../../../shared/apiErrors';
import { planApi, shareUrl } from './api';
import { usePlanner } from './PlannerContext';
import type { ShareInfo } from './model';

export default function SharePanel({ roundId, share, onShare }: { roundId: number; share: ShareInfo; onShare: (s: ShareInfo) => void }) {
  const { t } = useTranslation();
  const ctx = usePlanner();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  const act = async (action: 'create' | 'rotate' | 'disable') => {
    if (action === 'rotate' && !window.confirm(t('svs:plan.share.confirmRotate'))) return;
    if (action === 'disable' && !window.confirm(t('svs:plan.share.confirmDisable'))) return;
    setBusy(true);
    setError('');
    try {
      onShare((await planApi.share(roundId, action)).share);
    } catch (e) {
      setError(errorText(t, e));
    } finally {
      setBusy(false);
    }
  };

  const url = share.path ? shareUrl(share.path) : '';
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard blocked: the field is selectable
    }
  };

  return (
    <section className="bg-dark-card border border-theme-border rounded-xl p-3 space-y-2" data-testid="share-panel" data-enabled={share.enabled}>
      <div className="flex items-center gap-2">
        <Share2 className="w-4 h-4 text-accent" aria-hidden="true" />
        <h3 className="font-bold text-theme-text text-sm">{t('svs:plan.share.title')}</h3>
      </div>
      {share.enabled ? (
        <>
          <div className="flex gap-1.5">
            <input
              readOnly
              value={url}
              onFocus={(e) => e.target.select()}
              aria-label={t('svs:plan.share.link')}
              data-testid="share-url"
              dir="ltr"
              className="flex-1 min-w-0 min-h-[36px] px-2 text-xs bg-dark-input border border-theme-border rounded-md text-theme-text"
            />
            <button
              type="button"
              onClick={copy}
              data-testid="share-copy"
              className="shrink-0 inline-flex items-center gap-1 min-h-[36px] px-2.5 rounded-md bg-accent text-dark-bg text-xs font-bold"
            >
              {copied ? <Check className="w-4 h-4" aria-hidden="true" /> : <Copy className="w-4 h-4" aria-hidden="true" />}
              {copied ? t('svs:plan.share.copied') : t('svs:plan.share.copy')}
            </button>
            <a
              href={share.path ?? '#'}
              target="_blank"
              rel="noreferrer noopener"
              data-testid="share-open"
              aria-label={t('svs:plan.share.open')}
              title={t('svs:plan.share.open')}
              className="shrink-0 inline-flex items-center justify-center w-9 min-h-[36px] rounded-md border border-theme-border text-theme-dim hover:text-accent"
            >
              <ExternalLink className="w-4 h-4" aria-hidden="true" />
            </a>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              disabled={busy}
              onClick={() => act('rotate')}
              data-testid="share-rotate"
              className="inline-flex items-center gap-1 min-h-[32px] px-2.5 rounded-md border border-theme-border text-xs text-theme-text hover:border-accent"
            >
              <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
              {t('svs:plan.share.rotate')}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => act('disable')}
              data-testid="share-disable"
              className="inline-flex items-center gap-1 min-h-[32px] px-2.5 rounded-md border border-danger/50 text-xs text-danger hover:bg-danger/10"
            >
              <EyeOff className="w-3.5 h-3.5" aria-hidden="true" />
              {t('svs:plan.share.disable')}
            </button>
          </div>
        </>
      ) : (
        <>
          <p className="text-xs text-theme-dim">{t('svs:plan.share.off')}</p>
          <button
            type="button"
            disabled={busy}
            onClick={() => act('create')}
            data-testid="share-create"
            className="inline-flex items-center gap-1.5 min-h-[36px] px-3 rounded-md bg-accent text-dark-bg text-sm font-bold disabled:opacity-50"
          >
            <Link2 className="w-4 h-4" aria-hidden="true" />
            {t('svs:plan.share.create')}
          </button>
        </>
      )}
      <label className="flex items-start gap-2 text-xs text-theme-text cursor-pointer pt-1">
        <input
          type="checkbox"
          checked={ctx.doc.show_real_names}
          disabled={ctx.readOnly}
          onChange={(e) => ctx.update((d) => void (d.show_real_names = e.target.checked))}
          data-testid="show-real-names"
          className="mt-0.5 w-4 h-4 accent-accent"
        />
        <span>
          <span className="inline-flex items-center gap-1 font-semibold">
            <Eye className="w-3.5 h-3.5" aria-hidden="true" />
            {t('svs:plan.share.realNames')}
          </span>
          <span className="block text-theme-dim">{t('svs:plan.share.realNamesHint')}</span>
        </span>
      </label>
      {error && (
        <p className="text-xs text-danger" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
