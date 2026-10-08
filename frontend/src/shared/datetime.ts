// Dates and times shown to players and admins. ONE rule everywhere: a moment
// (an ISO-8601 UTC timestamp from the API) is shown in the display timezone the
// user picked in the header, with the language's month/weekday names and no
// seconds, followed by the zone, e.g. "Sat 10 Oct, 15:06 (London)".
// Use <DateTime iso=... /> in components, or formatDateTime() for plain strings
// (e.g. inside a translated sentence).
//
// Game windows that the game itself defines in UTC (Tyrant windows, minister
// slots) keep their own clearly labelled "UTC" displays.

import { timezoneShortLabel } from './timezone';

/** Unicode first-strong isolate ... pop: the plain-string version of <bdi>, so a
 * left-to-right date never scrambles inside an Arabic (RTL) sentence. */
const FSI = '\u2068';
const PDI = '\u2069';

/** Intl locale for a UI language. English uses day-month order ("10 Oct"), never the
 * ambiguous US numeric form; Arabic keeps Latin digits like the rest of the app. */
export function dateLocale(lang: string): string {
  const base = (lang || 'en').split('-')[0];
  if (base === 'en') return 'en-GB';
  if (base === 'ar') return 'ar-u-nu-latn';
  return base;
}

function safeZone(tz: string | undefined): string {
  if (!tz) return 'UTC';
  try {
    new Intl.DateTimeFormat('en', { timeZone: tz });
    return tz;
  } catch {
    return 'UTC';
  }
}

export interface FormatOptions {
  /** IANA zone (the header's display timezone). */
  timezone: string;
  /** UI language code (i18n.language). */
  lang: string;
  /** Append " (London)" etc. Default true. */
  withZone?: boolean;
  /** Include the weekday. Default true. */
  weekday?: boolean;
  /** Wrap in Unicode isolates for use inside a sentence. Default true. */
  isolate?: boolean;
  /** Reference "now" (tests); the year is shown only when it differs from now's. */
  now?: Date;
}

/** "Sat 10 Oct, 15:06 (London)" in the given zone and language ('' for null/invalid). */
export function formatDateTime(iso: string | null | undefined, opts: FormatOptions): string {
  if (!iso) return '';
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return '';
  const timeZone = safeZone(opts.timezone);
  const locale = dateLocale(opts.lang);
  const yearOf = (d: Date) => new Intl.DateTimeFormat('en', { timeZone, year: 'numeric' }).format(d);
  const showYear = yearOf(dt) !== yearOf(opts.now ?? new Date());
  const date = new Intl.DateTimeFormat(locale, {
    timeZone,
    weekday: opts.weekday === false ? undefined : 'short',
    day: 'numeric',
    month: 'short',
    year: showYear ? 'numeric' : undefined,
  }).format(dt);
  const time = new Intl.DateTimeFormat(locale, {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(dt);
  const base = (opts.lang || 'en').split('-')[0];
  const sep = base === 'ar' ? '، ' : base === 'zh' || base === 'ko' ? ' ' : ', ';
  let text = `${date}${sep}${time}`;
  if (opts.withZone !== false) text += ` (${timezoneShortLabel(timeZone)})`;
  return opts.isolate === false ? text : `${FSI}${text}${PDI}`;
}

// ---------------------------------------------------------------- admin inputs
// <input type="datetime-local"> holds a wall-clock time with no zone. The admin
// screens read and write it in the SAME display timezone as everything else
// (not the device's), and the API speaks ISO-8601 UTC.

function zoneParts(ms: number, timeZone: string) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).formatToParts(new Date(ms));
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
  return { y: get('year'), mo: get('month'), d: get('day'), h: get('hour') % 24, mi: get('minute'), s: get('second') };
}

/** Offset of a zone at an instant, in ms (local wall clock minus UTC). */
function offsetMs(ms: number, timeZone: string): number {
  const p = zoneParts(ms, timeZone);
  return Date.UTC(p.y, p.mo - 1, p.d, p.h, p.mi, p.s) - Math.floor(ms / 1000) * 1000;
}

const pad = (n: number) => String(n).padStart(2, '0');

/** ISO UTC -> 'YYYY-MM-DDTHH:mm' wall clock in `timezone` ('' for null/invalid). */
export function isoToZonedInput(iso: string | null | undefined, timezone: string): string {
  if (!iso) return '';
  const ms = new Date(iso).getTime();
  if (Number.isNaN(ms)) return '';
  const p = zoneParts(ms, safeZone(timezone));
  return `${p.y}-${pad(p.mo)}-${pad(p.d)}T${pad(p.h)}:${pad(p.mi)}`;
}

/** 'YYYY-MM-DDTHH:mm' wall clock in `timezone` -> ISO UTC (null for ''/invalid). */
export function zonedInputToIso(value: string, timezone: string): string | null {
  const m = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!m) return null;
  const tz = safeZone(timezone);
  const wall = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]);
  // Two passes settle the offset across a DST change.
  let guess = wall - offsetMs(wall, tz);
  guess = wall - offsetMs(guess, tz);
  return new Date(guess).toISOString();
}
