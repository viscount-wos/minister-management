import { ReactNode, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { X, UserPlus, Search, AlertCircle, Save, Info } from 'lucide-react';
import api, { ApiError, EventKey, Profile } from '../shared/api';
import { errorText } from '../shared/apiErrors';
import { Field } from '../shared/fields';
import { FID_RE } from '../shared/FidLookup';
import { DialogErrorContext, InlineError } from './dialogErrors';

// Event Management "Add player" (every event): create a sign-up in the selected round for someone who didn't sign
// up (POST /api/admin/rounds/<id>/applications). The FID is required; a FID with no profile also needs the in-game
// name; everything else is optional. Event-specific fields come in as `children`, their values via `extra()`.
// Looking the FID up first fills the name/alliance from the shared profile and tells the event (onProfile) so it
// can pre-fill its own fields (e.g. troop levels).
//
// EDIT mode (`edit`, v2.2.1, SVS + Frost Dragon Tyrant): the same form for one existing sign-up. The FID is shown
// read-only, the fields come prefilled, and Save sends PUT /api/admin/applications/<id> (admin mode: blanks allowed
// where the API allows them). Name and alliance are sent only when changed (a legacy 4-character tag survives an edit
// that doesn't touch it). A validation error lands on its field: the event's fields read it via DialogErrorContext.

export interface AddPlayerExtra {
  profile?: Record<string, unknown>;
  answers?: Record<string, unknown>;
}

export interface EditTarget {
  appId: number;
  fid: string;
  name: string;
  alliance: string;
}

/** A client-side check before saving: the API field path it belongs to and the translated message. */
export interface ClientError {
  field: string;
  message: string;
}

interface Props {
  event: EventKey;
  roundId: number;
  onClose: () => void;
  /** Called after a successful add with the player's name. */
  onAdded?: (name: string) => void;
  children?: ReactNode;
  extra?: () => AddPlayerExtra;
  onProfile?: (profile: Profile | null) => void;
  /** Edit an existing sign-up instead of adding one. */
  edit?: EditTarget;
  /** Edit mode: called with the updated application (admin shape) and the player's name. */
  onSaved?: (app: unknown, name: string) => void;
  /** Edit mode: the "shared with other events" note. */
  sharedNote?: string;
  /** Checks run before saving (e.g. Tyrant power in millions). */
  validate?: () => ClientError | null;
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

export default function AddPlayerDialog({ event, roundId, onClose, onAdded, children, extra, onProfile, edit, onSaved, sharedNote, validate }: Props) {
  const { t } = useTranslation();
  const editing = !!edit;
  const [fid, setFid] = useState(edit?.fid ?? '');
  const [checkedFid, setCheckedFid] = useState('');
  const [known, setKnown] = useState<boolean | null>(null);
  const [name, setName] = useState(edit?.name ?? '');
  const [alliance, setAlliance] = useState(edit?.alliance ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [invalid, setInvalid] = useState<string | null>(null);
  const [inlineShown, setInlineShown] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const prefix = editing ? 'edit' : 'add';

  // focus the first field on open; Esc closes (focus then returns to the row button via the caller)
  useEffect(() => {
    dialogRef.current?.querySelector<HTMLInputElement>(editing ? '#edit-name' : '#add-fid')?.focus();
    const onKey = (e: KeyboardEvent) => {
      // an open menu inside the dialog (Tyrant roles) takes the first Esc
      if (e.key === 'Escape' && !dialogRef.current?.querySelector('[aria-expanded="true"]')) onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // after an error: is it shown under a field? (then the bottom alert would only repeat it) Focus that field.
  useLayoutEffect(() => {
    const root = dialogRef.current;
    if (!root || !error) {
      setInlineShown(false);
      return;
    }
    setInlineShown(!!root.querySelector('[data-field-error]'));
    root.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
  }, [error, invalid]);

  const fail = (field: string | null, message: string) => {
    setInvalid(field);
    setError(message);
  };

  const lookup = async () => {
    const clean = fid.trim();
    if (!FID_RE.test(clean)) return fail('fid', t(clean ? 'profile:fidDigitsOnly' : 'profile:fidRequired'));
    setBusy(true);
    fail(null, '');
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
    if (!editing && !FID_RE.test(clean)) return fail('fid', t(clean ? 'profile:fidDigitsOnly' : 'profile:fidRequired'));
    if (!name.trim()) return fail('profile.game_name', t('ministry:form.required'));
    const local = validate?.();
    if (local) return fail(local.field, local.message);
    setBusy(true);
    fail(null, '');
    const ex = extra?.() ?? {};
    const ally = alliance.trim().toUpperCase();
    try {
      if (edit) {
        const profile: Record<string, unknown> = { ...(ex.profile ?? {}) };
        if (name !== edit.name) profile.game_name = name.trim();
        if (alliance !== edit.alliance) profile.alliance = ally;
        const updated = await api.admin.updateApplication<unknown>(edit.appId, {
          ...(Object.keys(profile).length ? { profile } : {}),
          ...(ex.answers ? { answers: ex.answers } : {}),
        });
        onSaved?.(updated, name.trim());
      } else {
        await api.admin.addPlayer(roundId, {
          fid: clean,
          profile: { game_name: name.trim(), ...(ally ? { alliance: ally } : {}), ...(ex.profile ?? {}) },
          ...(ex.answers ? { answers: ex.answers } : {}),
        });
        onAdded?.(name.trim());
      }
    } catch (e) {
      const field = e instanceof ApiError ? (e.code === 'APPLICATION_EXISTS' ? 'fid' : e.field ?? null) : null;
      fail(field, errorText(t, e, editing ? 'admin:playerUpdateError' : 'admin:addPlayer.error'));
    } finally {
      setBusy(false);
    }
  };

  const status = editing || known == null || checkedFid !== fid.trim() ? null : known ? t('admin:addPlayer.known') : t('admin:addPlayer.newPlayer');
  const fieldErr = (f: string) => (invalid === f ? error : null);

  // Portal to <body>: a transformed/animated ancestor would otherwise make `fixed` relative to it (the overlay then
  // stops covering the page). items-start + my-auto centres short dialogs while a tall one (Tyrant) scrolls from its
  // top instead of being clipped above the viewport.
  return createPortal(
    <div className="fixed inset-0 bg-black/50 flex items-start justify-center p-2 sm:p-4 z-50 overflow-y-auto">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-player-title"
        data-testid={editing ? 'edit-player-dialog' : 'add-player-dialog'}
        data-event={event}
        className="bg-dark-card rounded-xl p-4 sm:p-6 max-w-2xl w-full my-auto border border-theme-border"
      >
        <div className="flex items-center justify-between gap-3 mb-2">
          <h3 id="add-player-title" className="text-2xl font-bold text-accent min-w-0 break-words">
            {editing ? t('admin:editPlayer') : t('admin:addPlayer.title')}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] text-theme-dim hover:text-theme-text"
            aria-label={t('common:close')}
            data-testid={`${prefix}-player-close`}
          >
            <X className="w-6 h-6" aria-hidden="true" />
          </button>
        </div>
        <p className="text-theme-dim text-sm mb-3">{editing ? t('admin:playerEdit.desc') : t('admin:addPlayer.desc')}</p>
        {editing && sharedNote && (
          <p className="mb-5 p-3 rounded-lg bg-accent/10 border border-accent/30 text-sm text-theme-text flex items-start gap-2" data-testid="edit-shared-note">
            <Info className="w-4 h-4 shrink-0 mt-0.5 text-accent" aria-hidden="true" />
            <span>{sharedNote}</span>
          </p>
        )}

        <DialogErrorContext.Provider value={{ field: invalid, message: error }}>
          <div className="space-y-4">
            {editing ? (
              <Field
                id="edit-fid"
                label={t('tyrant:fields.fid')}
                value={fid}
                readOnly
                aria-readonly="true"
                inputClassName="!bg-dark-bg border-dashed text-theme-dim cursor-default focus:ring-0"
                hint={t('admin:playerEdit.fidFixed')}
              />
            ) : (
              <div>
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
                    aria-describedby={fieldErr('fid') ? 'add-fid-error' : undefined}
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
                <InlineError id="add-fid-error" message={fieldErr('fid')} />
              </div>
            )}
            {status && (
              <p className="text-sm text-theme-dim -mt-2" data-testid="add-status" data-known={known ? 'true' : 'false'}>
                {status}
              </p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="sm:col-span-2">
                <Field
                  id={`${prefix}-name`}
                  label={t('tyrant:fields.ingameName')}
                  required
                  maxLength={64}
                  autoComplete="off"
                  value={name}
                  invalid={invalid === 'profile.game_name'}
                  aria-describedby={fieldErr('profile.game_name') ? `${prefix}-name-error` : undefined}
                  onChange={(e) => setName(e.target.value)}
                />
                <InlineError id={`${prefix}-name-error`} message={fieldErr('profile.game_name')} />
              </div>
              <div>
                <Field
                  id={`${prefix}-alliance`}
                  label={`${t('tyrant:fields.alliance')} (${t('profile:optional')})`}
                  maxLength={editing && edit && edit.alliance.length > 3 && alliance === edit.alliance ? edit.alliance.length : 3}
                  autoComplete="off"
                  inputClassName="uppercase"
                  placeholder={t('tyrant:fields.alliancePlaceholder')}
                  value={alliance}
                  invalid={invalid === 'profile.alliance'}
                  aria-describedby={fieldErr('profile.alliance') ? `${prefix}-alliance-error` : undefined}
                  onChange={(e) => setAlliance(e.target.value.toUpperCase().slice(0, 3))}
                />
                <InlineError id={`${prefix}-alliance-error`} message={fieldErr('profile.alliance')} />
              </div>
            </div>

            {children && (
              <div className="pt-4 border-t border-theme-border space-y-4" data-testid={`${prefix}-event-fields`}>
                {!editing && <p className="text-sm text-theme-dim">{t('admin:addPlayer.optionalHint')}</p>}
                {children}
              </div>
            )}

            {error && !inlineShown && (
              <div className="p-3 bg-danger/10 border border-danger/30 rounded-lg flex items-center gap-2 text-danger" role="alert" data-testid={`${prefix}-error`}>
                <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
                {error}
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={save}
                disabled={busy}
                data-testid={`${prefix}-save`}
                className="flex-1 flex items-center justify-center gap-2 min-h-[48px] px-4 py-3 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium disabled:opacity-50"
              >
                {editing ? <Save className="w-5 h-5" aria-hidden="true" /> : <UserPlus className="w-5 h-5" aria-hidden="true" />}
                {editing ? t('common:save') : t('admin:addPlayer.save')}
              </button>
              <button
                type="button"
                onClick={onClose}
                data-testid={`${prefix}-cancel`}
                className="flex-1 min-h-[48px] px-4 py-3 bg-dark-bg text-theme-text rounded-lg hover:bg-dark-card-hover font-medium border border-theme-border"
              >
                {t('common:cancel')}
              </button>
            </div>
          </div>
        </DialogErrorContext.Provider>
      </div>
    </div>,
    document.body,
  );
}
