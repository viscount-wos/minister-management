import { Globe } from 'lucide-react';
import { TIMEZONES, saveTimezone } from './timezone';

interface TimezoneSelectorProps {
  value: string;
  onChange: (tz: string) => void;
  /** Accessible name for the select (screen readers only). */
  label?: string;
  /** id, so an external <label htmlFor> can name the select. */
  id?: string;
  testId?: string;
}

export default function TimezoneSelector({ value, onChange, label, id, testId }: TimezoneSelectorProps) {
  const handleChange = (tz: string) => {
    saveTimezone(tz);
    onChange(tz);
  };

  // A stored profile timezone outside the short list still shows and round-trips.
  const known = TIMEZONES.some((tz) => tz.id === value);

  return (
    <div className="flex items-center gap-2">
      <Globe className="w-4 h-4 text-theme-dim flex-shrink-0" aria-hidden="true" />
      <select
        id={id}
        data-testid={testId}
        value={value}
        aria-label={label}
        onChange={(e) => handleChange(e.target.value)}
        className="px-3 py-2 bg-dark-input border border-theme-border rounded-lg text-theme-text text-sm focus:ring-2 focus:ring-accent focus:border-accent cursor-pointer"
      >
        {!known && value && <option value={value}>{value}</option>}
        {TIMEZONES.map((tz) => (
          <option key={tz.id} value={tz.id}>
            {tz.label} (UTC{tz.offset})
          </option>
        ))}
      </select>
    </div>
  );
}
