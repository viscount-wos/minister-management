// <input type="datetime-local"> works in the browser's local time; the API
// speaks ISO-8601 UTC. These convert between the two.

/** ISO UTC -> 'YYYY-MM-DDTHH:mm' in local time ('' for null). */
export function isoToLocalInput(iso: string | null | undefined): string {
  if (!iso) return '';
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return '';
  const local = new Date(dt.getTime() - dt.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

/** 'YYYY-MM-DDTHH:mm' local -> ISO UTC (null for ''). */
export function localInputToIso(value: string): string | null {
  if (!value) return null;
  const dt = new Date(value);
  return Number.isNaN(dt.getTime()) ? null : dt.toISOString();
}

export function formatDateTime(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleString() : '';
}
