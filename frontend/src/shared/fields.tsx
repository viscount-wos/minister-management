import { InputHTMLAttributes, ReactNode } from 'react';

// Form field building blocks. Every input gets an id and a <label htmlFor>,
// so tests (and screen readers) can find it by its label.

export const INPUT_CLASS =
  'w-full px-4 py-3 bg-dark-input border rounded-lg text-theme-text placeholder-theme-dim focus:ring-2 focus:ring-accent focus:border-accent';

interface FieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  id: string;
  label: ReactNode;
  /** data-testid on the <input>. Defaults to the id. */
  testId?: string;
  invalid?: boolean;
  hint?: ReactNode;
  className?: string;
  inputClassName?: string;
}

export function Field({ id, label, testId, invalid, hint, className, inputClassName, required, ...input }: FieldProps) {
  return (
    <div className={className}>
      <label htmlFor={id} className="block text-sm font-medium text-theme-text mb-2">
        {label}
        {required && <span aria-hidden="true"> *</span>}
      </label>
      <input
        id={id}
        data-testid={testId ?? id}
        aria-invalid={invalid || undefined}
        required={required}
        className={`${INPUT_CLASS} ${invalid ? 'border-danger' : 'border-theme-border'} ${inputClassName ?? ''}`}
        {...input}
      />
      {hint && <p className="text-xs text-theme-dim mt-1">{hint}</p>}
    </div>
  );
}

/** Parses a number input; blank or invalid -> 0 (as v1.4). */
export function parseNumber(value: string): number {
  const n = parseFloat(value);
  return Number.isFinite(n) && n >= 0 ? n : 0;
}
