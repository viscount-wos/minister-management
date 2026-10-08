import { Globe } from 'lucide-react';
import { TIMEZONES, saveTimezone } from './timezone';

interface TimezoneSelectorProps {
  value: string;
  onChange: (tz: string) => void;
  /** Accessible name for the select (screen readers only). */
  label?: string;
}

export default function TimezoneSelector({ value, onChange, label }: TimezoneSelectorProps) {
  const handleChange = (tz: string) => {
    saveTimezone(tz);
    onChange(tz);
  };

  return (
    <div className="flex items-center gap-2">
      <Globe className="w-4 h-4 text-theme-dim flex-shrink-0" aria-hidden="true" />
      <select
        value={value}
        aria-label={label}
        onChange={(e) => handleChange(e.target.value)}
        className="px-3 py-2 bg-dark-input border border-theme-border rounded-lg text-theme-text text-sm focus:ring-2 focus:ring-accent focus:border-accent cursor-pointer"
      >
        {TIMEZONES.map((tz) => (
          <option key={tz.id} value={tz.id}>
            {tz.label} (UTC{tz.offset})
          </option>
        ))}
      </select>
    </div>
  );
}
