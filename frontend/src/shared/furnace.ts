// Furnace levels (owner rule, docs/SPEC.md "Furnace levels"): pre-FC furnaces 1-30 and Fire Crystal
// furnaces FC1-FC10 (nothing above FC10). Stored everywhere as a string code 'FC1'..'FC10' or '1'..'30'.
// Order everywhere: FC10, FC9 ... FC1, then 30, 29 ... 1.

export const FC_LEVELS: string[] = Array.from({ length: 10 }, (_, i) => `FC${10 - i}`);
export const PRE_FC_LEVELS: string[] = Array.from({ length: 30 }, (_, i) => String(30 - i));
export const FURNACE_LEVELS: string[] = [...FC_LEVELS, ...PRE_FC_LEVELS];

export function isFurnaceCode(v: unknown): v is string {
  return typeof v === 'string' && FURNACE_LEVELS.includes(v);
}

/** Sort/compare key: '1' -> 1 ... '30' -> 30, 'FC1' -> 31 ... 'FC10' -> 40; anything else 0. */
export function furnaceOrdinal(code: string | null | undefined): number {
  if (!isFurnaceCode(code)) return 0;
  return code.startsWith('FC') ? 30 + Number(code.slice(2)) : Number(code);
}

/** Stored profile value -> form value ('' when blank or not a valid code). */
export function toFurnaceCode(v: unknown): string {
  return isFurnaceCode(v) ? v : '';
}
