import type { MinistryAnswers, TimeSlotsByDay } from '../../shared/api';

// Ministry round-specific answers. In the form numbers are kept as text so an
// input can be cleared; they are converted on save.

export const DAY_TYPES = ['construction', 'research', 'troop'] as const;

export const SPEEDUP_FIELDS = [
  { key: 'construction_speedups_days', label: 'ministry:form.constructionSpeedups' },
  { key: 'research_speedups_days', label: 'ministry:form.researchSpeedups' },
  { key: 'troop_training_speedups_days', label: 'ministry:form.troopSpeedups' },
] as const;

export const CRYSTAL_FIELDS = [
  { key: 'fire_crystals', label: 'ministry:form.fireCrystals' },
  { key: 'refined_fire_crystals', label: 'ministry:form.refinedFireCrystals' },
  { key: 'fire_crystal_shards', label: 'ministry:form.fireCrystalShards' },
] as const;

type NumericKey = Exclude<keyof MinistryAnswers, 'time_slots_by_day'>;

export type AnswersForm = Record<NumericKey, string> & { time_slots_by_day: TimeSlotsByDay };

export const emptySlots = (): TimeSlotsByDay => ({ construction: [], research: [], troop: [] });

/** Blank answers for a new application in a round. */
export function blankAnswers(): AnswersForm {
  return {
    construction_speedups_days: '',
    research_speedups_days: '',
    troop_training_speedups_days: '',
    general_speedups_days: '',
    fire_crystals: '',
    refined_fire_crystals: '',
    fire_crystal_shards: '',
    time_slots_by_day: emptySlots(),
  };
}

const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? String(v) : '');

/** Stored answers (possibly partial / legacy) -> form values. */
export function answersToForm(a: Partial<MinistryAnswers> | null | undefined): AnswersForm {
  const by = a?.time_slots_by_day;
  return {
    construction_speedups_days: num(a?.construction_speedups_days),
    research_speedups_days: num(a?.research_speedups_days),
    troop_training_speedups_days: num(a?.troop_training_speedups_days),
    general_speedups_days: num(a?.general_speedups_days),
    fire_crystals: num(a?.fire_crystals),
    refined_fire_crystals: num(a?.refined_fire_crystals),
    fire_crystal_shards: num(a?.fire_crystal_shards),
    time_slots_by_day: {
      construction: [...(by?.construction ?? [])],
      research: [...(by?.research ?? [])],
      troop: [...(by?.troop ?? [])],
    },
  };
}

const toNumber = (v: string, integer = false) => {
  const n = integer ? parseInt(v, 10) : parseFloat(v);
  return Number.isFinite(n) && n >= 0 ? n : 0;
};

/** Form values -> the full answers object (the API replaces answers wholesale). */
export function formToAnswers(f: AnswersForm): MinistryAnswers {
  return {
    construction_speedups_days: toNumber(f.construction_speedups_days),
    research_speedups_days: toNumber(f.research_speedups_days),
    troop_training_speedups_days: toNumber(f.troop_training_speedups_days),
    general_speedups_days: toNumber(f.general_speedups_days),
    fire_crystals: toNumber(f.fire_crystals, true),
    refined_fire_crystals: toNumber(f.refined_fire_crystals, true),
    fire_crystal_shards: toNumber(f.fire_crystal_shards, true),
    time_slots_by_day: {
      construction: [...f.time_slots_by_day.construction].sort(),
      research: [...f.time_slots_by_day.research].sort(),
      troop: [...f.time_slots_by_day.troop].sort(),
    },
  };
}

export const totalSlots = (s: TimeSlotsByDay) => s.construction.length + s.research.length + s.troop.length;
