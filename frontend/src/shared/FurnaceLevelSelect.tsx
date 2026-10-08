import { useTranslation } from 'react-i18next';
import { INPUT_CLASS } from './fields';
import { FC_LEVELS, PRE_FC_LEVELS } from './furnace';

// THE furnace level control, used everywhere a furnace level is chosen (ministry wizard, Tyrant stats and
// per-troop camp levels, admin filters). Always a dropdown: an empty choice, then FC10 ... FC1, then 30 ... 1.
// `fcOnly` (Frost Dragon Tyrant, owner rule p2d): FC10 ... FC1 only; a stored pre-FC value shows as unselected.

interface FurnaceLevelSelectProps {
  id: string;
  /** data-testid; defaults to the id. */
  testId?: string;
  label?: string;
  /** '' = no selection, else a code 'FC1'..'FC10' / '1'..'30'. */
  value: string;
  onChange: (code: string) => void;
  invalid?: boolean;
  disabled?: boolean;
  /** Text of the empty choice (default "Select..."). */
  emptyLabel?: string;
  className?: string;
  /** Offer Fire Crystal levels only (FC10..FC1); any other value is shown as no selection. */
  fcOnly?: boolean;
  /** Small help text under the select. */
  hint?: string;
  required?: boolean;
}

export function furnaceOptionLabel(code: string, t: (k: string, o?: Record<string, unknown>) => string): string {
  return code.startsWith('FC') ? code : t('common:furnace.level', { n: code });
}

export default function FurnaceLevelSelect({
  id,
  testId,
  label,
  value,
  onChange,
  invalid,
  disabled,
  emptyLabel,
  className,
  fcOnly,
  hint,
  required,
}: FurnaceLevelSelectProps) {
  const { t } = useTranslation();
  const shown = fcOnly && !FC_LEVELS.includes(value) ? '' : value;
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className={className}>
      {label && (
        <label htmlFor={id} className="block text-sm font-medium text-theme-text mb-2">
          {label}
        </label>
      )}
      <select
        id={id}
        data-testid={testId ?? id}
        value={shown}
        disabled={disabled}
        required={required}
        aria-invalid={invalid || undefined}
        aria-describedby={hintId}
        onChange={(e) => onChange(e.target.value)}
        className={`${INPUT_CLASS} ${invalid ? 'border-danger' : 'border-theme-border'}`}
      >
        <option value="">{emptyLabel ?? t('common:furnace.select')}</option>
        {fcOnly ? (
          FC_LEVELS.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))
        ) : (
          <>
            <optgroup label={t('common:furnace.fireCrystal')}>
              {FC_LEVELS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </optgroup>
            <optgroup label={t('common:furnace.preFc')}>
              {PRE_FC_LEVELS.map((c) => (
                <option key={c} value={c}>
                  {furnaceOptionLabel(c, t)}
                </option>
              ))}
            </optgroup>
          </>
        )}
      </select>
      {hint && (
        <p id={hintId} className="text-xs text-theme-dim mt-1" data-testid={`${testId ?? id}-hint`}>
          {hint}
        </p>
      )}
    </div>
  );
}
