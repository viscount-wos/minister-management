import { Clock } from 'lucide-react';
import { TIMEZONES, saveTimezone, timezoneOption } from './timezone';

interface TimezoneSelectorProps {
  value: string;
  onChange: (tz: string) => void;
  /** Accessible name for the select (screen readers only). */
  label?: string;
  /** id, so an external <label htmlFor> can name the select. */
  id?: string;
  testId?: string;
}

/** The <option>s: the short list, plus the current zone when it is not on it (detected / stored). */
export function TimezoneOptions({ value }: { value: string }) {
  const known = TIMEZONES.some((tz) => tz.id === value);
  const extra = !known && value ? timezoneOption(value) : null;
  return (
    <>
      {extra && (
        <option value={extra.id}>
          {extra.label}
          {extra.offset ? ` (UTC${extra.offset})` : ''}
        </option>
      )}
      {TIMEZONES.map((tz) => (
        <option key={tz.id} value={tz.id}>
          {tz.label} (UTC{tz.offset})
        </option>
      ))}
    </>
  );
}

export default function TimezoneSelector({ value, onChange, label, id, testId }: TimezoneSelectorProps) {
  const handleChange = (tz: string) => {
    saveTimezone(tz);
    onChange(tz);
  };

  return (
    <div className="flex items-center gap-2 min-w-0 max-w-full">
      <Clock className="w-4 h-4 text-theme-dim flex-shrink-0" aria-hidden="true" />
      <select
        id={id}
        data-testid={testId}
        value={value}
        aria-label={label}
        onChange={(e) => handleChange(e.target.value)}
        // 16px on phones (iOS zooms into smaller controls), 44px tall tap target.
        className="min-w-0 max-w-full min-h-[44px] px-3 py-2 bg-dark-input border border-theme-border rounded-lg text-theme-text text-base sm:text-sm focus:ring-2 focus:ring-accent focus:border-accent cursor-pointer"
      >
        <TimezoneOptions value={value} />
      </select>
    </div>
  );
}
