import { ReactNode, useEffect, useState } from 'react';

// Admin dashboard building blocks shared by the Frost Dragon Tyrant and SVS players views: headline stat cards,
// clickable breakdown bars (each row toggles a filter) and a debounced number/date filter input.

const INPUT_SM =
  'w-full min-h-[44px] px-3 py-2 text-base bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim';

export function StatCard({ label, value, testId, sub }: { label: string; value: ReactNode; testId: string; sub?: ReactNode }) {
  return (
    <div className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-5 text-center" data-testid={testId}>
      <div className="text-3xl font-bold text-accent" data-testid={`${testId}-value`}>
        {value}
      </div>
      <div className="text-sm text-theme-dim mt-1">{label}</div>
      {sub && <div className="text-xs text-theme-dim mt-0.5">{sub}</div>}
    </div>
  );
}

/** Horizontal bar list: label + count, bar width relative to the shown total. Each row toggles a filter. */
export function Bars({
  title,
  rows,
  total,
  testId,
}: {
  title: string;
  rows: { key: string; label: ReactNode; n: number; active: boolean; onClick: () => void }[];
  total: number;
  testId: string;
}) {
  return (
    <div className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-5" data-testid={testId}>
      <h3 className="font-semibold text-accent mb-3">{title}</h3>
      <div className="space-y-1">
        {rows.map((r) => (
          <button
            key={r.key}
            type="button"
            onClick={r.onClick}
            aria-pressed={r.active}
            className={`w-full min-h-[44px] px-2 py-1 rounded-lg text-sm text-start border ${
              r.active ? 'border-accent bg-accent/15' : 'border-transparent hover:bg-dark-card-hover'
            }`}
            data-testid={`${testId}-${r.key}`}
            data-count={r.n}
            data-active={r.active ? 'true' : undefined}
          >
            <div className="flex justify-between gap-2 text-theme-text">
              <span>{r.label}</span>
              <span className="font-semibold">{r.n}</span>
            </div>
            <div className="h-1.5 rounded bg-dark-bg mt-1 overflow-hidden">
              <div className="h-full bg-accent" style={{ width: `${total ? Math.round((r.n / total) * 100) : 0}%` }} />
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

/** A number/date input that writes to the URL after a short pause (not on every keystroke). */
export function DebouncedInput({
  id,
  label,
  value,
  onCommit,
  type = 'number',
  inputMode,
}: {
  id: string;
  label: string;
  value: string;
  onCommit: (v: string) => void;
  type?: string;
  inputMode?: 'decimal' | 'numeric';
}) {
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);
  useEffect(() => {
    if (local === value) return;
    const h = setTimeout(() => onCommit(local), 400);
    return () => clearTimeout(h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [local]);
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-theme-text mb-2">
        {label}
      </label>
      <input
        id={id}
        data-testid={id}
        type={type}
        min={0}
        step="any"
        inputMode={inputMode}
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        className={INPUT_SM}
      />
    </div>
  );
}
