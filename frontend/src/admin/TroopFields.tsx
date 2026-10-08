import { useTranslation } from 'react-i18next';
import FurnaceLevelSelect from '../shared/FurnaceLevelSelect';
import { INPUT_CLASS } from '../shared/fields';
import { TROOP_TYPES, TroopType } from '../events/tyrant/api';
import { TroopIcon } from '../shared/heroes/HeroCard';
import { DialogErrorContext, InlineError, fieldMatches } from './dialogErrors';
import { useContext } from 'react';

// Compact per-troop camp level + tier editor for admin dialogs ("Add player" / "Edit player" in Frost Dragon Tyrant
// and SVS). Blank = not given (the shared-profile merge keeps what is stored). A validation error on
// profile.troops.<type>[.field] shows under that troop's card.

export type TroopValues = Record<TroopType, { furnace_level: string | null; tier: number | null }>;

export const blankTroopValues = (): TroopValues =>
  Object.fromEntries(TROOP_TYPES.map((k) => [k, { furnace_level: null, tier: null }])) as TroopValues;

/** Only the values that were filled in (what an admin create/edit sends). */
export function filledTroops(tr: TroopValues): Record<string, Record<string, unknown>> | undefined {
  const out: Record<string, Record<string, unknown>> = {};
  for (const k of TROOP_TYPES) {
    const e: Record<string, unknown> = {};
    if (tr[k].furnace_level) e.furnace_level = tr[k].furnace_level;
    if (tr[k].tier != null) e.tier = tr[k].tier;
    if (Object.keys(e).length) out[k] = e;
  }
  return Object.keys(out).length ? out : undefined;
}

/** Only what CHANGED against `before` (an edit): an untouched legacy value (e.g. a stored T9 SVS can't show) is
 * never re-sent, and a value cleared back to blank is not sent either (blank never clears, see the hint). */
export function changedTroops(tr: TroopValues, before: TroopValues): Record<string, Record<string, unknown>> | undefined {
  const out: Record<string, Record<string, unknown>> = {};
  for (const k of TROOP_TYPES) {
    const e: Record<string, unknown> = {};
    if (tr[k].furnace_level && tr[k].furnace_level !== before[k].furnace_level) e.furnace_level = tr[k].furnace_level;
    if (tr[k].tier != null && tr[k].tier !== before[k].tier) e.tier = tr[k].tier;
    if (Object.keys(e).length) out[k] = e;
  }
  return Object.keys(out).length ? out : undefined;
}

export default function TroopFields({
  value,
  onChange,
  tiers,
  idPrefix = 'add',
  hint,
}: {
  value: TroopValues;
  onChange: (v: TroopValues) => void;
  /** Tier choices, highest first (SVS: 11, 10; Tyrant: 11..8). */
  tiers: readonly number[];
  idPrefix?: string;
  /** Small note under the cards (edit: "a blank level keeps what is stored"). */
  hint?: string;
}) {
  const { t } = useTranslation();
  const err = useContext(DialogErrorContext);
  return (
    <div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-testid={`${idPrefix}-troops`}>
        {TROOP_TYPES.map((k) => {
          const base = `profile.troops.${k}`;
          const msg = fieldMatches(err.field, base) ? err.message : null;
          const campBad = !!msg && (err.field === base || err.field === 'profile.troops' || fieldMatches(err.field, `${base}.furnace_level`));
          const tierBad = !!msg && (err.field === base || err.field === 'profile.troops' || fieldMatches(err.field, `${base}.tier`));
          return (
            <div key={k} className={`bg-dark-bg p-3 rounded-lg border space-y-2 ${msg ? 'border-danger' : 'border-theme-border'}`} data-testid={`${idPrefix}-troop-${k}`}>
              <div className="font-semibold text-accent text-sm inline-flex items-center gap-1.5">
                <TroopIcon troop={k} className="w-4 h-4" />
                {t(`tyrant:step4.${k}`)}
              </div>
              <FurnaceLevelSelect
                id={`${idPrefix}-${k}-camp`}
                label={t('tyrant:admin.campRow')}
                fcOnly
                emptyLabel="—"
                invalid={campBad}
                value={value[k].furnace_level ?? ''}
                onChange={(code) => onChange({ ...value, [k]: { ...value[k], furnace_level: code || null } })}
              />
              <div>
                <label htmlFor={`${idPrefix}-${k}-tier`} className="block text-sm font-medium text-theme-text mb-2">
                  {t('tyrant:admin.tierRow')}
                </label>
                <select
                  id={`${idPrefix}-${k}-tier`}
                  data-testid={`${idPrefix}-${k}-tier`}
                  aria-invalid={tierBad || undefined}
                  aria-describedby={msg ? `${idPrefix}-${k}-error` : undefined}
                  value={value[k].tier != null && tiers.includes(value[k].tier!) ? String(value[k].tier) : ''}
                  onChange={(e) => onChange({ ...value, [k]: { ...value[k], tier: e.target.value ? Number(e.target.value) : null } })}
                  className={`${INPUT_CLASS} ${tierBad ? 'border-danger' : 'border-theme-border'}`}
                >
                  <option value="">—</option>
                  {tiers.map((n) => (
                    <option key={n} value={String(n)}>
                      T{n}
                    </option>
                  ))}
                </select>
              </div>
              <InlineError id={`${idPrefix}-${k}-error`} message={msg} />
            </div>
          );
        })}
      </div>
      {hint && <p className="text-xs text-theme-dim mt-2" data-testid={`${idPrefix}-troops-hint`}>{hint}</p>}
    </div>
  );
}
