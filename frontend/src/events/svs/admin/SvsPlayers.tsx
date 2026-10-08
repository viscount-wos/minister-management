import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, FileSpreadsheet, FileText, ChevronUp, ChevronDown, AlertCircle, SlidersHorizontal, CheckCircle, UserPlus, X } from 'lucide-react';
import { Round, downloadBlob } from '../../../shared/api';
import { errorText } from '../../../shared/apiErrors';
import { useFormatDateTime } from '../../../shared/DateTime';
import FurnaceLevelSelect from '../../../shared/FurnaceLevelSelect';
import { useUrlFilters, splitList } from '../../../shared/filters/useUrlFilters';
import { CheckboxMenu, ChipButton, FilterPill, FilterPills } from '../../../shared/filters/FilterControls';
import { Bars, DebouncedInput, StatCard } from '../../../shared/filters/Breakdowns';
import AddPlayerDialog, { AddPlayerButton } from '../../../admin/AddPlayerDialog';
import TroopFields, { TroopValues, blankTroopValues, changedTroops, filledTroops } from '../../../admin/TroopFields';
import { InlineError, useDialogError } from '../../../admin/dialogErrors';
import { ClosedRoundNote, DeletePlayerDialog, PlayerRowActions, useToast } from '../../../admin/PlayerRowActions';
import {
  FILTER_KEYS,
  FilterKey,
  FilterQuery,
  SVS_TIERS,
  SortKey,
  SvsAdminApplication,
  SvsSettings,
  SvsSummary,
  TROOP_TYPES,
  TroopType,
  battleHours,
  parseTroops,
  svsApi,
  svsTroops,
} from '../api';
import { TroopIcon } from '../../../shared/heroes/HeroCard';
import { planApi } from '../plan/api';
import { leaderLabel, groupLabel, makePlayerName, placementShort } from '../plan/labels';
import { normalizeDoc, placements } from '../plan/model';
import type { Person, Placement, PlanDoc } from '../plan/model';
import AddToRally, { type RallyPlayer } from './AddToRally';

// SVS admin Players tab (modelled on Frost Dragon Tyrant's, owner's dashboard order): headline stats -> breakdown
// bars (players per hour, alliances; clickable filters) -> troop camp/tier chips -> filter bar -> table.
// Filter state lives in the URL with the API's keys (docs/API.md "SVS"); exports follow the filters.

const PAGE_SIZE = 50;
const SORT_KEYS: SortKey[] = ['submitted', 'updated', 'name', 'alliance', 'fid', 'strength', 'hours'];
const URL_KEYS = [...FILTER_KEYS, 'sort', 'dir'] as const;
type UrlKey = (typeof URL_KEYS)[number];
const MORE_KEYS: FilterKey[] = ['vc', 'submitted_from', 'submitted_to', 'days'];
const PLAN_VALUES = ['yes', 'no'] as const;
const SELECT_CLASS = 'w-full min-h-[44px] px-3 py-2 text-base bg-dark-input border rounded-lg text-theme-text';
const INPUT_SM =
  'w-full min-h-[44px] px-3 py-2 text-base bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim';

interface Props {
  round: Round<SvsSettings>;
  readOnly: boolean;
  onChanged: () => void;
  /** Switch the admin shell to the Battle plan tab. */
  onOpenPlan?: () => void;
}

const tierValue = (label: string) => (label === 'none' ? 'none' : label.replace(/^T/, ''));

/** SVS answers for the add/edit player dialog: all optional (admin mode). */
interface AddState {
  hours: string[];
  vc: '' | 'yes' | 'no';
  troops: TroopValues;
}
const blankAdd = (): AddState => ({ hours: [], vc: '', troops: blankTroopValues() });

/** Edit dialog state: the form, the troops as loaded (only changes are sent) and the row button to refocus. */
interface EditState {
  app: SvsAdminApplication;
  el: HTMLElement;
  form: AddState;
  before: TroopValues;
}

/** The delete confirm's plan sentence: "They are Joiner 2 with Rally Caller 01 (Main); ...". */
function planWarning(t: ReturnType<typeof useTranslation>['t'], d: PlanDoc, p: Placement, people: Record<string, Person>): string {
  const name = makePlayerName(people);
  const g = d.groups.find((x) => x.id === p.groupId);
  const group = g ? groupLabel(t, g) : '';
  if (p.kind === 'extraGroup') return t('svs:players.deletePlan.group', { group });
  const l = d.leaders.find((x) => x.id === p.leaderId);
  const leader = l ? leaderLabel(t, d, l, name) : '?';
  if (p.kind === 'leader') return t('svs:players.deletePlan.leader', { leader, group });
  if (p.kind === 'joiner') return t('svs:players.deletePlan.joiner', { leader, group, n: p.index + 1 });
  return t('svs:players.deletePlan.extra', { leader, group });
}

/** Hours, Discord VC and troops: the SVS part of the add AND edit dialogs. `oldHours`: hours this sign-up keeps
 * that the round no longer has (start/duration changed); they stay selectable so an edit doesn't drop them. */
function SvsAnswerFields({
  value,
  onChange,
  hours,
  oldHours = [],
  prefix,
  troopsHint,
}: {
  value: AddState;
  onChange: (f: (s: AddState) => AddState) => void;
  hours: string[];
  oldHours?: string[];
  prefix: string;
  troopsHint?: string;
}) {
  const { t } = useTranslation();
  const hoursErr = useDialogError('answers.hours');
  const vcErr = useDialogError('answers.discord_vc');
  return (
    <>
      <div>
        <p className="block text-sm font-medium text-theme-text mb-2" id={`${prefix}-hours-label`}>
          {t('svs:step2.title')}
        </p>
        <div
          className={`flex flex-wrap gap-2 ${hoursErr ? 'p-1 rounded-lg ring-2 ring-danger' : ''}`}
          role="group"
          aria-labelledby={`${prefix}-hours-label`}
          aria-describedby={hoursErr ? `${prefix}-hours-error` : undefined}
          data-testid={`${prefix}-hours`}
        >
          {[...hours, ...oldHours].map((h) => {
            const on = value.hours.includes(h);
            const old = !hours.includes(h);
            return (
              <button
                key={h}
                type="button"
                aria-pressed={on}
                aria-invalid={(hoursErr && h === hours[0]) || undefined}
                data-testid={`${prefix}-hour-${h}`}
                data-old={old ? 'true' : undefined}
                title={old ? t('admin:playerEdit.oldHour') : undefined}
                onClick={() => onChange((s) => ({ ...s, hours: on ? s.hours.filter((x) => x !== h) : [...s.hours, h] }))}
                className={`min-h-[44px] px-3 rounded-lg border-2 text-sm font-semibold ${old ? 'border-dashed' : ''} ${on ? 'bg-accent border-accent text-dark-bg' : 'border-theme-border text-theme-text hover:border-accent'}`}
              >
                <bdi dir="ltr">{h} UTC</bdi>
                {old && <span className="ms-1 text-xs font-normal">({t('admin:playerEdit.old')})</span>}
              </button>
            );
          })}
        </div>
        <InlineError id={`${prefix}-hours-error`} message={hoursErr} />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor={`${prefix}-vc`} className="block text-sm font-medium text-theme-text mb-2">
            {t('svs:step4.vc')}
          </label>
          <select
            id={`${prefix}-vc`}
            data-testid={`${prefix}-vc`}
            value={value.vc}
            aria-invalid={!!vcErr || undefined}
            aria-describedby={vcErr ? `${prefix}-vc-error` : undefined}
            onChange={(e) => onChange((s) => ({ ...s, vc: e.target.value as AddState['vc'] }))}
            className={`${SELECT_CLASS} ${vcErr ? 'border-danger' : 'border-theme-border'}`}
          >
            <option value="">—</option>
            <option value="yes">{t('common:yes')}</option>
            <option value="no">{t('common:no')}</option>
          </select>
          <InlineError id={`${prefix}-vc-error`} message={vcErr} />
        </div>
      </div>
      <TroopFields value={value.troops} onChange={(tr) => onChange((s) => ({ ...s, troops: tr }))} tiers={SVS_TIERS} idPrefix={prefix} hint={troopsHint} />
    </>
  );
}

export default function SvsPlayers({ round, readOnly, onChanged, onOpenPlan }: Props) {
  const { t } = useTranslation();
  const fmt = useFormatDateTime();
  const F = useUrlFilters<UrlKey>(URL_KEYS);
  const v = F.values;
  const hours = useMemo(() => battleHours(round.settings), [round.settings]);

  const [summary, setSummary] = useState<SvsSummary | null>(null);
  const [apps, setApps] = useState<SvsAdminApplication[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState(v.q ?? '');
  const [page, setPage] = useState(0);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const moreActive = MORE_KEYS.filter((k) => v[k]).length;
  const [moreOpen, setMoreOpen] = useState(moreActive > 0);
  const [adding, setAdding] = useState(false);
  const [add, setAdd] = useState<AddState>(blankAdd);
  const [planDoc, setPlanDoc] = useState<PlanDoc | null>(null);
  const [planPeople, setPlanPeople] = useState<Record<string, Person>>({});
  const [selected, setSelected] = useState<Map<string, string>>(new Map()); // fid -> name
  const [rally, setRally] = useState<{ anchor: HTMLElement; players: RallyPlayer[] } | null>(null);
  const [rallyNote, setRallyNote] = useState<{ text: string; warn: boolean } | null>(null);
  const [editing, setEditing] = useState<EditState | null>(null);
  const [deleting, setDeleting] = useState<{ app: SvsAdminApplication; el: HTMLElement; warning: string | null } | null>(null);
  const toast = useToast();
  const sort: SortKey = SORT_KEYS.includes(v.sort as SortKey) ? (v.sort as SortKey) : 'submitted';
  const dir: 'asc' | 'desc' = v.dir === 'asc' ? 'asc' : 'desc';

  // the URL is the filter state; drop hours this round doesn't have (a link from another round)
  const filters: FilterQuery = useMemo(() => {
    const f: FilterQuery = {};
    for (const k of FILTER_KEYS) if (v[k]) f[k] = v[k];
    if (f.hours) f.hours = splitList(f.hours).filter((h) => hours.includes(h)).join(',') || undefined;
    return f;
  }, [v, hours]);
  const filtersKey = JSON.stringify(filters);
  const filtered = Object.values(filters).some(Boolean);

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
      const [s, list, plan] = await Promise.all([
        svsApi.admin.summary(round.id, filters),
        svsApi.admin.applications(round.id, { ...filters, sort, dir, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
        planApi.get(round.id).catch(() => null),
      ]);
      setSummary(s);
      if (plan) {
        setPlanDoc(normalizeDoc(plan.plan));
        setPlanPeople(plan.people);
      }
      setApps(list.applications);
      setTotal(list.total);
      setError('');
    } catch (e) {
      setError(errorText(t, e, 'admin:fetchError'));
    }
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

  const toggleExact = (key: FilterKey, value: string) => F.set({ [key]: v[key] === value ? null : value });

  // ------------------------------------------------------------ edit / remove (v2.2.1)
  const openEdit = (a: SvsAdminApplication, el: HTMLElement) => {
    const troops = svsTroops(a.profile.troops);
    const vc = a.answers.discord_vc;
    setEditing({ app: a, el, before: troops, form: { hours: [...(a.answers.hours ?? [])], vc: vc == null ? '' : vc ? 'yes' : 'no', troops } });
  };
  const closeEdit = () => {
    const el = editing?.el;
    setEditing(null);
    el?.focus();
  };
  /** Summary counts follow an edit; the list itself is patched in place (no reload: filters, page and scroll stay). */
  const refreshSummary = () =>
    svsApi.admin
      .summary(round.id, filters)
      .then(setSummary)
      .catch(() => undefined);

  const openDelete = async (a: SvsAdminApplication, el: HTMLElement) => {
    // the plan as it is NOW (another leader may have changed it since the list loaded)
    const plan = await planApi.get(round.id).catch(() => null);
    let warning: string | null = null;
    if (plan) {
      const d = normalizeDoc(plan.plan);
      setPlanDoc(d);
      setPlanPeople(plan.people);
      const p = placements(d).get(`fid:${a.fid}`);
      if (p) warning = planWarning(t, d, p, plan.people);
    }
    setDeleting({ app: a, el, warning });
  };
  const closeDelete = () => {
    const el = deleting?.el;
    setDeleting(null);
    el?.focus();
  };
  const remove = async (a: SvsAdminApplication) => {
    try {
      const res = await svsApi.admin.deleteApplication(a.id);
      setDeleting(null);
      setSelected((m) => {
        const n = new Map(m);
        n.delete(a.fid);
        return n;
      });
      toast.show(t(res.plan_removed?.length ? 'admin:playerEdit.removedPlan' : 'admin:playerEdit.removed', { name: a.profile.game_name }));
      onChanged();
      load();
    } catch (e) {
      setDeleting(null);
      setError(errorText(t, e, 'admin:deleteError'));
    }
  };

  const doExport = async (kind: 'csv' | 'xlsx') => {
    try {
      const blob = kind === 'csv' ? await svsApi.admin.exportCsv(round.id, filters) : await svsApi.admin.exportXlsx(round.id, filters);
      const slug = round.name.replace(/[^A-Za-z0-9]+/g, '_').toLowerCase() || 'round';
      downloadBlob(blob, `svs_${slug}${filtered ? '_filtered' : ''}.${kind}`);
    } catch (e) {
      setError(errorText(t, e, 'tyrant:admin.exportError'));
    }
  };

  // ------------------------------------------------------------ pills
  const troopName = (k: string) => t(`tyrant:admin.troopName.${k}`);
  const daysLabel = (n: number) => (n === 1 ? t('tyrant:admin.filter.last24h') : t('tyrant:admin.pill.days', { n }));
  const pills: FilterPill[] = [];
  const pill = (id: string, text: string, onRemove: () => void) => pills.push({ id, text, label: text, onRemove });
  if (v.q) pill('q', t('tyrant:admin.pill.search', { v: v.q }), () => F.set({ q: null }));
  for (const a of splitList(v.alliance)) pill(`alliance-${a}`, t('tyrant:admin.pill.alliance', { v: a }), () => F.toggleInList('alliance', a));
  for (const h of splitList(filters.hours)) pill(`hour-${h}`, t('svs:admin.pill.hour', { v: h }), () => F.toggleInList('hours', h));
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
  if (v.vc === 'yes' || v.vc === 'no') pill('vc', t(v.vc === 'yes' ? 'svs:admin.pill.vcYes' : 'svs:admin.pill.vcNo'), () => F.set({ vc: null }));
  if (v.submitted_from) pill('submitted_from', t('tyrant:admin.pill.from', { v: v.submitted_from }), () => F.set({ submitted_from: null }));
  if (v.submitted_to) pill('submitted_to', t('tyrant:admin.pill.to', { v: v.submitted_to }), () => F.set({ submitted_to: null }));
  if (v.days) pill('days', daysLabel(Number(v.days)), () => F.set({ days: null }));
  if (v.in_plan === 'yes' || v.in_plan === 'no')
    pill('in_plan', t(v.in_plan === 'yes' ? 'svs:players.filter.inPlan' : 'svs:players.filter.notInPlan'), () => F.set({ in_plan: null }));

  // ------------------------------------------------------------ battle plan (Plan column, Add to rally, bulk)
  const planName = useMemo(() => makePlayerName(planPeople), [planPeople]);
  const placedMap = useMemo(() => (planDoc ? placements(planDoc) : null), [planDoc]);
  const planText = (fid: string) => {
    const p = placedMap?.get(`fid:${fid}`);
    return p && planDoc ? placementShort(t, planDoc, p, planName) : null;
  };
  const toggleSelect = (a: SvsAdminApplication) =>
    setSelected((m) => {
      const n = new Map(m);
      if (n.has(a.fid)) n.delete(a.fid);
      else n.set(a.fid, a.profile.game_name);
      return n;
    });
  const pageAllSelected = apps.length > 0 && apps.every((a) => selected.has(a.fid));
  const toggleAllOnPage = () =>
    setSelected((m) => {
      const n = new Map(m);
      if (pageAllSelected) apps.forEach((a) => n.delete(a.fid));
      else apps.forEach((a) => n.set(a.fid, a.profile.game_name));
      return n;
    });
  const rallyDone = (text: string, warn: boolean) => {
    const bulkRun = (rally?.players.length ?? 0) > 1;
    setRally(null);
    if (bulkRun) setSelected(new Map());
    setRallyNote({ text, warn });
    load();
  };

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
  const vcCell = (on: boolean | null) =>
    on == null ? <span className="text-theme-dim">?</span> : on ? <span className="text-success font-bold">✓</span> : <span className="text-theme-dim">—</span>;
  const allianceSel = splitList(v.alliance);
  const hourSel = splitList(filters.hours);
  const chosen = (n: number, none: string) => (n ? t('tyrant:admin.filter.selected', { n }) : none);

  const openAdd = () => {
    setAdd(blankAdd());
    setAdding(true);
  };

  return (
    <div className="space-y-6">
      {error && (
        <div className="p-3 bg-danger/10 border border-danger/30 rounded-lg flex items-center gap-2 text-danger" role="alert">
          <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
          {error}
        </div>
      )}
      {notice && (
        <div className="p-3 bg-success/10 border border-success/30 rounded-lg flex items-center gap-2 text-success" role="status" data-testid="add-player-done">
          <CheckCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
          {notice}
        </div>
      )}

      {rallyNote && (
        <div
          className={`p-3 rounded-lg flex items-start gap-2 border ${rallyNote.warn ? 'bg-warning/10 border-warning/30 text-warning' : 'bg-success/10 border-success/30 text-success'}`}
          role="status"
          data-testid="rally-result"
        >
          {rallyNote.warn ? <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" /> : <CheckCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />}
          <span className="flex-1">{rallyNote.text}</span>
          <button type="button" onClick={() => setRallyNote(null)} aria-label={t('svs:players.add.close')} className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] -m-3 rounded-lg">
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>
      )}

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
            <StatCard testId="stat-avg-hours" label={t('svs:admin.stats.avgHours')} value={summary.avg_hours} />
            <StatCard testId="stat-all-t11" label={t('svs:admin.stats.allT11')} value={summary.all_t11} />
            <StatCard testId="stat-discord-vc" label={t('svs:admin.stats.vc')} value={summary.discord_vc} />
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <Bars
              testId="by-hour"
              title={t('svs:admin.byHour')}
              total={summary.total}
              rows={summary.hours.map((h) => ({
                key: h.hour,
                n: h.count,
                active: hourSel.includes(h.hour),
                onClick: () => F.toggleInList('hours', h.hour),
                label: <bdi dir="ltr">{h.hour} UTC</bdi>,
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

          <div className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-5" data-testid="by-troop">
            <h3 className="font-semibold text-accent">{t('tyrant:admin.byTroop')}</h3>
            <p className="text-xs text-theme-dim mb-3">{t('tyrant:admin.chipHint')}</p>
            <div className="grid lg:grid-cols-3 gap-4">
              {TROOP_TYPES.map((k: TroopType) => (
                <div key={k} data-testid={`by-troop-${k}`} className="space-y-2">
                  <div className="text-theme-text font-semibold flex items-center gap-1.5"><TroopIcon troop={k} className="w-4 h-4" />{t(`tyrant:step4.${k}`)}</div>
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

      {/* ---------------------------------------------------------------- filter bar */}
      <div className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-5 space-y-4" data-testid="svs-filters">
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 items-end">
          <div className="col-span-2 md:col-span-3 xl:col-span-2">
            <label htmlFor="svs-search" className="block text-sm font-medium text-theme-text mb-2">
              {t('tyrant:admin.filter.search')}
            </label>
            <div className="relative">
              <Search className="w-4 h-4 absolute top-1/2 -translate-y-1/2 start-3 text-theme-dim" aria-hidden="true" />
              <input
                id="svs-search"
                data-testid="svs-search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t('svs:admin.search')}
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
            id="hours-filter"
            label={t('svs:admin.filter.hours')}
            summary={chosen(hourSel.length, t('svs:admin.filter.anyHour'))}
            options={hours.map((h) => ({ value: h, label: <bdi dir="ltr">{h} UTC</bdi> }))}
            selected={hourSel}
            onToggle={(h) => F.toggleInList('hours', h)}
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
                {t('svs:admin.stats.vc')}
              </label>
              <select id="filter-vc" data-testid="filter-vc" value={v.vc ?? ''} onChange={(e) => F.set({ vc: e.target.value || null })} className={`${SELECT_CLASS} border-theme-border`}>
                <option value="">{t('tyrant:admin.filter.any')}</option>
                <option value="yes">{t('tyrant:admin.filter.yes')}</option>
                <option value="no">{t('tyrant:admin.filter.no')}</option>
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

        {summary?.plan && (
          <div className="flex flex-wrap items-center gap-2" data-testid="plan-chips">
            <span className="text-sm font-medium text-theme-text">{t('svs:players.filter.plan')}</span>
            {PLAN_VALUES.map((val) => (
              <ChipButton key={val} testId={`chip-in-plan-${val}`} active={v.in_plan === val} onClick={() => toggleExact('in_plan', val)}>
                {t(val === 'yes' ? 'svs:players.filter.inPlan' : 'svs:players.filter.notInPlan')}: <b data-testid="chip-count">{val === 'yes' ? summary.plan!.in : summary.plan!.out}</b>
              </ChipButton>
            ))}
          </div>
        )}

        <FilterPills pills={pills} onClear={clearAll} />
      </div>

      {/* ---------------------------------------------------------------- table */}
      <div className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-3 mb-3">
          <p className="text-sm text-theme-dim flex-1" data-testid="result-count">
            {filtered && summary ? t('tyrant:admin.showingOf', { n: total, total: summary.round_total }) : t('tyrant:admin.showing', { n: total })}
          </p>
          {!readOnly && <AddPlayerButton onClick={openAdd} />}
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

        {/* relative: the Plan column's sr-only text is position:absolute; without a positioned scroller it escaped the
            horizontal scroll and widened the whole page on phones (579px at 390) */}
        <div className="relative overflow-x-auto">
          <ClosedRoundNote show={readOnly} />
          <table className="w-full text-sm" data-testid="svs-table">
            <thead className="border-b border-theme-border">
              <tr>
                {!readOnly && (
                  <th className="px-1 py-1 w-10">
                    <input
                      type="checkbox"
                      checked={pageAllSelected}
                      onChange={toggleAllOnPage}
                      aria-label={t('svs:players.select.all')}
                      data-testid="select-all"
                      className="w-5 h-5 accent-accent cursor-pointer align-middle"
                    />
                  </th>
                )}
                {th('name', t('tyrant:fields.ingameName'))}
                {th('fid', t('admin:fid'))}
                {th('alliance', t('tyrant:fields.alliance'))}
                {th('hours', t('svs:admin.col.hours'))}
                {th(null, t('svs:players.col.plan'))}
                {th(null, t('tyrant:admin.col.vc'))}
                {th('strength', t('tyrant:admin.col.strength'))}
                {th('submitted', t('tyrant:admin.col.submitted'))}
                {th(null, t('admin:actions'))}
              </tr>
            </thead>
            <tbody>
              {apps.map((a) => {
                const troops = parseTroops(a.profile.troops);
                const mine = new Set(a.answers.hours ?? []);
                return (
                  <tr key={a.id} className="border-b border-theme-border/50 hover:bg-dark-card-hover align-top" data-testid={`player-row-${a.fid}`}>
                    {!readOnly && (
                      <td className="px-1 py-2">
                        <input
                          type="checkbox"
                          checked={selected.has(a.fid)}
                          onChange={() => toggleSelect(a)}
                          aria-label={t('svs:players.select.row', { name: a.profile.game_name })}
                          data-testid={`select-${a.fid}`}
                          className="w-5 h-5 mt-3 accent-accent cursor-pointer"
                        />
                      </td>
                    )}
                    <td className="px-2 py-2 font-medium text-theme-text min-w-[12rem]">
                      <bdi>{a.profile.game_name}</bdi>
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
                    <td className="px-2 py-2">
                      <div className="flex flex-wrap gap-1 max-w-[11rem]" data-testid={`hours-${a.fid}`}>
                        {hours.map((h) => (
                          <span
                            key={h}
                            data-on={mine.has(h) ? 'true' : undefined}
                            className={`px-1.5 py-0.5 rounded text-xs ${mine.has(h) ? 'bg-success/20 text-success' : 'bg-dark-bg text-theme-dim'}`}
                          >
                            <bdi dir="ltr">{h}</bdi>
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-2 py-2 text-xs min-w-[9rem] max-w-[14rem]" data-testid={`plan-${a.fid}`}>
                      {planText(a.fid) ? (
                        <span className="inline-block px-1.5 py-0.5 rounded bg-accent/15 text-accent font-semibold">
                          <bdi>{planText(a.fid)}</bdi>
                        </span>
                      ) : (
                        <span className="text-theme-dim">
                          <span aria-hidden="true">—</span>
                          <span className="sr-only">{t('svs:players.filter.notInPlan')}</span>
                        </span>
                      )}
                    </td>
                    <td className="px-2 py-2">{vcCell(a.answers.discord_vc ?? null)}</td>
                    <td className="px-2 py-2 text-theme-text font-semibold" data-testid="strength">
                      {a.joiner_strength ?? '—'}
                    </td>
                    <td className="px-2 py-2 text-xs text-theme-dim whitespace-nowrap">{fmt(a.created_at, { withZone: false, weekday: false, isolate: false })}</td>
                    <td className="px-2 py-2 whitespace-nowrap">
                      <PlayerRowActions
                        fid={a.fid}
                        name={a.profile.game_name}
                        readOnly={readOnly}
                        onEdit={(el) => openEdit(a, el)}
                        onDelete={(el) => openDelete(a, el)}
                      >
                        {!readOnly && (
                        <button
                          type="button"
                          onClick={(e) => {
                            const el = e.currentTarget;
                            setRallyNote(null);
                            setRally((r) => (r?.anchor === el ? null : { anchor: el, players: [{ fid: a.fid, name: a.profile.game_name }] }));
                          }}
                          data-testid={`add-to-rally-${a.fid}`}
                          aria-label={t('svs:players.add.button', { name: a.profile.game_name })}
                          title={t('svs:players.add.title')}
                          aria-haspopup="dialog"
                          aria-expanded={rally?.players.length === 1 && rally.players[0].fid === a.fid}
                          className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] p-2 text-accent hover:bg-accent/10 rounded-lg"
                        >
                          <UserPlus className="w-4 h-4" aria-hidden="true" />
                        </button>
                        )}
                      </PlayerRowActions>
                    </td>
                  </tr>
                );
              })}
              {apps.length === 0 && (
                <tr>
                  <td colSpan={11} className="px-3 py-10 text-center text-theme-dim" data-testid="no-players">
                    {filtered ? t('tyrant:admin.noMatches') : t('tyrant:admin.noPlayers')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {pages > 1 && (
          <div className="flex items-center justify-center gap-4 mt-4 text-sm" data-testid="pager">
            <button type="button" disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="min-h-[44px] px-3 py-1 border border-theme-border rounded-lg text-theme-text disabled:opacity-40">
              {t('tyrant:admin.prev')}
            </button>
            <span className="text-theme-dim">{t('tyrant:admin.page', { page: page + 1, pages })}</span>
            <button type="button" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)} className="min-h-[44px] px-3 py-1 border border-theme-border rounded-lg text-theme-text disabled:opacity-40">
              {t('tyrant:admin.next')}
            </button>
          </div>
        )}
      </div>

      {!readOnly && selected.size > 0 && (
        <div className="sticky bottom-2 z-30 flex flex-wrap items-center gap-3 p-3 rounded-xl border border-accent/50 bg-dark-card shadow-2xl" data-testid="bulk-bar" role="region" aria-label={t('svs:players.bulk.selected', { n: selected.size })}>
          <span className="text-sm font-semibold text-theme-text flex-1" data-testid="bulk-count">
            {t('svs:players.bulk.selected', { n: selected.size })}
          </span>
          <button
            type="button"
            onClick={() => setSelected(new Map())}
            data-testid="bulk-clear"
            className="min-h-[44px] px-3 rounded-lg border border-theme-border text-theme-text text-sm hover:bg-dark-card-hover"
          >
            {t('svs:players.bulk.clear')}
          </button>
          <button
            type="button"
            onClick={(e) => {
              const el = e.currentTarget;
              setRallyNote(null);
              setRally((r) => (r?.anchor === el ? null : { anchor: el, players: [...selected].map(([fid, name]) => ({ fid, name })) }));
            }}
            aria-haspopup="dialog"
            data-testid="bulk-add"
            className="inline-flex items-center gap-2 min-h-[44px] px-4 rounded-lg bg-accent text-dark-bg font-semibold hover:opacity-90"
          >
            <UserPlus className="w-4 h-4" aria-hidden="true" />
            {t('svs:players.bulk.add', { n: selected.size })}
          </button>
        </div>
      )}

      {rally && (
        <AddToRally
          round={round}
          anchor={rally.anchor}
          players={rally.players}
          onClose={() => setRally(null)}
          onDone={rallyDone}
          onOpenPlan={
            onOpenPlan
              ? () => {
                  setRally(null);
                  onOpenPlan();
                }
              : undefined
          }
        />
      )}

      {adding && (
        <AddPlayerDialog
          event="svs"
          roundId={round.id}
          onClose={() => setAdding(false)}
          onAdded={(name) => {
            setAdding(false);
            setNotice(t('admin:addPlayer.added', { name }));
            setTimeout(() => setNotice(''), 4000);
            onChanged();
            load();
          }}
          onProfile={(p) => {
            const tr = svsTroops(p?.troops);
            setAdd((s) => ({ ...s, troops: tr }));
          }}
          extra={() => {
            const answers: Record<string, unknown> = {};
            if (add.hours.length) answers.hours = hours.filter((h) => add.hours.includes(h));
            if (add.vc) answers.discord_vc = add.vc === 'yes';
            const troops = filledTroops(add.troops);
            return { answers, ...(troops ? { profile: { troops } } : {}) };
          }}
        >
          <SvsAnswerFields value={add} onChange={setAdd} hours={hours} prefix="add" />
        </AddPlayerDialog>
      )}

      {editing && (
        <AddPlayerDialog
          event="svs"
          roundId={round.id}
          edit={{ appId: editing.app.id, fid: editing.app.fid, name: editing.app.profile.game_name, alliance: editing.app.profile.alliance ?? '' }}
          sharedNote={t('admin:playerEdit.shared')}
          onClose={closeEdit}
          onSaved={(raw, name) => {
            const u = raw as SvsAdminApplication;
            // in place: keep the row's plan placement (an edit doesn't move anyone in the plan)
            setApps((list) => list.map((x) => (x.id === u.id ? { ...x, ...u, plan_place: x.plan_place } : x)));
            setPlanPeople((pp) => (pp[u.fid] ? { ...pp, [u.fid]: { ...pp[u.fid], game_name: u.profile.game_name, alliance: u.profile.alliance } } : pp));
            closeEdit();
            toast.show(t('admin:playerEdit.saved', { name }));
            refreshSummary();
          }}
          extra={() => {
            const f = editing.form;
            const all = [...hours, ...(editing.app.answers.hours ?? []).filter((h) => !hours.includes(h))];
            const answers: Record<string, unknown> = { hours: all.filter((h) => f.hours.includes(h)), discord_vc: f.vc ? f.vc === 'yes' : null };
            const troops = changedTroops(f.troops, editing.before);
            return { answers, ...(troops ? { profile: { troops } } : {}) };
          }}
        >
          <SvsAnswerFields
            value={editing.form}
            onChange={(fn) => setEditing((e) => (e ? { ...e, form: fn(e.form) } : e))}
            hours={hours}
            oldHours={(editing.app.answers.hours ?? []).filter((h) => !hours.includes(h))}
            prefix="edit"
            troopsHint={t('admin:playerEdit.troopsHint')}
          />
        </AddPlayerDialog>
      )}

      {deleting && (
        <DeletePlayerDialog
          name={deleting.app.profile.game_name}
          alliance={deleting.app.profile.alliance}
          fid={deleting.app.fid}
          planWarning={deleting.warning}
          onConfirm={() => remove(deleting.app)}
          onClose={closeDelete}
        />
      )}
      {toast.node}
    </div>
  );
}
