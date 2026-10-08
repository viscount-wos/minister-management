import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Save, X, Check, ToggleLeft, ToggleRight, AlertCircle, Lock } from 'lucide-react';
import api, { MinistrySettings, Round } from '../../../shared/api';
import { errorText } from '../../../shared/apiErrors';
import { activeDaysInOrder } from '../../../shared/days';
import { isoToZonedInput, zonedInputToIso } from '../../../shared/datetime';
import { useFormatDateTime } from '../../../shared/DateTime';
import { useTimezone } from '../../../shared/TimezoneContext';
import { timezoneShortLabel } from '../../../shared/timezone';
import HeroGenerationSetting from '../../../admin/HeroGenerationSetting';

// Global settings (state number) plus the selected round's own settings:
// name, closing time, research day, fire crystals, slot scheme, published days.

interface AdminSettingsProps {
  round: Round | null;
  readOnly: boolean;
  onRoundUpdated: (r: Round) => void;
}

const CARD = 'bg-dark-card rounded-xl border border-theme-border p-6';

export default function AdminSettings({ round, readOnly, onRoundUpdated }: AdminSettingsProps) {
  const { t } = useTranslation();
  const { timezone } = useTimezone();
  const fmt = useFormatDateTime();
  const [stateNumber, setStateNumber] = useState('');
  const [closingLocal, setClosingLocal] = useState(isoToZonedInput(round?.closing_time, timezone));
  const [message, setMessage] = useState('');
  // The closing-time input is in the header's display timezone: follow it when it changes.
  useEffect(() => setClosingLocal(isoToZonedInput(round?.closing_time, timezone)), [timezone, round?.closing_time]);
  const [error, setError] = useState('');

  useEffect(() => {
    api.admin.settings()
      .then((s) => setStateNumber(s.state_number || ''))
      .catch(() => {});
  }, []);

  const saved = (text = t('admin:settingsSaved')) => {
    setError('');
    setMessage(text);
    setTimeout(() => setMessage(''), 3000);
  };
  const failed = (err: unknown) => {
    setMessage('');
    setError(errorText(t, err, 'admin:settingsError'));
  };

  const saveStateNumber = async () => {
    try {
      const res = await api.admin.updateSettings({ state_number: stateNumber.trim() });
      setStateNumber(res.state_number ?? '');
      saved();
    } catch (err) {
      failed(err);
    }
  };

  const updateRound = async (body: Parameters<typeof api.admin.updateRound>[1]) => {
    if (!round || readOnly) return;
    try {
      const res = await api.admin.updateRound(round.id, body);
      onRoundUpdated(res);
      setClosingLocal(isoToZonedInput(res.closing_time, timezone));
      saved(res.remapped !== undefined ? t('admin:round.remapped', { n: res.remapped }) : undefined);
    } catch (err) {
      failed(err);
    }
  };

  const setSetting = (patch: Partial<MinistrySettings>) => updateRound({ settings: patch });

  const togglePublished = async (day: string, publish: boolean) => {
    if (!round || readOnly) return;
    try {
      const res = publish
        ? await api.admin.ministry.publish(round.id, day)
        : await api.admin.ministry.unpublish(round.id, day);
      onRoundUpdated({ ...round, settings: { ...round.settings, published_days: res.published_days } });
      saved();
    } catch (err) {
      failed(err);
    }
  };

  const s = round?.settings;

  return (
    <div className="space-y-6" data-testid="settings-panel">
      {message && (
        <div className="bg-success/10 border border-success/30 rounded-lg p-3 flex items-center gap-2" role="status" data-testid="settings-saved">
          <Check className="w-5 h-5 text-success" aria-hidden="true" />
          <span className="text-success font-medium">{message}</span>
        </div>
      )}
      {error && (
        <div className="bg-danger/10 border border-danger/30 rounded-lg p-3 flex items-center gap-2" role="alert" data-testid="settings-error">
          <AlertCircle className="w-5 h-5 text-danger" aria-hidden="true" />
          <span className="text-danger font-medium">{error}</span>
        </div>
      )}

      {/* Global */}
      <div className={CARD}>
        <h3 className="text-xl font-bold text-accent mb-2">
          <label htmlFor="state-number">{t('admin:stateNumber')}</label>
        </h3>
        <p className="text-theme-dim text-sm mb-4">{t('admin:stateNumberDesc')}</p>
        <div className="flex gap-3 items-center">
          <input
            id="state-number"
            data-testid="state-number"
            type="text"
            value={stateNumber}
            onChange={(e) => setStateNumber(e.target.value)}
            placeholder={t('admin:stateNumberPlaceholder')}
            className="px-4 py-2 bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim focus:ring-2 focus:ring-accent focus:border-accent w-48"
          />
          <button
            onClick={saveStateNumber}
            data-testid="save-state-number"
            className="flex items-center gap-2 min-h-[44px] px-4 py-2 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors"
          >
            <Save className="w-4 h-4" aria-hidden="true" />
            {t('common:save')}
          </button>
        </div>
      </div>

      {/* Global: the state's hero generation (SVS planner / hero library) */}
      <HeroGenerationSetting />

      {round && s && (
        <>
          <div className="pt-2">
            <h2 className="text-2xl font-bold text-accent" data-testid="round-settings-title">
              {t('admin:round.settingsFor', { round: round.name })}
            </h2>
            <p className="text-theme-dim text-sm mt-1">{t('admin:round.settingsDesc')}</p>
            {readOnly && (
              <p className="mt-2 flex items-center gap-2 text-warning text-sm">
                <Lock className="w-4 h-4" aria-hidden="true" />
                {t('admin:round.readOnly')}
              </p>
            )}
          </div>

          {/* Closing time */}
          <div className={CARD}>
            <h3 className="text-xl font-bold text-accent mb-2">
              <label htmlFor="closing-time">{t('admin:closingTime')}</label>
            </h3>
            <p className="text-theme-dim text-sm mb-1">{t('admin:closingTimeDesc')}</p>
            <p className="text-theme-dim text-xs mb-4" data-testid="closing-time-zone">
              {t('admin:closingTimeZone', { zone: timezoneShortLabel(timezone) })}
            </p>
            <div className="flex flex-wrap gap-3 items-center">
              <input
                id="closing-time"
                data-testid="closing-time"
                type="datetime-local"
                value={closingLocal}
                disabled={readOnly}
                onChange={(e) => setClosingLocal(e.target.value)}
                className="px-4 py-2 bg-dark-input border border-theme-border rounded-lg text-theme-text focus:ring-2 focus:ring-accent focus:border-accent disabled:opacity-60"
              />
              {!readOnly && (
                <>
                  <button
                    onClick={() => updateRound({ closing_time: zonedInputToIso(closingLocal, timezone) })}
                    data-testid="save-closing-time"
                    className="flex items-center gap-2 min-h-[44px] px-4 py-2 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors"
                  >
                    <Save className="w-4 h-4" aria-hidden="true" />
                    {t('common:save')}
                  </button>
                  <button
                    onClick={() => updateRound({ closing_time: null })}
                    data-testid="clear-closing-time"
                    className="flex items-center gap-2 min-h-[44px] px-4 py-2 bg-danger/20 text-danger rounded-lg hover:bg-danger/30 font-medium transition-colors"
                  >
                    <X className="w-4 h-4" aria-hidden="true" />
                    {t('admin:clear')}
                  </button>
                </>
              )}
            </div>
            <div className="mt-3 text-sm" data-testid="closing-time-status">
              {round.closing_time ? (
                <p className={round.is_closed_for_new ? 'text-danger' : 'text-success'}>
                  {t('admin:currentClosingTime')}: {fmt(round.closing_time)}
                  {round.is_closed_for_new && <span className="ms-2 font-medium">({t('ministry:home.applicationsClosed')})</span>}
                </p>
              ) : (
                <p className="text-theme-dim italic">{t('admin:noClosingTime')}</p>
              )}
            </div>
          </div>

          {/* Research day */}
          <div className={CARD}>
            <h3 className="text-xl font-bold text-accent mb-2">{t('admin:researchDayToggle')}</h3>
            <p className="text-theme-dim text-sm mb-4">{t('admin:researchDayDesc')}</p>
            <button
              onClick={() => {
                // Workaround (docs/BACKEND_ISSUES.md #1): the API keeps the old research day in
                // published_days, so drop it when switching.
                const next = s.research_day === 'tuesday' ? 'friday' : 'tuesday';
                setSetting({ research_day: next, published_days: s.published_days.filter((d) => d !== s.research_day) });
              }}
              disabled={readOnly}
              data-testid="research-day-toggle"
              data-value={s.research_day}
              className="flex items-center gap-2 px-4 py-3 bg-dark-bg border border-theme-border rounded-lg hover:border-accent transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {s.research_day === 'tuesday' ? (
                <ToggleLeft className="w-7 h-7 text-accent" aria-hidden="true" />
              ) : (
                <ToggleRight className="w-7 h-7 text-accent" aria-hidden="true" />
              )}
              <span className="text-accent font-medium text-lg">{t(`admin:${s.research_day}`).split(' - ')[0]}</span>
            </button>
          </div>

          {/* Fire crystals */}
          <div className={CARD}>
            <h3 className="text-xl font-bold text-accent mb-2">{t('admin:showFireCrystals')}</h3>
            <p className="text-theme-dim text-sm mb-4">{t('admin:showFireCrystalsDesc')}</p>
            <label htmlFor="show-fire-crystals" className="flex items-center gap-3 cursor-pointer">
              <input
                id="show-fire-crystals"
                data-testid="show-fire-crystals"
                type="checkbox"
                checked={s.show_fire_crystals}
                disabled={readOnly}
                onChange={() => setSetting({ show_fire_crystals: !s.show_fire_crystals })}
                className="w-5 h-5 accent-accent"
              />
              <span className={`font-medium ${s.show_fire_crystals ? 'text-accent' : 'text-theme-dim'}`}>
                {s.show_fire_crystals ? t('admin:enabled') : t('admin:disabled')}
              </span>
            </label>
          </div>

          {/* Slot scheme */}
          <div className={CARD}>
            <h3 className="text-xl font-bold text-accent mb-2">{t('admin:timeSlotScheme')}</h3>
            <p className="text-theme-dim text-sm mb-4">{t('admin:timeSlotSchemeDesc')}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                { value: 'exact_alignment' as const, title: t('admin:schemeExact'), desc: t('admin:schemeExactDesc') },
                { value: 'max_slots' as const, title: t('admin:schemeMax'), desc: t('admin:schemeMaxDesc') },
              ].map((opt) => {
                const active = s.time_slot_scheme === opt.value;
                return (
                  <button
                    key={opt.value}
                    onClick={() => !active && setSetting({ time_slot_scheme: opt.value })}
                    disabled={readOnly}
                    aria-pressed={active}
                    data-testid={`scheme-${opt.value}`}
                    className={`text-start p-4 rounded-lg border transition-colors disabled:cursor-not-allowed ${
                      active ? 'border-accent bg-accent/10' : 'border-theme-border bg-dark-bg hover:border-accent/50'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      {active ? (
                        <ToggleRight className="w-6 h-6 text-accent" aria-hidden="true" />
                      ) : (
                        <ToggleLeft className="w-6 h-6 text-theme-dim" aria-hidden="true" />
                      )}
                      <span className={`font-semibold ${active ? 'text-accent' : 'text-theme-text'}`}>{opt.title}</span>
                    </div>
                    <p className="text-theme-dim text-xs leading-relaxed">{opt.desc}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Published days */}
          <div className={CARD}>
            <h3 className="text-xl font-bold text-accent mb-2">{t('admin:round.publishedDays')}</h3>
            <p className="text-theme-dim text-sm mb-4">{t('admin:round.publishedDaysDesc')}</p>
            <div className="flex flex-wrap gap-6">
              {activeDaysInOrder(s.research_day).map((day) => {
                const on = s.published_days.includes(day);
                return (
                  <label key={day} htmlFor={`publish-${day}`} className="flex items-center gap-3 cursor-pointer">
                    <input
                      id={`publish-${day}`}
                      data-testid={`publish-${day}`}
                      type="checkbox"
                      checked={on}
                      disabled={readOnly}
                      onChange={() => togglePublished(day, !on)}
                      className="w-5 h-5 accent-accent"
                    />
                    <span className={on ? 'text-accent font-medium' : 'text-theme-text'}>{t(`admin:${day}`)}</span>
                  </label>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
