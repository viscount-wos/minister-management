import { ReactNode, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { X, ChevronDown, Check } from 'lucide-react';

// Reusable admin filter UI pieces (phone-first: 44px targets). State lives in useUrlFilters.

export interface FilterPill {
  /** Stable id, also the test id suffix: filter-pill-<id>. */
  id: string;
  label: ReactNode;
  /** Plain text for the remove button's aria-label. */
  text: string;
  onRemove: () => void;
}

/** Active filters as removable pills, plus one "Clear filters" button. Renders nothing when no filter is active. */
export function FilterPills({ pills, onClear }: { pills: FilterPill[]; onClear: () => void }) {
  const { t } = useTranslation();
  if (pills.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="filter-pills" aria-live="polite">
      {pills.map((p) => (
        <button
          key={p.id}
          type="button"
          onClick={p.onRemove}
          data-testid={`filter-pill-${p.id}`}
          aria-label={t('common:filters.remove', { label: p.text })}
          className="inline-flex items-center gap-1.5 min-h-[44px] ps-3 pe-2 rounded-full bg-accent/20 border border-accent/50 text-accent text-sm font-medium hover:bg-accent/30"
        >
          <span>{p.label}</span>
          <X className="w-4 h-4 shrink-0" aria-hidden="true" />
        </button>
      ))}
      <button
        type="button"
        onClick={onClear}
        data-testid="clear-filters"
        className="min-h-[44px] px-3 rounded-full border border-theme-border text-theme-text text-sm font-medium hover:bg-dark-card-hover"
      >
        {t('common:filters.clear')}
      </button>
    </div>
  );
}

/** A count chip ("FC10: 3") that toggles a filter; highlighted (aria-pressed) while that filter is active. */
export function ChipButton({
  active,
  onClick,
  children,
  testId,
  title,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
  testId?: string;
  title?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      title={title}
      data-testid={testId}
      data-active={active ? 'true' : undefined}
      className={`inline-flex items-center gap-1 min-h-[44px] min-w-[44px] px-3 rounded-lg border text-sm transition-colors ${
        active
          ? 'bg-accent text-dark-bg border-accent font-semibold shadow'
          : 'bg-dark-bg border-theme-border text-theme-text hover:border-accent hover:bg-accent/10'
      }`}
    >
      {children}
    </button>
  );
}

/** A compact multi-select: a 44px button opening a checkbox list (closes on outside click / Escape). */
export function CheckboxMenu({
  id,
  label,
  summary,
  options,
  selected,
  onToggle,
  footer,
}: {
  id: string;
  label: string;
  /** Text on the button (e.g. "All alliances" or "2 selected"). */
  summary: ReactNode;
  options: { value: string; label: ReactNode }[];
  selected: string[];
  onToggle: (value: string) => void;
  footer?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent | TouchEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('touchstart', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('touchstart', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);
  return (
    <div className="relative" ref={ref}>
      <span id={`${id}-label`} className="block text-sm font-medium text-theme-text mb-2">
        {label}
      </span>
      <button
        type="button"
        id={id}
        data-testid={id}
        aria-haspopup="true"
        aria-expanded={open}
        aria-labelledby={`${id}-label ${id}`}
        onClick={() => setOpen((o) => !o)}
        className={`w-full min-h-[44px] px-4 py-2 text-base bg-dark-input border rounded-lg text-theme-text flex items-center justify-between gap-2 ${
          selected.length ? 'border-accent' : 'border-theme-border'
        }`}
      >
        <span className="truncate">{summary}</span>
        <ChevronDown className="w-4 h-4 shrink-0" aria-hidden="true" />
      </button>
      {open && (
        <div
          className="absolute z-30 mt-1 start-0 min-w-full w-max max-w-[calc(100vw-2rem)] max-h-80 overflow-auto bg-dark-card border border-theme-border rounded-lg shadow-xl p-1"
          data-testid={`${id}-menu`}
        >
          {options.map((o) => {
            const on = selected.includes(o.value);
            return (
              <button
                key={o.value}
                type="button"
                role="menuitemcheckbox"
                aria-checked={on}
                data-testid={`${id}-option-${o.value}`}
                onClick={() => onToggle(o.value)}
                className="w-full min-h-[44px] px-3 flex items-center gap-2 rounded-md text-start text-theme-text hover:bg-dark-card-hover"
              >
                <span
                  className={`w-5 h-5 shrink-0 rounded border flex items-center justify-center ${on ? 'bg-accent border-accent text-dark-bg' : 'border-theme-border'}`}
                  aria-hidden="true"
                >
                  {on && <Check className="w-4 h-4" />}
                </span>
                <span>{o.label}</span>
              </button>
            );
          })}
          {footer}
        </div>
      )}
    </div>
  );
}
