import { ReactNode, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { X, UserPlus, Search, AlertCircle } from 'lucide-react';
import api, { ApiError, EventKey, Profile } from '../shared/api';
import { errorText } from '../shared/apiErrors';
import { Field } from '../shared/fields';
import { FID_RE } from '../shared/FidLookup';

// Event Management "Add player" (every event): create a sign-up in the selected round for someone who didn't sign
// up (POST /api/admin/rounds/<id>/applications). The FID is required; a FID with no profile also needs the in-game
// name; everything else is optional. Event-specific fields come in as `children`, their values via `extra()`.
// Looking the FID up first fills the name/alliance from the shared profile and tells the event (onProfile) so it
// can pre-fill its own fields (e.g. troop levels).

export interface AddPlayerExtra {
  profile?: Record<string, unknown>;
  answers?: Record<string, unknown>;
}

interface Props {
  event: EventKey;
  roundId: number;
  onClose: () => void;
  /** Called after a successful add with the player's name. */
  onAdded: (name: string) => void;
  children?: ReactNode;
  extra?: () => AddPlayerExtra;
  onProfile?: (profile: Profile | null) => void;
}

export function AddPlayerButton({ onClick }: { onClick: () => void }) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid="add-player"
      className="flex items-center gap-2 min-h-[44px] px-4 py-2 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors"
    >
      <UserPlus className="w-4 h-4" aria-hidden="true" />
      {t('admin:addPlayer.button')}
    </button>
  );
}

export default function AddPlayerDialog({ event, roundId, onClose, onAdded, children, extra, onProfile }: Props) {
  const { t } = useTranslation();
  const [fid, setFid] = useState('');
  const [checkedFid, setCheckedFid] = useState('');
  const [known, setKnown] = useState<boolean | null>(null);
  const [name, setName] = useState('');
  const [alliance, setAlliance] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [invalid, setInvalid] = useState<string | null>(null);

  const lookup = async () => {
    const clean = fid.trim();
    if (!FID_RE.test(clean)) {
      setInvalid('fid');
      setError(t(clean ? 'profile:fidDigitsOnly' : 'profile:fidRequired'));
      return;
    }
    setBusy(true);
    setError('');
    setInvalid(null);
    try {
      const p = await api.admin.profile(clean).catch((e) => {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      });
      setKnown(!!p);
      setCheckedFid(clean);
      setName(p?.game_name ?? '');
      setAlliance((p?.alliance ?? '').toUpperCase().slice(0, 3));
      onProfile?.(p);
    } catch (e) {
      setError(errorText(t, e));
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    const clean = fid.trim();
    if (!FID_RE.test(clean)) {
      setInvalid('fid');
      return setError(t(clean ? 'profile:fidDigitsOnly' : 'profile:fidRequired'));
    }
    if (!name.trim()) {
      setInvalid('profile.game_name');
      return setError(t('ministry:form.required'));
    }
    setBusy(true);
    setError('');
    setInvalid(null);
    const ex = extra?.() ?? {};
    const ally = alliance.trim().toUpperCase();
    try {
      await api.admin.addPlayer(roundId, {
        fid: clean,
        profile: { game_name: name.trim(), ...(ally ? { alliance: ally } : {}), ...(ex.profile ?? {}) },
        ...(ex.answers ? { answers: ex.answers } : {}),
      });
      onAdded(name.trim());
    } catch (e) {
      if (e instanceof ApiError) setInvalid(e.code === 'APPLICATION_EXISTS' ? 'fid' : e.field);
      setError(errorText(t, e, 'admin:addPlayer.error'));
    } finally {
      setBusy(false);
    }
  };

  const status = known == null || checkedFid !== fid.trim() ? null : known ? t('admin:addPlayer.known') : t('admin:addPlayer.newPlayer');

  // Portal to <body>: a transformed/animated ancestor would otherwise make `fixed` relative to it (the overlay then
  // stops covering the page). items-start + my-auto centres short dialogs while a tall one (Tyrant) scrolls from its
  // top instead of being clipped above the viewport.
  return createPortal(
    <div className="fixed inset-0 bg-black/50 flex items-start justify-center p-2 sm:p-4 z-50 overflow-y-auto">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-player-title"
        data-testid="add-player-dialog"
        data-event={event}
        className="bg-dark-card rounded-xl p-4 sm:p-6 max-w-2xl w-full my-auto border border-theme-border"
      >
        <div className="flex items-center justify-between gap-3 mb-2">
          <h3 id="add-player-title" className="text-2xl font-bold text-accent">
            {t('admin:addPlayer.title')}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] text-theme-dim hover:text-theme-text"
            aria-label={t('common:close')}
            data-testid="add-player-close"
          >
            <X className="w-6 h-6" aria-hidden="true" />
          </button>
        </div>
        <p className="text-theme-dim text-sm mb-5">{t('admin:addPlayer.desc')}</p>

        <div className="space-y-4">
          <div className="flex items-end gap-2">
            <Field
              id="add-fid"
              className="flex-1"
              label={t('tyrant:fields.fid')}
              required
              inputMode="numeric"
              autoComplete="off"
              value={fid}
              invalid={invalid === 'fid'}
              onChange={(e) => setFid(e.target.value)}
              onBlur={() => fid.trim() && fid.trim() !== checkedFid && lookup()}
            />
            <button
              type="button"
              onClick={lookup}
              disabled={busy}
              data-testid="add-lookup"
              className="flex items-center gap-2 min-h-[48px] px-4 border border-theme-border rounded-lg text-theme-text hover:bg-dark-card-hover disabled:opacity-50"
            >
              <Search className="w-4 h-4" aria-hidden="true" />
              {t('admin:addPlayer.lookup')}
            </button>
          </div>
          {status && (
            <p className="text-sm text-theme-dim -mt-2" data-testid="add-status" data-known={known ? 'true' : 'false'}>
              {status}
            </p>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Field
              id="add-name"
              className="sm:col-span-2"
              label={t('tyrant:fields.ingameName')}
              required
              maxLength={64}
              autoComplete="off"
              value={name}
              invalid={invalid === 'profile.game_name'}
              onChange={(e) => setName(e.target.value)}
            />
            <Field
              id="add-alliance"
              label={`${t('tyrant:fields.alliance')} (${t('profile:optional')})`}
              maxLength={3}
              autoComplete="off"
              inputClassName="uppercase"
              placeholder={t('tyrant:fields.alliancePlaceholder')}
              value={alliance}
              invalid={invalid === 'profile.alliance'}
              onChange={(e) => setAlliance(e.target.value.toUpperCase().slice(0, 3))}
            />
          </div>

          {children && (
            <div className="pt-4 border-t border-theme-border space-y-4" data-testid="add-event-fields">
              <p className="text-sm text-theme-dim">{t('admin:addPlayer.optionalHint')}</p>
              {children}
            </div>
          )}

          {error && (
            <div className="p-3 bg-danger/10 border border-danger/30 rounded-lg flex items-center gap-2 text-danger" role="alert" data-testid="add-error">
              <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
              {error}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={save}
              disabled={busy}
              data-testid="add-save"
              className="flex-1 flex items-center justify-center gap-2 min-h-[48px] px-4 py-3 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium disabled:opacity-50"
            >
              <UserPlus className="w-5 h-5" aria-hidden="true" />
              {t('admin:addPlayer.save')}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex-1 min-h-[48px] px-4 py-3 bg-dark-bg text-theme-text rounded-lg hover:bg-dark-card-hover font-medium border border-theme-border"
            >
              {t('common:cancel')}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
