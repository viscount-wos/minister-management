import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

// Reusable admin filter state kept in the URL query (shareable, survives reload). Every value is a string;
// lists are comma-separated (helpers below). Only the given keys are read or written, so other params
// (e.g. the admin shell's ?event=) are left alone. Used by the Tyrant admin; meant for Minister / SVS too.

export type FilterValues<K extends string> = Partial<Record<K, string>>;

export interface UrlFilters<K extends string> {
  values: FilterValues<K>;
  /** Set (or with '' / null / undefined remove) one or more keys in one history entry. */
  set: (patch: Partial<Record<K, string | null | undefined>>) => void;
  /** Toggle one item in a comma-list key. */
  toggleInList: (key: K, item: string) => void;
  /** Remove every filter key (not the other params). */
  clear: (except?: K[]) => void;
  /** Number of active keys (minus `ignore`, e.g. sort keys). */
  activeCount: (ignore?: K[]) => number;
}

export const splitList = (v: string | undefined | null): string[] => (v ? v.split(',').filter(Boolean) : []);
export const joinList = (items: string[]): string => items.filter(Boolean).join(',');

export function useUrlFilters<K extends string>(keys: readonly K[]): UrlFilters<K> {
  const [params, setParams] = useSearchParams();

  const values = useMemo(() => {
    const out: FilterValues<K> = {};
    for (const k of keys) {
      const v = params.get(k);
      if (v != null && v !== '') out[k] = v;
    }
    return out;
    // keys is a module-level constant in practice
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  const set = useCallback(
    (patch: Partial<Record<K, string | null | undefined>>) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [k, v] of Object.entries(patch) as [K, string | null | undefined][]) {
            if (v == null || v === '') next.delete(k);
            else next.set(k, v);
          }
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  const toggleInList = useCallback(
    (key: K, item: string) => {
      const list = splitList(values[key]);
      set({ [key]: joinList(list.includes(item) ? list.filter((x) => x !== item) : [...list, item]) } as Partial<Record<K, string>>);
    },
    [values, set],
  );

  const clear = useCallback(
    (except: K[] = []) => {
      const patch: Partial<Record<K, null>> = {};
      for (const k of keys) if (!except.includes(k)) patch[k] = null;
      set(patch);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [set],
  );

  const activeCount = useCallback(
    (ignore: K[] = []) => (Object.keys(values) as K[]).filter((k) => !ignore.includes(k)).length,
    [values],
  );

  return { values, set, toggleInList, clear, activeCount };
}
