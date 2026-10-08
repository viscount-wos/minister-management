import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { DayType, Heatmap, TimeSlotsByDay } from '../../shared/api';
import TimezoneSelector from '../../shared/TimezoneSelector';
import { generatePlayerTimeSlots, getTimezoneAbbr } from '../../shared/timezone';
import { DAY_TYPES } from './answers';

// Hourly time-preference picker with one tab per ministry day type and the
// demand heat map. Values are stored as UTC "HH:00"; display follows the
// chosen timezone. Used by the player form and the admin edit dialog.

interface TimeSlotPickerProps {
  value: TimeSlotsByDay;
  onChange: (next: TimeSlotsByDay) => void;
  researchDay: string;
  timezone: string;
  onTimezoneChange: (tz: string) => void;
  heatmap?: Heatmap;
  compact?: boolean;
  disabled?: boolean;
}

export function useDayTypeLabel() {
  const { t } = useTranslation();
  return (dayType: string, researchDay: string) => {
    const researchDayName = t(`ministry:form.${researchDay === 'friday' ? 'fridayName' : 'tuesdayName'}`);
    return t(`ministry:form.${dayType}Times`, dayType === 'research' ? { day: researchDayName } : {});
  };
}

export default function TimeSlotPicker({
  value,
  onChange,
  researchDay,
  timezone,
  onTimezoneChange,
  heatmap = {},
  compact,
  disabled,
}: TimeSlotPickerProps) {
  const { t } = useTranslation();
  const dayTypeLabel = useDayTypeLabel();
  const [active, setActive] = useState<DayType>('construction');
  const slots = value[active] ?? [];
  const options = generatePlayerTimeSlots(timezone);

  const toggle = (utc: string) => {
    if (disabled) return;
    const cur = value[active] ?? [];
    onChange({ ...value, [active]: cur.includes(utc) ? cur.filter((s) => s !== utc) : [...cur, utc] });
  };

  const dayHeat = heatmap[active] || {};
  const counts = Object.values(dayHeat);
  const maxCount = counts.length > 0 ? Math.max(...counts) : 0;
  const heatClasses = (utc: string) => {
    const count = dayHeat[utc] || 0;
    if (count === 0 || maxCount === 0) return '';
    const ratio = count / maxCount;
    if (ratio <= 0.33) return 'bg-heat-low/25 border-heat-low/60';
    if (ratio <= 0.66) return 'bg-heat-mid/30 border-heat-mid/70';
    return 'bg-heat-high/30 border-heat-high/70';
  };

  return (
    <div data-testid="time-slot-picker">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        {!compact && <p className="text-sm text-accent font-medium">{t('ministry:form.selectAllAvailable')}</p>}
        <TimezoneSelector value={timezone} onChange={onTimezoneChange} label={t('common:header.timezone')} />
      </div>

      <div className="flex flex-wrap gap-2 mb-4 border-b border-theme-border" role="tablist">
        {DAY_TYPES.map((dayType) => {
          const n = value[dayType]?.length ?? 0;
          return (
            <button
              key={dayType}
              type="button"
              role="tab"
              aria-selected={active === dayType}
              data-testid={`day-tab-${dayType}`}
              onClick={() => setActive(dayType)}
              className={`px-4 py-3 font-medium transition-colors border-b-2 ${
                active === dayType ? 'border-accent text-accent' : 'border-transparent text-theme-dim hover:text-theme-text'
              } ${compact ? 'text-sm px-3 py-2' : ''}`}
            >
              {dayTypeLabel(dayType, researchDay)}
              {n > 0 && <span className="ms-2 px-2 py-0.5 text-xs rounded-full bg-accent/20 text-accent">{n}</span>}
            </button>
          );
        })}
      </div>

      <div className={`grid gap-3 ${compact ? 'grid-cols-6' : 'grid-cols-4 sm:grid-cols-6 md:grid-cols-8'}`}>
        {options.map(({ display, utcValue }) => {
          const selected = slots.includes(utcValue);
          const count = dayHeat[utcValue] || 0;
          const heat = selected ? '' : heatClasses(utcValue);
          return (
            <button
              key={utcValue}
              type="button"
              aria-pressed={selected}
              disabled={disabled}
              data-testid={`slot-${active}-${utcValue}`}
              onClick={() => toggle(utcValue)}
              className={`${compact ? 'p-2 text-sm' : 'p-3'} rounded-lg border-2 transition-all font-medium relative disabled:cursor-not-allowed ${
                selected
                  ? 'bg-accent border-accent text-dark-bg'
                  : heat
                    ? `text-theme-text hover:border-accent ${heat}`
                    : 'bg-dark-input border-theme-border text-theme-text hover:border-accent'
              }`}
              title={count > 0 ? t('ministry:form.applicantCount', { n: count }) : undefined}
            >
              {display}
              {timezone !== 'UTC' && (
                <span className={`block text-xs mt-0.5 ${selected ? 'opacity-70' : 'opacity-50'}`}>{utcValue} UTC</span>
              )}
              {selected && count > 0 && (
                <span className="absolute top-0.5 end-1 text-[10px] font-bold opacity-70">{count}</span>
              )}
            </button>
          );
        })}
      </div>
      {maxCount > 0 && <p className="text-xs text-theme-dim mt-2 text-center italic">{t('ministry:form.heatmapLegend')}</p>}
      <p className="text-sm text-theme-dim mt-4 text-center" data-testid="selected-count">
        {t('ministry:form.selectedSlots', { count: slots.length })}
        {timezone !== 'UTC' && (
          <span className="ms-2 text-accent">
            ({t('ministry:form.timesShownIn')} {getTimezoneAbbr(timezone)})
          </span>
        )}
      </p>
      {!compact && (
        <div className="mt-3 p-3 bg-accent/10 border border-accent/30 rounded-lg">
          <p className="text-sm text-accent text-center">
            <strong>⏱ </strong>
            {t('ministry:form.timeToleranceNote')}
          </p>
        </div>
      )}
    </div>
  );
}
