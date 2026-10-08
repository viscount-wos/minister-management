import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Save, RotateCcw, CheckCircle, AlertCircle } from 'lucide-react';
import { Round } from '../../../shared/api';
import { errorText } from '../../../shared/apiErrors';
import { isoToZonedInput, zonedInputToIso } from '../../../shared/datetime';
import { useFormatDateTime } from '../../../shared/DateTime';
import { useTimezone } from '../../../shared/TimezoneContext';
import { timezoneShortLabel } from '../../../shared/timezone';
import { SvsSettings, battleHours, hourEnd, svsApi } from '../api';

// SVS round settings: the battle window (start time UTC + duration in hours; players pick from its hours) and the
// closing time. Defaults 11:00 UTC for 5 hours (owner: "starts 11:00 UTC and lasts 5 hours", not 100% sure, so a
// setting). A new round copies them.

interface Props {
  round: Round<SvsSettings>;
  readOnly: boolean;
  onSaved: (r: Round<SvsSettings>) => void;
}

const input = 'min-h-[44px] px-3 py-2 text-base bg-dark-input border border-theme-border rounded-lg text-theme-text focus:ring-2 focus:ring-accent';

export default function SvsRoundSettings({ round, readOnly, onSaved }: Props) {
  const { t } = useTranslation();
  const { timezone } = useTimezone();
  const fmt = useFormatDateTime();
  const [start, setStart] = useState(round.settings.battle_start);
  const [duration, setDuration] = useState(String(round.settings.battle_hours));
  const [closing, setClosing] = useState(isoToZonedInput(round.closing_time, timezone));
  const [current, setCurrent] = useState(round);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => setClosing(isoToZonedInput(current.closing_time, timezone)), [timezone, current.closing_time]);

  const save = async (body: { settings?: Partial<SvsSettings>; closing_time?: string | null }) => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await svsApi.admin.updateRound(round.id, body);
      setCurrent(r);
      setStart(r.settings.battle_start);
      setDuration(String(r.settings.battle_hours));
      onSaved(r);
      setMsg({ ok: true, text: t('tyrant:admin.settings.saved') });
    } catch (e) {
      setMsg({ ok: false, text: errorText(t, e, 'svs:admin.settings.error') });
    } finally {
      setBusy(false);
    }
  };

  const n = Number(duration);
  const preview = /^\d{1,2}$/.test(duration) && n >= 1 && n <= 24 ? battleHours({ battle_start: start, battle_hours: n }) : [];

  return (
    <div className="space-y-6">
      <div className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-6" data-testid="battle-editor">
        <h3 className="text-xl font-semibold text-accent mb-1">{t('svs:admin.settings.battleTitle')}</h3>
        <p className="text-theme-dim text-sm mb-4">{t('svs:admin.settings.battleDesc')}</p>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="battle-start" className="block text-xs text-theme-dim mb-1">
              {t('svs:admin.settings.start')}
            </label>
            <input
              id="battle-start"
              data-testid="battle-start"
              type="time"
              step={60}
              dir="ltr"
              value={start}
              disabled={readOnly}
              onChange={(e) => setStart(e.target.value)}
              className={input}
            />
          </div>
          <div>
            <label htmlFor="battle-hours" className="block text-xs text-theme-dim mb-1">
              {t('svs:admin.settings.duration')}
            </label>
            <input
              id="battle-hours"
              data-testid="battle-hours"
              type="number"
              min={1}
              max={24}
              inputMode="numeric"
              value={duration}
              disabled={readOnly}
              onChange={(e) => setDuration(e.target.value)}
              className={`${input} w-28`}
            />
          </div>
          {!readOnly && (
            <>
              <button
                type="button"
                onClick={() => save({ settings: { battle_start: start, battle_hours: n } })}
                disabled={busy || preview.length === 0}
                data-testid="save-battle"
                className="flex items-center gap-2 min-h-[44px] px-4 py-2 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium disabled:opacity-50"
              >
                <Save className="w-4 h-4" aria-hidden="true" />
                {t('common:save')}
              </button>
              <button
                type="button"
                onClick={() => {
                  setStart('11:00');
                  setDuration('5');
                }}
                data-testid="battle-defaults"
                className="flex items-center gap-2 min-h-[44px] px-4 py-2 border border-theme-border rounded-lg text-theme-text hover:bg-dark-card-hover"
              >
                <RotateCcw className="w-4 h-4" aria-hidden="true" />
                {t('tyrant:admin.settings.resetDefaults')}
              </button>
            </>
          )}
        </div>
        <div className="mt-4">
          <p className="text-xs text-theme-dim mb-2">{t('svs:admin.settings.preview')}</p>
          <div className="flex flex-wrap gap-2" data-testid="battle-preview">
            {preview.map((h) => (
              <span key={h} className="px-2 py-1 rounded bg-accent/15 text-accent text-sm font-semibold" data-hour={h}>
                <bdi dir="ltr">
                  {h}–{hourEnd(h)}
                </bdi>
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-6" data-testid="closing-editor">
        <label htmlFor="closing-time" className="block text-xl font-semibold text-accent mb-1">
          {t('admin:closingTime')}
        </label>
        <p className="text-theme-dim text-sm mb-1">{t('admin:closingTimeDesc')}</p>
        <p className="text-theme-dim text-xs mb-4" data-testid="closing-time-zone">
          {t('admin:closingTimeZone', { zone: timezoneShortLabel(timezone) })}
        </p>
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
                onClick={() => save({ closing_time: zonedInputToIso(closing, timezone) })}
                disabled={busy || !closing}
                data-testid="save-closing-time"
                className="min-h-[44px] px-4 py-2 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium disabled:opacity-50"
              >
                {t('common:save')}
              </button>
              <button
                type="button"
                onClick={() => save({ closing_time: null })}
                disabled={busy}
                data-testid="clear-closing-time"
                className="min-h-[44px] px-4 py-2 border border-theme-border rounded-lg text-theme-text hover:bg-dark-card-hover"
              >
                {t('admin:clear')}
              </button>
            </>
          )}
        </div>
        <p className="mt-3 text-sm text-theme-dim" data-testid="closing-time-status">
          {current.closing_time ? `${t('admin:currentClosingTime')}: ${fmt(current.closing_time)}` : t('admin:noClosingTime')}
        </p>
      </div>

      {msg && (
        <div
          role={msg.ok ? 'status' : 'alert'}
          data-testid={msg.ok ? 'settings-saved' : 'settings-error'}
          className={`p-3 rounded-lg flex items-center gap-2 border ${msg.ok ? 'bg-success/10 border-success/30 text-success' : 'bg-danger/10 border-danger/30 text-danger'}`}
        >
          {msg.ok ? <CheckCircle className="w-4 h-4" aria-hidden="true" /> : <AlertCircle className="w-4 h-4" aria-hidden="true" />}
          {msg.text}
        </div>
      )}
    </div>
  );
}
