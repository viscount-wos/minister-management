import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, Trash2, Save, RotateCcw, CheckCircle, AlertCircle } from 'lucide-react';
import { Round } from '../../../shared/api';
import { errorText } from '../../../shared/apiErrors';
import { formatDateTime, isoToLocalInput, localInputToIso } from '../../../shared/datetime';
import { TyrantSettings, TyrantWindow, tyrantApi } from '../api';

// Per-round settings: the availability windows (tyrantpoll's five by default) and the closing time.
const DEFAULT_WINDOWS: TyrantWindow[] = [
  { id: 'w1', start: '11:01', end: '11:15', rush: true },
  { id: 'w2', start: '11:15', end: '13:00', rush: false },
  { id: 'w3', start: '13:00', end: '15:00', rush: false },
  { id: 'w4', start: '15:00', end: '16:30', rush: false },
  { id: 'w5', start: '16:30', end: '18:00', rush: false },
];

interface Props {
  round: Round<TyrantSettings>;
  readOnly: boolean;
  onSaved: (r: Round<TyrantSettings>) => void;
}

const nextId = (ws: TyrantWindow[]) => {
  const nums = ws.map((w) => Number(/^w(\d+)$/.exec(w.id)?.[1] ?? 0));
  return `w${Math.max(0, ...nums) + 1}`;
};

export default function TyrantRoundSettings({ round, readOnly, onSaved }: Props) {
  const { t } = useTranslation();
  const [windows, setWindows] = useState<TyrantWindow[]>(round.settings.windows.map((w) => ({ ...w })));
  const [closing, setClosing] = useState(isoToLocalInput(round.closing_time));
  const [current, setCurrent] = useState(round);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const update = (i: number, patch: Partial<TyrantWindow>) =>
    setWindows((ws) => ws.map((w, j) => (j === i ? { ...w, ...patch } : w)));

  const save = async (body: { settings?: Partial<TyrantSettings>; closing_time?: string | null }) => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await tyrantApi.admin.updateRound(round.id, body);
      setCurrent(r);
      setWindows(r.settings.windows.map((w) => ({ ...w })));
      setClosing(isoToLocalInput(r.closing_time));
      onSaved(r);
      setMsg({ ok: true, text: t('tyrant:admin.settings.saved') });
    } catch (e) {
      setMsg({ ok: false, text: errorText(t, e, 'tyrant:admin.settings.error') });
    } finally {
      setBusy(false);
    }
  };

  const input = 'px-3 py-2 bg-dark-input border border-theme-border rounded-lg text-theme-text focus:ring-2 focus:ring-accent';

  return (
    <div className="space-y-6">
      <div className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-6" data-testid="windows-editor">
        <h3 className="text-xl font-semibold text-accent mb-1">{t('tyrant:admin.settings.windows')}</h3>
        <p className="text-theme-dim text-sm mb-4">{t('tyrant:admin.settings.windowsDesc')}</p>
        <div className="space-y-3">
          {windows.map((w, i) => (
            <div key={w.id} className="flex flex-wrap items-end gap-3" data-testid={`window-row-${i}`}>
              <div>
                <label htmlFor={`w-start-${i}`} className="block text-xs text-theme-dim mb-1">
                  {t('tyrant:admin.settings.start')}
                </label>
                <input
                  id={`w-start-${i}`}
                  data-testid={`window-start-${i}`}
                  type="time"
                  dir="ltr"
                  value={w.start}
                  disabled={readOnly}
                  onChange={(e) => update(i, { start: e.target.value })}
                  className={input}
                />
              </div>
              <div>
                <label htmlFor={`w-end-${i}`} className="block text-xs text-theme-dim mb-1">
                  {t('tyrant:admin.settings.end')}
                </label>
                <input
                  id={`w-end-${i}`}
                  data-testid={`window-end-${i}`}
                  type="time"
                  dir="ltr"
                  value={w.end}
                  disabled={readOnly}
                  onChange={(e) => update(i, { end: e.target.value })}
                  className={input}
                />
              </div>
              <label className="flex items-center gap-2 py-2 text-theme-text text-sm">
                <input
                  type="checkbox"
                  data-testid={`window-rush-${i}`}
                  checked={w.rush}
                  disabled={readOnly}
                  onChange={(e) => update(i, { rush: e.target.checked })}
                  className="w-4 h-4 accent-accent"
                />
                {t('tyrant:step2.openingRush')}
              </label>
              <button
                type="button"
                disabled={readOnly || windows.length <= 1}
                onClick={() => setWindows((ws) => ws.filter((_, j) => j !== i))}
                data-testid={`window-remove-${i}`}
                aria-label={t('tyrant:admin.settings.remove')}
                className="p-2 text-danger hover:bg-danger/10 rounded-lg disabled:opacity-40"
              >
                <Trash2 className="w-4 h-4" aria-hidden="true" />
              </button>
            </div>
          ))}
        </div>
        {!readOnly && (
          <div className="flex flex-wrap gap-3 mt-4">
            <button
              type="button"
              onClick={() => setWindows((ws) => [...ws, { id: nextId(ws), start: '18:00', end: '19:00', rush: false }])}
              disabled={windows.length >= 12}
              data-testid="window-add"
              className="flex items-center gap-2 px-4 py-2 border border-theme-border rounded-lg text-theme-text hover:bg-dark-card-hover disabled:opacity-40"
            >
              <Plus className="w-4 h-4" aria-hidden="true" />
              {t('tyrant:admin.settings.add')}
            </button>
            <button
              type="button"
              onClick={() => setWindows(DEFAULT_WINDOWS.map((w) => ({ ...w })))}
              data-testid="window-defaults"
              className="flex items-center gap-2 px-4 py-2 border border-theme-border rounded-lg text-theme-text hover:bg-dark-card-hover"
            >
              <RotateCcw className="w-4 h-4" aria-hidden="true" />
              {t('tyrant:admin.settings.resetDefaults')}
            </button>
            <button
              type="button"
              onClick={() => save({ settings: { windows } })}
              disabled={busy}
              data-testid="save-windows"
              className="flex items-center gap-2 px-4 py-2 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium disabled:opacity-50"
            >
              <Save className="w-4 h-4" aria-hidden="true" />
              {t('tyrant:admin.settings.save')}
            </button>
          </div>
        )}
      </div>

      <div className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-6" data-testid="closing-editor">
        <label htmlFor="closing-time" className="block text-xl font-semibold text-accent mb-1">
          {t('admin:closingTime')}
        </label>
        <p className="text-theme-dim text-sm mb-4">{t('admin:closingTimeDesc')}</p>
        <div className="flex flex-wrap gap-3">
          <input
            id="closing-time"
            data-testid="closing-time"
            type="datetime-local"
            value={closing}
            disabled={readOnly}
            onChange={(e) => setClosing(e.target.value)}
            className={input}
          />
          {!readOnly && (
            <>
              <button
                type="button"
                onClick={() => save({ closing_time: localInputToIso(closing) })}
                disabled={busy || !closing}
                data-testid="save-closing-time"
                className="px-4 py-2 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium disabled:opacity-50"
              >
                {t('common:save')}
              </button>
              <button
                type="button"
                onClick={() => save({ closing_time: null })}
                disabled={busy}
                data-testid="clear-closing-time"
                className="px-4 py-2 border border-theme-border rounded-lg text-theme-text hover:bg-dark-card-hover"
              >
                {t('admin:clear')}
              </button>
            </>
          )}
        </div>
        <p className="mt-3 text-sm text-theme-dim" data-testid="closing-time-status">
          {current.closing_time ? `${t('admin:currentClosingTime')}: ${formatDateTime(current.closing_time)}` : t('admin:noClosingTime')}
        </p>
      </div>

      {msg && (
        <div
          role={msg.ok ? 'status' : 'alert'}
          data-testid={msg.ok ? 'settings-saved' : 'settings-error'}
          className={`p-3 rounded-lg flex items-center gap-2 border ${
            msg.ok ? 'bg-success/10 border-success/30 text-success' : 'bg-danger/10 border-danger/30 text-danger'
          }`}
        >
          {msg.ok ? <CheckCircle className="w-4 h-4" aria-hidden="true" /> : <AlertCircle className="w-4 h-4" aria-hidden="true" />}
          {msg.text}
        </div>
      )}
    </div>
  );
}
