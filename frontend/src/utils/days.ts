// Weekday ordering for the SVS schedule.
//
// The active ministry days are Monday (construction), Thursday (troop
// training), and a research day that admins set to either Tuesday or Friday.
// Sorting day names alphabetically puts Thursday before Tuesday, so anything
// that lists days orders them through here instead.

export const WEEKDAY_ORDER = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
] as const;

/** Position in the week, with unrecognised names sorting last. */
function weekIndex(day: string): number {
  const i = WEEKDAY_ORDER.indexOf(day.toLowerCase() as typeof WEEKDAY_ORDER[number]);
  return i === -1 ? WEEKDAY_ORDER.length : i;
}

/** Calendar order, Monday first. Does not mutate the input. */
export function sortDaysByWeek<T extends string>(days: readonly T[]): T[] {
  return [...days].sort((a, b) => weekIndex(a) - weekIndex(b));
}

/**
 * The three active ministry days in calendar order, following the research-day
 * setting: Mon/Tue/Thu when research is Tuesday, Mon/Thu/Fri when it is Friday.
 */
export function activeDaysInOrder(researchDay: string): string[] {
  return sortDaysByWeek(['monday', researchDay, 'thursday']);
}
