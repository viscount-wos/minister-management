import { ReactNode, useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, Trash2, FileSpreadsheet, FileText, ChevronUp, ChevronDown, AlertCircle, SlidersHorizontal } from 'lucide-react';
import { Round, downloadBlob } from '../../../shared/api';
import { errorText } from '../../../shared/apiErrors';
import FurnaceLevelSelect from '../../../shared/FurnaceLevelSelect';
import { useUrlFilters, splitList, joinList } from '../../../shared/filters/useUrlFilters';
import { CheckboxMenu, ChipButton, FilterPill, FilterPills } from '../../../shared/filters/FilterControls';
import {
  FILTER_KEYS,
  FilterKey,
  FilterQuery,
  ROLES,
  SortKey,
  TROOP_TYPES,
  TroopType,
  TyrantAdminApplication,
  TyrantSettings,
  TyrantSummary,
  parseTroops,
  tyrantApi,
} from '../api';

// Tyrant admin Players tab: filter bar (state in the URL, shared hook), stats + clickable count chips for the
// FILTERED set, sortable table. Filters are documented in docs/API.md "Frost Dragon Tyrant".

const PAGE_SIZE = 50;
const SORT_KEYS: SortKey[] = ['submitted', 'updated', 'name', 'alliance', 'fid', 'power', 'gems', 'strength'];
const URL_KEYS = [...FILTER_KEYS, 'sort', 'dir'] as const;
type UrlKey = (typeof URL_KEYS)[number];
/** Keys shown in the "More filters" panel (the rest sit in the main row). */
const MORE_KEYS: FilterKey[] = ['min_power', 'max_power', 'min_gems', 'max_gems', 'vc', 'roles', 'roles_mode', 'submitted_from', 'submitted_to', 'days'];
const RUSH = '__rush';
const SELECT_CLASS = 'w-full min-h-[44px] px-3 py-2 text-base bg-dark-input border rounded-lg text-theme-text';
const INPUT_SM =
  'w-full min-h-[44px] px-3 py-2 text-base bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim';

interface Props {
  round: Round<TyrantSettings>;
  readOnly: boolean;
  onChanged: () => void;
}

function StatCard({ label, value, testId, sub }: { label: string; value: ReactNode; testId: string; sub?: ReactNode }) {
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
function Bars({
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
function DebouncedInput({
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

const Range = ({ start, end }: { start: string; end: string }) => (
  <bdi dir="ltr">
    {start}–{end}
  </bdi>
);

const millions = (abs: string | undefined) => (abs ? String(Math.round((Number(abs) / 1e6) * 100) / 100) : '');
const fromMillions = (m: string) => (m.trim() && Number.isFinite(Number(m)) && Number(m) >= 0 ? String(Math.round(Number(m) * 1e6)) : '');
const wholeOrBlank = (v: string) => (/^\d+$/.test(v.trim()) ? v.trim() : '');
const tierValue = (label: string) => (label === 'none' ? 'none' : label.replace(/^T/, ''));

export default function TyrantPlayers({ round, readOnly, onChanged }: Props) {
  const { t } = useTranslation();
  const F = useUrlFilters<UrlKey>(URL_KEYS);
  const v = F.values;
  const windows = round.settings.windows;
  const windowIds = useMemo(() => new Set(windows.map((w) => w.id)), [windows]);

  const [summary, setSummary] = useState<TyrantSummary | null>(null);
  const [apps, setApps] = useState<TyrantAdminApplication[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState(v.q ?? '');
  const [page, setPage] = useState(0);
  const [error, setError] = useState('');
  const moreActive = MORE_KEYS.filter((k) => v[k]).length;
  const [moreOpen, setMoreOpen] = useState(moreActive > 0);
  const sort: SortKey = SORT_KEYS.includes(v.sort as SortKey) ? (v.sort as SortKey) : 'submitted';
  const dir: 'asc' | 'desc' = v.dir === 'asc' ? 'asc' : 'desc';

  // the URL is the filter state; drop window ids this round doesn't have (a link from another round)
  const filters: FilterQuery = useMemo(() => {
    const f: FilterQuery = {};
    for (const k of FILTER_KEYS) if (v[k]) f[k] = v[k];
    if (f.windows) f.windows = joinList(splitList(f.windows).filter((w) => windowIds.has(w))) || undefined;
    return f;
  }, [v, windowIds]);
  const filtersKey = JSON.stringify(filters);
  const filtered = Object.values(filters).some(Boolean);

  // debounce the search box into the URL
  useEffect(() => setSearch(v.q ?? ''), [v.q]);
  useEffect(() => {
    if (search === (v.q ?? '')) return;
    const id = setTimeout(() => F.set({ q: search }), 250);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  useEffect(() => setPage(0), [filtersKey]);

  const load = useCallback(async () => {
    try {
      const [s, list] = await Promise.all([
        tyrantApi.admin.summary(round.id, filters),
        tyrantApi.admin.applications(round.id, { ...filters, sort, dir, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
      ]);
      setSummary(s);
      setApps(list.applications);
      setTotal(list.total);
      setError('');
    } catch (e) {
      setError(errorText(t, e, 'admin:fetchError'));
    }
    // filtersKey stands for filters
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [round.id, filtersKey, sort, dir, page, t]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleSort = (key: SortKey) => {
    if (sort === key) F.set({ dir: dir === 'asc' ? 'desc' : 'asc' });
    else F.set({ sort: key, dir: key === 'name' || key === 'alliance' || key === 'fid' ? 'asc' : 'desc' });
    setPage(0);
  };

  /** Toggle an exact single-value filter (the summary chips): the same value again removes it. */
  const toggleExact = (key: FilterKey, value: string) => F.set({ [key]: v[key] === value ? null : value });

  const remove = async (a: TyrantAdminApplication) => {
    if (!window.confirm(t('tyrant:admin.confirmDelete', { name: a.profile.game_name }))) return;
    try {
      await tyrantApi.admin.deleteApplication(a.id);
      onChanged();
      load();
    } catch (e) {
      setError(errorText(t, e, 'admin:deleteError'));
    }
  };

  const doExport = async (kind: 'csv' | 'xlsx') => {
    try {
      const blob = kind === 'csv' ? await tyrantApi.admin.exportCsv(round.id, filters) : await tyrantApi.admin.exportXlsx(round.id, filters);
      const slug = round.name.replace(/[^A-Za-z0-9]+/g, '_').toLowerCase() || 'round';
      downloadBlob(blob, `tyrant_${slug}${filtered ? '_filtered' : ''}.${kind}`);
    } catch (e) {
      setError(errorText(t, e, 'tyrant:admin.exportError'));
    }
  };

  // ------------------------------------------------------------ pills (every active filter, removable)
  const troopName = (k: string) => t(`tyrant:admin.troopName.${k}`);
  const daysLabel = (n: number) => (n === 1 ? t('tyrant:admin.filter.last24h') : t('tyrant:admin.pill.days', { n }));
  const windowLabel = (id: string) => {
    const w = windows.find((x) => x.id === id);
    return w ? `${w.start}–${w.end}` : id;
  };
  const pills: FilterPill[] = [];
  const pill = (id: string, text: string, onRemove: () => void) => pills.push({ id, text, label: text, onRemove });
  if (v.q) pill('q', t('tyrant:admin.pill.search', { v: v.q }), () => F.set({ q: null }));
  for (const a of splitList(v.alliance)) pill(`alliance-${a}`, t('tyrant:admin.pill.alliance', { v: a }), () => F.toggleInList('alliance', a));
  const troopScope = troopName(v.troop && v.troop !== 'all' ? v.troop : 'all');
  if (v.min_camp)
    pill('min_camp', t('tyrant:admin.pill.minCamp', { troop: troopScope, v: v.min_camp }), () => F.set({ min_camp: null, ...(v.min_tier ? {} : { troop: null }) }));
  if (v.min_tier)
    pill('min_tier', t('tyrant:admin.pill.minTier', { troop: troopScope, v: `T${v.min_tier}` }), () => F.set({ min_tier: null, ...(v.min_camp ? {} : { troop: null }) }));
  for (const k of TROOP_TYPES) {
    const camp = v[`${k}_camp` as FilterKey];
    if (camp) pill(`${k}_camp`, t('tyrant:admin.pill.camp', { troop: troopName(k), v: camp === 'none' ? t('tyrant:admin.none') : camp }), () => F.set({ [`${k}_camp`]: null }));
    const tier = v[`${k}_tier` as FilterKey];
    if (tier) pill(`${k}_tier`, t('tyrant:admin.pill.tier', { troop: troopName(k), v: tier === 'none' ? t('tyrant:admin.none') : `T${tier}` }), () => F.set({ [`${k}_tier`]: null }));
  }
  if (v.rush) pill('rush', t('tyrant:step2.openingRush'), () => F.set({ rush: null }));
  for (const w of splitList(filters.windows)) pill(`window-${w}`, t('tyrant:admin.pill.window', { v: windowLabel(w) }), () => F.toggleInList('windows', w));
  if (v.min_power) pill('min_power', t('tyrant:admin.pill.minPower', { v: millions(v.min_power) }), () => F.set({ min_power: null }));
  if (v.max_power) pill('max_power', t('tyrant:admin.pill.maxPower', { v: millions(v.max_power) }), () => F.set({ max_power: null }));
  if (v.min_gems) pill('min_gems', t('tyrant:admin.pill.minGems', { v: Number(v.min_gems).toLocaleString() }), () => F.set({ min_gems: null }));
  if (v.max_gems) pill('max_gems', t('tyrant:admin.pill.maxGems', { v: Number(v.max_gems).toLocaleString() }), () => F.set({ max_gems: null }));
  if (v.vc === 'yes' || v.vc === 'no') pill('vc', t(v.vc === 'yes' ? 'tyrant:admin.pill.vcYes' : 'tyrant:admin.pill.vcNo'), () => F.set({ vc: null }));
  for (const r of splitList(v.roles))
    pill(`role-${r}`, t(v.roles_mode === 'all' ? 'tyrant:admin.pill.roleAll' : 'tyrant:admin.pill.roleAny', { v: t(`tyrant:roles.${r}`) }), () => {
      const left = splitList(v.roles).filter((x) => x !== r);
      F.set({ roles: joinList(left), ...(left.length ? {} : { roles_mode: null }) });
    });
  if (v.submitted_from) pill('submitted_from', t('tyrant:admin.pill.from', { v: v.submitted_from }), () => F.set({ submitted_from: null }));
  if (v.submitted_to) pill('submitted_to', t('tyrant:admin.pill.to', { v: v.submitted_to }), () => F.set({ submitted_to: null }));
  if (v.days) pill('days', daysLabel(Number(v.days)), () => F.set({ days: null }));

  const clearAll = () => {
    setSearch('');
    F.clear(['sort', 'dir']);
  };

  const th = (key: SortKey | null, label: string) => (
    <th className="px-2 py-1 text-start font-semibold text-theme-dim whitespace-nowrap">
      {key ? (
        <button
          type="button"
          onClick={() => toggleSort(key)}
          data-testid={`sort-${key}`}
          data-active={sort === key ? dir : undefined}
          className="inline-flex items-center gap-1 min-h-[44px] px-1 hover:text-theme-text"
        >
          {label}
          {sort === key && (dir === 'asc' ? <ChevronUp className="w-4 h-4" aria-hidden="true" /> : <ChevronDown className="w-4 h-4" aria-hidden="true" />)}
        </button>
      ) : (
        label
      )}
    </th>
  );

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const tick = (on: boolean) => (on ? <span className="text-success font-bold">✓</span> : <span className="text-theme-dim">—</span>);
  const allianceSel = splitList(v.alliance);
  const windowSel = [...(v.rush ? [RUSH] : []), ...splitList(filters.windows)];
  const rolesSel = splitList(v.roles);
  const chosen = (n: number, none: string) => (n ? t('tyrant:admin.filter.selected', { n }) : none);

  return (
    <div className="space-y-6">
      {error && (
        <div className="p-3 bg-danger/10 border border-danger/30 rounded-lg flex items-center gap-2 text-danger" role="alert">
          <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
          {error}
        </div>
      )}

      {/* ---------------------------------------------------------------- filter bar */}
      <div className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-5 space-y-4" data-testid="tyrant-filters">
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 items-end">
          <div className="col-span-2 md:col-span-3 xl:col-span-2">
            <label htmlFor="tyrant-search" className="block text-sm font-medium text-theme-text mb-2">
              {t('tyrant:admin.filter.search')}
            </label>
            <div className="relative">
              <Search className="w-4 h-4 absolute top-1/2 -translate-y-1/2 start-3 text-theme-dim" aria-hidden="true" />
              <input
                id="tyrant-search"
                data-testid="tyrant-search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t('tyrant:admin.search')}
                className={`${INPUT_SM} ps-9`}
              />
            </div>
          </div>
          <CheckboxMenu
            id="alliance-filter"
            label={t('tyrant:admin.allianceFilter')}
            summary={allianceSel.length ? allianceSel.join(', ') : t('tyrant:admin.allAlliances')}
            options={(summary?.alliance_options ?? []).map((a) => ({ value: a, label: a }))}
            selected={allianceSel}
            onToggle={(a) => F.toggleInList('alliance', a)}
          />
          <CheckboxMenu
            id="windows-filter"
            label={t('tyrant:admin.filter.windows')}
            summary={chosen(windowSel.length, t('tyrant:admin.filter.anyWindow'))}
            options={[
              { value: RUSH, label: <b>{t('tyrant:step2.openingRush')}</b> },
              ...windows.map((w) => ({
                value: w.id,
                label: (
                  <>
                    <Range start={w.start} end={w.end} /> {w.rush ? `(${t('tyrant:step2.openingRush')})` : ''}
                  </>
                ),
              })),
            ]}
            selected={windowSel}
            onToggle={(id) => (id === RUSH ? F.set({ rush: v.rush ? null : '1' }) : F.toggleInList('windows', id))}
          />
          <div>
            <label htmlFor="filter-troop" className="block text-sm font-medium text-theme-text mb-2">
              {t('tyrant:admin.filter.troop')}
            </label>
            <select
              id="filter-troop"
              data-testid="filter-troop"
              value={v.troop && v.troop !== 'all' ? v.troop : ''}
              onChange={(e) => F.set({ troop: e.target.value || null })}
              className={`${SELECT_CLASS} ${v.troop && v.troop !== 'all' ? 'border-accent' : 'border-theme-border'}`}
            >
              <option value="">{troopName('all')}</option>
              {TROOP_TYPES.map((k) => (
                <option key={k} value={k}>
                  {troopName(k)}
                </option>
              ))}
            </select>
          </div>
          <FurnaceLevelSelect
            id="filter-min-camp"
            label={t('tyrant:admin.filter.campAtLeast')}
            emptyLabel={t('tyrant:admin.filter.anyCamp')}
            fcOnly
            value={v.min_camp ?? ''}
            onChange={(code) => F.set({ min_camp: code || null })}
          />
          <div>
            <label htmlFor="filter-min-tier" className="block text-sm font-medium text-theme-text mb-2">
              {t('tyrant:admin.filter.tier')}
            </label>
            <select
              id="filter-min-tier"
              data-testid="filter-min-tier"
              value={v.min_tier ?? ''}
              onChange={(e) => F.set({ min_tier: e.target.value || null })}
              className={`${SELECT_CLASS} ${v.min_tier ? 'border-accent' : 'border-theme-border'}`}
            >
              <option value="">{t('tyrant:admin.filter.anyTier')}</option>
              <option value="10">{t('tyrant:admin.filter.tier10')}</option>
              <option value="11">{t('tyrant:admin.filter.tier11')}</option>
            </select>
          </div>
          <button
            type="button"
            onClick={() => setMoreOpen((o) => !o)}
            aria-expanded={moreOpen}
            aria-controls="more-filters"
            data-testid="filter-more"
            className="inline-flex items-center justify-center gap-2 min-h-[44px] px-4 rounded-lg border border-theme-border text-theme-text hover:bg-dark-card-hover font-medium"
          >
            <SlidersHorizontal className="w-4 h-4" aria-hidden="true" />
            {moreOpen ? t('common:filters.fewer') : t('common:filters.more')}
            {moreActive > 0 && <span className="px-2 rounded-full bg-accent text-dark-bg text-xs font-bold">{moreActive}</span>}
          </button>
        </div>

        {moreOpen && (
          <div id="more-filters" data-testid="more-filters" className="grid grid-cols-2 md:grid-cols-4 gap-3 items-end pt-3 border-t border-theme-border">
            <div>
              <label htmlFor="filter-vc" className="block text-sm font-medium text-theme-text mb-2">
                {t('tyrant:admin.stats.discordVc')}
              </label>
              <select id="filter-vc" data-testid="filter-vc" value={v.vc ?? ''} onChange={(e) => F.set({ vc: e.target.value || null })} className={`${SELECT_CLASS} border-theme-border`}>
                <option value="">{t('tyrant:admin.filter.any')}</option>
                <option value="yes">{t('tyrant:admin.filter.yes')}</option>
                <option value="no">{t('tyrant:admin.filter.no')}</option>
              </select>
            </div>
            <DebouncedInput id="filter-min-power" label={t('tyrant:admin.filter.minPower')} inputMode="decimal" value={millions(v.min_power)} onCommit={(m) => F.set({ min_power: fromMillions(m) })} />
            <DebouncedInput id="filter-max-power" label={t('tyrant:admin.filter.maxPower')} inputMode="decimal" value={millions(v.max_power)} onCommit={(m) => F.set({ max_power: fromMillions(m) })} />
            <DebouncedInput id="filter-min-gems" label={t('tyrant:admin.filter.minGems')} inputMode="numeric" value={v.min_gems ?? ''} onCommit={(g) => F.set({ min_gems: wholeOrBlank(g) })} />
            <DebouncedInput id="filter-max-gems" label={t('tyrant:admin.filter.maxGems')} inputMode="numeric" value={v.max_gems ?? ''} onCommit={(g) => F.set({ max_gems: wholeOrBlank(g) })} />
            <CheckboxMenu
              id="roles-filter"
              label={t('tyrant:step5.title')}
              summary={chosen(rolesSel.length, t('tyrant:admin.filter.anyRole'))}
              options={ROLES.map((r) => ({ value: r, label: t(`tyrant:roles.${r}`) }))}
              selected={rolesSel}
              onToggle={(r) => F.toggleInList('roles', r)}
            />
            <div>
              <label htmlFor="filter-roles-mode" className="block text-sm font-medium text-theme-text mb-2">
                {t('tyrant:admin.filter.rolesMode')}
              </label>
              <select
                id="filter-roles-mode"
                data-testid="filter-roles-mode"
                value={v.roles_mode === 'all' ? 'all' : 'any'}
                onChange={(e) => F.set({ roles_mode: e.target.value === 'all' ? 'all' : null })}
                className={`${SELECT_CLASS} border-theme-border`}
              >
                <option value="any">{t('tyrant:admin.filter.rolesAny')}</option>
                <option value="all">{t('tyrant:admin.filter.rolesAll')}</option>
              </select>
            </div>
            <div>
              <label htmlFor="filter-days" className="block text-sm font-medium text-theme-text mb-2">
                {t('tyrant:admin.col.submitted')}
              </label>
              <select id="filter-days" data-testid="filter-days" value={v.days ?? ''} onChange={(e) => F.set({ days: e.target.value || null })} className={`${SELECT_CLASS} border-theme-border`}>
                <option value="">{t('tyrant:admin.filter.anyTime')}</option>
                {[1, 3, 7, 30].map((n) => (
                  <option key={n} value={String(n)}>
                    {daysLabel(n)}
                  </option>
                ))}
              </select>
            </div>
            <DebouncedInput id="filter-submitted-from" type="date" label={t('tyrant:admin.filter.from')} value={v.submitted_from ?? ''} onCommit={(d) => F.set({ submitted_from: d })} />
            <DebouncedInput id="filter-submitted-to" type="date" label={t('tyrant:admin.filter.to')} value={v.submitted_to ?? ''} onCommit={(d) => F.set({ submitted_to: d })} />
          </div>
        )}

        <FilterPills pills={pills} onClear={clearAll} />
      </div>

      {/* ---------------------------------------------------------------- stats (for the filtered set) */}
      {summary && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              testId="stat-total"
              label={t('tyrant:admin.stats.total')}
              value={summary.total}
              sub={filtered ? t('tyrant:admin.ofRound', { total: summary.round_total }) : undefined}
            />
            <StatCard testId="stat-opening-rush" label={t('tyrant:admin.stats.openingRush')} value={summary.opening_rush} />
            <StatCard testId="stat-discord-vc" label={t('tyrant:admin.stats.discordVc')} value={summary.discord_vc} />
            <StatCard testId="stat-alliances" label={t('tyrant:admin.stats.alliances')} value={summary.alliances.filter((a) => a.alliance).length} />
          </div>

          <div className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-5" data-testid="by-troop">
            <h3 className="font-semibold text-accent">{t('tyrant:admin.byTroop')}</h3>
            <p className="text-xs text-theme-dim mb-3">{t('tyrant:admin.chipHint')}</p>
            <div className="grid lg:grid-cols-3 gap-4">
              {TROOP_TYPES.map((k: TroopType) => (
                <div key={k} data-testid={`by-troop-${k}`} className="space-y-2">
                  <div className="text-theme-text font-semibold">{t(`tyrant:step4.${k}`)}</div>
                  <div className="text-xs text-theme-dim">{t('tyrant:admin.campRow')}</div>
                  <div className="flex flex-wrap gap-1.5" data-testid={`camp-chips-${k}`}>
                    {Object.entries(summary.camp_levels?.[k] ?? {}).map(([code, n]) => (
                      <ChipButton
                        key={code}
                        testId={`chip-${k}-camp-${code}`}
                        active={v[`${k}_camp` as FilterKey] === code}
                        onClick={() => toggleExact(`${k}_camp` as FilterKey, code)}
                      >
                        <bdi dir="ltr">{code === 'none' ? t('tyrant:admin.none') : code}</bdi>: <b data-testid="chip-count">{n}</b>
                      </ChipButton>
                    ))}
                  </div>
                  <div className="text-xs text-theme-dim">{t('tyrant:admin.tierRow')}</div>
                  <div className="flex flex-wrap gap-1.5" data-testid={`tier-chips-${k}`}>
                    {Object.entries(summary.troop_tiers[k] ?? {}).map(([tier, n]) => (
                      <ChipButton
                        key={tier}
                        testId={`chip-${k}-tier-${tier}`}
                        active={v[`${k}_tier` as FilterKey] === tierValue(tier)}
                        onClick={() => toggleExact(`${k}_tier` as FilterKey, tierValue(tier))}
                      >
                        <bdi dir="ltr">{tier === 'none' ? t('tyrant:admin.none') : tier}</bdi>: <b data-testid="chip-count">{n}</b>
                      </ChipButton>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

        </>
      )}

      {/* ---------------------------------------------------------------- table */}
      <div className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-3 mb-3">
          <p className="text-sm text-theme-dim flex-1" data-testid="result-count">
            {filtered && summary ? t('tyrant:admin.showingOf', { n: total, total: summary.round_total }) : t('tyrant:admin.showing', { n: total })}
          </p>
          <button
            type="button"
            onClick={() => doExport('csv')}
            data-testid="export-csv"
            className="flex items-center gap-2 min-h-[44px] px-4 py-2 bg-accent/20 text-accent rounded-lg hover:bg-accent/30 font-medium"
          >
            <FileText className="w-4 h-4" aria-hidden="true" />
            {t('tyrant:admin.exportCsv')}
          </button>
          <button
            type="button"
            onClick={() => doExport('xlsx')}
            data-testid="export-excel"
            className="flex items-center gap-2 min-h-[44px] px-4 py-2 bg-success text-white rounded-lg hover:bg-success-dark font-medium"
          >
            <FileSpreadsheet className="w-4 h-4" aria-hidden="true" />
            {t('tyrant:admin.exportExcel')}
          </button>
        </div>
        {filtered && (
          <p className="text-xs text-theme-dim mb-2" data-testid="export-filtered-note">
            {t('tyrant:admin.exportFiltered')}
          </p>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="tyrant-table">
            <thead className="border-b border-theme-border">
              <tr>
                {th('name', t('tyrant:fields.ingameName'))}
                {th('fid', t('admin:fid'))}
                {th('alliance', t('tyrant:fields.alliance'))}
                {th('strength', t('tyrant:admin.col.strength'))}
                {th('power', t('tyrant:admin.col.power'))}
                {th('gems', t('tyrant:admin.col.gems'))}
                {th(null, t('tyrant:admin.col.windows'))}
                {th(null, t('tyrant:admin.col.vc'))}
                {th(null, t('tyrant:fields.discordId'))}
                {th(null, t('tyrant:step5.title'))}
                {th('submitted', t('tyrant:admin.col.submitted'))}
                {!readOnly && th(null, t('admin:actions'))}
              </tr>
            </thead>
            <tbody>
              {apps.map((a) => {
                const troops = parseTroops(a.profile.troops);
                const avail = new Set(a.answers.availability ?? []);
                return (
                  <tr key={a.id} className="border-b border-theme-border/50 hover:bg-dark-card-hover align-top" data-testid={`player-row-${a.fid}`}>
                    <td className="px-2 py-2 font-medium text-theme-text min-w-[12rem]">
                      <bdi>{a.profile.game_name}</bdi>
                      {/* compact per-troop camp + tier summary, readable without scrolling sideways */}
                      <div className="text-xs font-normal text-theme-dim mt-0.5 leading-5" data-testid={`troop-summary-${a.fid}`}>
                        {TROOP_TYPES.map((k, i) => (
                          <span key={k} className="whitespace-nowrap">
                            {i > 0 && <span aria-hidden="true"> · </span>}
                            <span>{t(`tyrant:admin.troopShort.${k}`)}</span>{' '}
                            <bdi dir="ltr" className="text-theme-text">
                              {troops[k].furnace_level || '—'} {troops[k].tier ? `T${troops[k].tier}` : '—'}
                            </bdi>
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-2 py-2 text-theme-dim">{a.fid}</td>
                    <td className="px-2 py-2 text-accent font-semibold">{a.profile.alliance}</td>
                    <td className="px-2 py-2 text-theme-text font-semibold" data-testid="strength">
                      {a.joiner_strength ?? '—'}
                    </td>
                    <td className="px-2 py-2 text-theme-text">{a.profile.power != null ? `${Math.round(a.profile.power / 1e5) / 10}M` : '—'}</td>
                    <td className="px-2 py-2 text-theme-text">{a.answers.gem_spend != null ? a.answers.gem_spend.toLocaleString() : '—'}</td>
                    <td className="px-2 py-2">
                      <div className="flex flex-wrap gap-1 max-w-[9rem]">
                        {windows.map((w) => (
                          <span
                            key={w.id}
                            title={`${w.start}–${w.end}`}
                            className={`px-1.5 py-0.5 rounded text-xs ${avail.has(w.id) ? 'bg-success/20 text-success' : 'bg-dark-bg text-theme-dim'}`}
                          >
                            <bdi dir="ltr">{w.start}</bdi>
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-2 py-2">{tick(!!a.answers.discord_vc)}</td>
                    <td className="px-2 py-2 text-theme-text">
                      <bdi>{a.profile.discord_id || '—'}</bdi>
                    </td>
                    <td className="px-2 py-2 text-xs text-theme-text">{(a.answers.roles ?? []).map((r) => t(`tyrant:roles.${r}`)).join(', ') || '—'}</td>
                    <td className="px-2 py-2 text-xs text-theme-dim whitespace-nowrap">
                      {new Date(a.created_at).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}
                    </td>
                    {!readOnly && (
                      <td className="px-2 py-2">
                        <button
                          type="button"
                          onClick={() => remove(a)}
                          data-testid={`delete-${a.fid}`}
                          aria-label={t('admin:delete')}
                          className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] p-2 text-danger hover:bg-danger/10 rounded-lg"
                        >
                          <Trash2 className="w-4 h-4" aria-hidden="true" />
                        </button>
                      </td>
                    )}
                  </tr>
                );
              })}
              {apps.length === 0 && (
                <tr>
                  <td colSpan={13} className="px-3 py-10 text-center text-theme-dim" data-testid="no-players">
                    {filtered ? t('tyrant:admin.noMatches') : t('tyrant:admin.noPlayers')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {pages > 1 && (
          <div className="flex items-center justify-center gap-4 mt-4 text-sm" data-testid="pager">
            <button
              type="button"
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
              className="min-h-[44px] px-3 py-1 border border-theme-border rounded-lg text-theme-text disabled:opacity-40"
            >
              {t('tyrant:admin.prev')}
            </button>
            <span className="text-theme-dim">{t('tyrant:admin.page', { page: page + 1, pages })}</span>
            <button
              type="button"
              disabled={page + 1 >= pages}
              onClick={() => setPage((p) => p + 1)}
              className="min-h-[44px] px-3 py-1 border border-theme-border rounded-lg text-theme-text disabled:opacity-40"
            >
              {t('tyrant:admin.next')}
            </button>
          </div>
        )}
      </div>

      {/* breakdowns below the table (phones reach the players first); rows are filters too */}
      {summary && (
          <div className="grid md:grid-cols-3 gap-4">
          <Bars
            testId="by-window"
            title={t('tyrant:admin.byWindow')}
            total={summary.total}
            rows={summary.windows.map((w) => ({
              key: w.id,
              n: w.count,
              active: splitList(filters.windows).includes(w.id),
              onClick: () => F.toggleInList('windows', w.id),
              label: w.rush ? (
                <>
                  {t('tyrant:step2.openingRush')} <Range start={w.start} end={w.end} />
                </>
              ) : (
                <Range start={w.start} end={w.end} />
              ),
            }))}
          />
          <Bars
            testId="by-role"
            title={t('tyrant:admin.byRole')}
            total={summary.total}
            rows={ROLES.map((r) => ({
              key: r,
              n: summary.roles[r] ?? 0,
              label: t(`tyrant:roles.${r}`),
              active: rolesSel.includes(r),
              onClick: () => F.toggleInList('roles', r),
            }))}
          />
          <Bars
            testId="by-alliance"
            title={t('tyrant:admin.byAlliance')}
            total={summary.total}
            rows={summary.alliances.map((a) => ({
              key: a.alliance ?? 'none',
              n: a.count,
              label: a.alliance ?? t('tyrant:admin.none'),
              active: !!a.alliance && allianceSel.includes(a.alliance),
              onClick: () => {
                if (a.alliance) F.toggleInList('alliance', a.alliance);
              },
            }))}
          />
        </div>
      )}
    </div>
  );
}
