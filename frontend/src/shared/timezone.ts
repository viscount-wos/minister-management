// Timezone utilities for the Ministry Management System
// All internal storage is UTC; display can be converted to any timezone.

export interface TimezoneOption {
  id: string;
  label: string;
  offset: string;
}

export const TIMEZONES: TimezoneOption[] = [
  { id: 'UTC', label: 'UTC', offset: '+0' },
  { id: 'Asia/Seoul', label: 'KST (Korea)', offset: '+9' },
  { id: 'Asia/Shanghai', label: 'CST (China)', offset: '+8' },
  { id: 'America/New_York', label: 'ET (US East)', offset: '-5/-4' },
  { id: 'America/Chicago', label: 'CT (US Central)', offset: '-6/-5' },
  { id: 'America/Los_Angeles', label: 'PT (US West)', offset: '-8/-7' },
  { id: 'Europe/Istanbul', label: 'TRT (Turkey)', offset: '+3' },
  { id: 'Asia/Riyadh', label: 'AST (Arabia)', offset: '+3' },
];

const TZ_STORAGE_KEY = 'preferred_timezone';

// Other names browsers report for zones in the list above.
const TZ_ALIASES: Record<string, string> = {
  'Etc/UTC': 'UTC',
  'Etc/GMT': 'UTC',
  'Etc/Universal': 'UTC',
  'Etc/Zulu': 'UTC',
  GMT: 'UTC',
  'Asia/Istanbul': 'Europe/Istanbul',
  Turkey: 'Europe/Istanbul',
  'Asia/Chongqing': 'Asia/Shanghai',
  'Asia/Harbin': 'Asia/Shanghai',
  PRC: 'Asia/Shanghai',
  ROK: 'Asia/Seoul',
  'US/Eastern': 'America/New_York',
  'US/Central': 'America/Chicago',
  'US/Pacific': 'America/Los_Angeles',
};

/** True when the browser knows this IANA zone. */
export function isValidTimezone(tz: string): boolean {
  try {
    new Intl.DateTimeFormat('en', { timeZone: tz });
    return true;
  } catch {
    return false;
  }
}

/**
 * The phone/browser's own timezone (Intl), mapped onto the list when it is one of
 * ours (or an alias), else the zone itself (the selectors add it as an extra
 * option), else UTC. Never IP / geolocation.
 */
export function detectTimezone(): string {
  let tz = '';
  try {
    tz = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
  } catch {
    tz = '';
  }
  tz = TZ_ALIASES[tz] ?? tz;
  if (!tz) return 'UTC';
  if (TIMEZONES.some((o) => o.id === tz)) return tz;
  return isValidTimezone(tz) ? tz : 'UTC';
}

/** Saved choice, else the detected timezone (not saved: only a choice is remembered). */
export function getSavedTimezone(): string {
  try {
    const saved = localStorage.getItem(TZ_STORAGE_KEY);
    if (saved && isValidTimezone(saved)) return saved;
  } catch {
    // localStorage not available
  }
  return detectTimezone();
}

/** Offset of a zone right now, e.g. "+1", "-4", "+5:30". */
export function currentOffset(tz: string, at: Date = new Date()): string {
  try {
    const part = new Intl.DateTimeFormat('en-US', { timeZone: tz, timeZoneName: 'shortOffset' })
      .formatToParts(at)
      .find((p) => p.type === 'timeZoneName')?.value;
    const m = part?.match(/GMT([+-]\d{1,2}(?::\d{2})?)?/);
    if (m) return m[1] ?? '+0';
  } catch {
    // older browsers: no shortOffset
  }
  return '';
}

/**
 * Option for any zone: one of the list, or a zone outside it (detected, or a
 * stored profile value) labelled by its city, e.g. "London (UTC+1)".
 */
export function timezoneOption(tz: string): TimezoneOption {
  const known = TIMEZONES.find((o) => o.id === tz);
  if (known) return known;
  const city = tz.split('/').pop()?.replace(/_/g, ' ') || tz;
  return { id: tz, label: city, offset: currentOffset(tz) };
}

/** Short tag for compact controls: "UTC", "KST", "ET", or the city for other zones. */
export function timezoneShortLabel(tz: string): string {
  const known = TIMEZONES.find((o) => o.id === tz);
  if (known) return known.label.split(' ')[0];
  return timezoneOption(tz).label;
}

export function saveTimezone(tz: string): void {
  try {
    localStorage.setItem(TZ_STORAGE_KEY, tz);
  } catch {
    // localStorage not available
  }
}

/**
 * Convert a UTC time string (HH:MM) to the given IANA timezone.
 * Handles slot IDs like "23:50+" by stripping the suffix.
 */
export function formatTimeInTimezone(utcHHMM: string, timezone: string): string {
  const clean = utcHHMM.replace('+', '');
  if (timezone === 'UTC') return clean;
  const [h, m] = clean.split(':').map(Number);
  // Use July 15 to be in summer (DST-aware for northern hemisphere)
  const date = new Date(Date.UTC(2024, 6, 15, h, m));
  return new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: timezone,
    hour12: false,
  }).format(date);
}

export type TimeSlotScheme = 'exact_alignment' | 'max_slots';

/**
 * Generate the assignment time slots for a scheme.
 *
 * 'exact_alignment' — 48 hour-aligned slots: 00:00, 00:30, ... 23:30.
 * 'max_slots'       — 49 slots starting at 23:50 UTC (previous day) through
 *                     23:50+ UTC (end of day): 23:50, 00:20, 00:50, ... 23:20, 23:50+.
 */
export function generateAssignmentSlots(scheme: TimeSlotScheme = 'exact_alignment'): string[] {
  if (scheme === 'exact_alignment') {
    const slots: string[] = [];
    let hour = 0;
    let minute = 0;
    for (let i = 0; i < 48; i++) {
      slots.push(`${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`);
      minute += 30;
      if (minute >= 60) {
        minute -= 60;
        hour += 1;
      }
    }
    return slots;
  }
  // max_slots
  const slots: string[] = ['23:50'];
  let hour = 0;
  let minute = 20;
  while (true) {
    const slot = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
    if (slot === '23:50') {
      slots.push('23:50+'); // End-of-day 23:50 slot (distinct from the pre-midnight one)
      break;
    }
    slots.push(slot);
    minute += 30;
    if (minute >= 60) {
      minute -= 60;
      hour += 1;
    }
  }
  return slots;
}

/**
 * Get display label for a slot ID, optionally converted to a timezone.
 * Handles "23:50+" by displaying as the same time but can add context.
 */
export function getSlotDisplayTime(slotId: string, timezone: string): string {
  return formatTimeInTimezone(slotId, timezone);
}

/**
 * Generate 24 hourly player-facing time slots.
 * Returns display time (in chosen timezone) paired with UTC value (for storage).
 * Kept in UTC order so switching timezones visually shifts the displayed times.
 */
export function generatePlayerTimeSlots(timezone: string): { display: string; utcValue: string }[] {
  const result: { display: string; utcValue: string }[] = [];
  for (let utcH = 0; utcH < 24; utcH++) {
    const utc = `${utcH.toString().padStart(2, '0')}:00`;
    const display = formatTimeInTimezone(utc, timezone);
    result.push({ display, utcValue: utc });
  }
  return result;
}

/**
 * Get the timezone abbreviation for display.
 */
export function getTimezoneAbbr(timezoneId: string): string {
  return timezoneShortLabel(timezoneId);
}
