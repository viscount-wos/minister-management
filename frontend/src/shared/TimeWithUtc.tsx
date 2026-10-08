import { ReactNode } from 'react';
import { formatTimeInTimezone } from './timezone';

/**
 * A time chip's text: the local time, then "(HH:MM UTC)" when the zone isn't UTC. Each time value is a
 * left-to-right isolate (<bdi dir="ltr">) so Arabic (RTL) shows "20:00 (11:00 UTC)" in reading order instead of
 * the bidi-scrambled "(UTC 11:00) 20:00"; the local time comes first in reading order in both directions.
 */
export default function TimeWithUtc({ utc, timezone, extra }: { utc: string; timezone: string; extra?: ReactNode }) {
  return (
    <>
      <bdi dir="ltr" data-testid="time-local">
        {formatTimeInTimezone(utc, timezone)}
      </bdi>
      {extra}
      {timezone !== 'UTC' && (
        <span className="opacity-60 ms-1 text-xs">
          <bdi dir="ltr" data-testid="time-utc">
            ({utc} UTC)
          </bdi>
        </span>
      )}
    </>
  );
}
