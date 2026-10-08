import { ReactNode, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, CheckCircle, Pencil, Trash2, X } from 'lucide-react';

// Per-row Edit / Remove buttons, the Remove confirmation and the success toast for the SVS and Frost Dragon Tyrant
// player lists (v2.2.1). In a closed round both buttons stay visible but are aria-disabled with a tooltip (closed
// rounds are read-only on the server): aria-disabled rather than `disabled` keeps them focusable, so keyboard and
// screen-reader users also get the reason.

const BTN = 'inline-flex items-center justify-center min-w-[44px] min-h-[44px] p-2 rounded-lg';

export function PlayerRowActions({
  fid,
  name,
  readOnly,
  onEdit,
  onDelete,
  children,
}: {
  fid: string;
  name: string;
  readOnly: boolean;
  onEdit: (el: HTMLElement) => void;
  onDelete: (el: HTMLElement) => void;
  /** Extra buttons before Edit (SVS: Add to rally). */
  children?: ReactNode;
}) {
  const { t } = useTranslation();
  const closed = t('admin:playerEdit.closed');
  const off = 'opacity-40 cursor-not-allowed text-theme-dim';
  return (
    <div className="flex items-center gap-1 whitespace-nowrap">
      {children}
      <button
        type="button"
        onClick={(e) => !readOnly && onEdit(e.currentTarget)}
        data-testid={`edit-${fid}`}
        aria-label={t('admin:playerEdit.editLabel', { name })}
        aria-disabled={readOnly || undefined}
        aria-describedby={readOnly ? 'row-actions-closed' : undefined}
        title={readOnly ? closed : t('admin:playerEdit.editLabel', { name })}
        className={`${BTN} ${readOnly ? off : 'text-accent hover:bg-accent/10'}`}
      >
        <Pencil className="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        onClick={(e) => !readOnly && onDelete(e.currentTarget)}
        data-testid={`delete-${fid}`}
        aria-label={t('admin:playerEdit.deleteLabel', { name })}
        aria-disabled={readOnly || undefined}
        aria-describedby={readOnly ? 'row-actions-closed' : undefined}
        title={readOnly ? closed : t('admin:playerEdit.deleteLabel', { name })}
        className={`${BTN} ${readOnly ? off : 'text-danger hover:bg-danger/10'}`}
      >
        <Trash2 className="w-4 h-4" aria-hidden="true" />
      </button>
    </div>
  );
}

/** The one hidden description the disabled row buttons point at (render once per table). */
export function ClosedRoundNote({ show }: { show: boolean }) {
  const { t } = useTranslation();
  if (!show) return null;
  return (
    <span id="row-actions-closed" className="sr-only">
      {t('admin:playerEdit.closed')}
    </span>
  );
}

/** "Remove <name>?" with an optional battle-plan warning. Cancel has the focus (the safe choice); Esc cancels. */
export function DeletePlayerDialog({
  name,
  alliance,
  fid,
  planWarning,
  onConfirm,
  onClose,
}: {
  name: string;
  alliance?: string | null;
  fid: string;
  /** SVS: "They are Joiner 2 with Rally Caller 01 (Main); they will be removed from the battle plan too." */
  planWarning?: string | null;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    cancelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const go = async () => {
    setBusy(true);
    try {
      await onConfirm();
    } finally {
      setBusy(false);
    }
  };
  return createPortal(
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-3 sm:p-4 z-50">
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="delete-player-title"
        aria-describedby="delete-player-desc"
        data-testid="delete-dialog"
        className="bg-dark-card rounded-xl p-4 sm:p-6 max-w-md w-full border border-theme-border"
      >
        <div className="flex items-start justify-between gap-3 mb-2">
          <h3 id="delete-player-title" className="text-xl font-bold text-theme-text min-w-0 break-words">
            {t('admin:playerEdit.deleteTitle', { name })}
          </h3>
          <button type="button" onClick={onClose} aria-label={t('common:close')} className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] -m-2 text-theme-dim hover:text-theme-text">
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>
        <p className="text-sm text-theme-dim mb-1" data-testid="delete-who">
          {alliance ? `[${alliance}] ` : ''}
          <bdi>{name}</bdi> · <bdi dir="ltr">{fid}</bdi>
        </p>
        <p id="delete-player-desc" className="text-sm text-theme-text mb-4">
          {t('admin:playerEdit.deleteBody')}
        </p>
        {planWarning && (
          <p className="mb-4 p-3 rounded-lg bg-warning/10 border border-warning/40 text-warning text-sm flex items-start gap-2" data-testid="delete-plan-warning">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
            <span>{planWarning}</span>
          </p>
        )}
        <div className="flex gap-3">
          <button
            type="button"
            onClick={go}
            disabled={busy}
            data-testid="confirm-delete"
            className="flex-1 inline-flex items-center justify-center gap-2 min-h-[48px] px-4 py-3 bg-danger text-white rounded-lg hover:bg-danger-dark font-medium disabled:opacity-50"
          >
            <Trash2 className="w-4 h-4" aria-hidden="true" />
            {t('admin:playerEdit.deleteConfirm')}
          </button>
          <button
            ref={cancelRef}
            type="button"
            onClick={onClose}
            data-testid="cancel-delete"
            className="flex-1 min-h-[48px] px-4 py-3 bg-dark-bg text-theme-text rounded-lg hover:bg-dark-card-hover font-medium border border-theme-border"
          >
            {t('common:cancel')}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

/** A short success message pinned to the bottom of the screen (visible however far the table is scrolled). */
export function useToast(ms = 4000) {
  const [msg, setMsg] = useState('');
  const timer = useRef<number>();
  const show = (text: string) => {
    setMsg(text);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setMsg(''), ms);
  };
  useEffect(() => () => window.clearTimeout(timer.current), []);
  const node = msg
    ? createPortal(
        <div
          role="status"
          data-testid="admin-toast"
          className="fixed bottom-4 start-1/2 -translate-x-1/2 rtl:translate-x-1/2 z-[60] max-w-[calc(100vw-2rem)] px-4 py-3 rounded-lg bg-dark-card border border-success text-success shadow-2xl text-sm flex items-center gap-2"
        >
          <CheckCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
          <span>{msg}</span>
        </div>,
        document.body,
      )
    : null;
  return { show, node };
}
