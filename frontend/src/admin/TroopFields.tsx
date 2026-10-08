import { useTranslation } from 'react-i18next';
import FurnaceLevelSelect from '../shared/FurnaceLevelSelect';
import { INPUT_CLASS } from '../shared/fields';
import { TROOP_TYPES, TroopType } from '../events/tyrant/api';

// Compact per-troop camp level + tier editor for admin dialogs ("Add player" in Frost Dragon Tyrant and SVS).
// Blank = not given (the shared-profile merge keeps what is stored).

export type TroopValues = Record<TroopType, { furnace_level: string | null; tier: number | null }>;

export const blankTroopValues = (): TroopValues =>
  Object.fromEntries(TROOP_TYPES.map((k) => [k, { furnace_level: null, tier: null }])) as TroopValues;

/** Only the values that were filled in (what an admin create sends). */
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

export default function TroopFields({
  value,
  onChange,
  tiers,
  idPrefix = 'add',
}: {
  value: TroopValues;
  onChange: (v: TroopValues) => void;
  /** Tier choices, highest first (SVS: 11, 10; Tyrant: 11..8). */
  tiers: readonly number[];
  idPrefix?: string;
}) {
  const { t } = useTranslation();
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-testid={`${idPrefix}-troops`}>
      {TROOP_TYPES.map((k) => (
        <div key={k} className="bg-dark-bg p-3 rounded-lg border border-theme-border space-y-2">
          <div className="font-semibold text-accent text-sm">{t(`tyrant:step4.${k}`)}</div>
          <FurnaceLevelSelect
            id={`${idPrefix}-${k}-camp`}
            label={t('tyrant:admin.campRow')}
            fcOnly
            emptyLabel="—"
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
              value={value[k].tier != null && tiers.includes(value[k].tier!) ? String(value[k].tier) : ''}
              onChange={(e) => onChange({ ...value, [k]: { ...value[k], tier: e.target.value ? Number(e.target.value) : null } })}
              className={`${INPUT_CLASS} border-theme-border`}
            >
              <option value="">—</option>
              {tiers.map((n) => (
                <option key={n} value={String(n)}>
                  T{n}
                </option>
              ))}
            </select>
          </div>
        </div>
      ))}
    </div>
  );
}
