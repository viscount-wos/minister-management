import { ReactNode, useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, Trash2, FileSpreadsheet, FileText, ChevronUp, ChevronDown, AlertCircle } from 'lucide-react';
import { Round, downloadBlob } from '../../../shared/api';
import { errorText } from '../../../shared/apiErrors';
import FurnaceLevelSelect from '../../../shared/FurnaceLevelSelect';
import { ROLES, SortKey, TROOP_TYPES, TyrantAdminApplication, TyrantSettings, TyrantSummary, parseTroops, tyrantApi } from '../api';

const PAGE_SIZE = 50;

interface Props {
  round: Round<TyrantSettings>;
  readOnly: boolean;
  onChanged: () => void;
}

function StatCard({ label, value, testId }: { label: string; value: ReactNode; testId: string }) {
  return (
    <div className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-5 text-center" data-testid={testId}>
      <div className="text-3xl font-bold text-accent" data-testid={`${testId}-value`}>
        {value}
      </div>
      <div className="text-sm text-theme-dim mt-1">{label}</div>
    </div>
  );
}

/** Horizontal bar list: label + count, bar width relative to the round total. */
function Bars({ title, rows, total, testId }: { title: string; rows: { key: string; label: ReactNode; n: number }[]; total: number; testId: string }) {
  return (
    <div className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-5" data-testid={testId}>
      <h3 className="font-semibold text-accent mb-3">{title}</h3>
      <div className="space-y-2">
        {rows.map((r) => (
          <div key={r.key} className="text-sm" data-testid={`${testId}-${r.key}`} data-count={r.n}>
            <div className="flex justify-between gap-2 text-theme-text">
              <span>{r.label}</span>
              <span className="font-semibold">{r.n}</span>
            </div>
            <div className="h-1.5 rounded bg-dark-bg mt-1 overflow-hidden">
              <div className="h-full bg-accent" style={{ width: `${total ? Math.round((r.n / total) * 100) : 0}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const Range = ({ start, end }: { start: string; end: string }) => (
  <bdi dir="ltr">
    {start}–{end}
  </bdi>
);

export default function TyrantPlayers({ round, readOnly, onChanged }: Props) {
  const { t } = useTranslation();
  const [summary, setSummary] = useState<TyrantSummary | null>(null);
  const [apps, setApps] = useState<TyrantAdminApplication[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  const [alliance, setAlliance] = useState('');
  const [minFurnace, setMinFurnace] = useState('');
  const [sort, setSort] = useState<SortKey>('submitted');
  const [dir, setDir] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(0);
  const [error, setError] = useState('');
  const windows = round.settings.windows;

  // debounce the search box
  useEffect(() => {
    const id = setTimeout(() => {
      setQuery(q);
      setPage(0);
    }, 250);
    return () => clearTimeout(id);
  }, [q]);

  const load = useCallback(async () => {
    try {
      const [s, list] = await Promise.all([
        tyrantApi.admin.summary(round.id, alliance || undefined),
        tyrantApi.admin.applications(round.id, {
          q: query || undefined,
          alliance: alliance || undefined,
          min_furnace: minFurnace || undefined,
          sort,
          dir,
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
        }),
      ]);
      setSummary(s);
      setApps(list.applications);
      setTotal(list.total);
      setError('');
    } catch (e) {
      setError(errorText(t, e, 'admin:fetchError'));
    }
  }, [round.id, query, alliance, minFurnace, sort, dir, page, t]);

  useEffect(() => {
    load();
  }, [load]);

  // the alliance list comes from the unfiltered summary, so keep the first one we saw
  const [allAlliances, setAllAlliances] = useState<string[]>([]);
  useEffect(() => {
    if (summary && !alliance) setAllAlliances(summary.alliances.map((a) => a.alliance).filter((a): a is string => !!a));
  }, [summary, alliance]);

  const toggleSort = (key: SortKey) => {
    if (sort === key) setDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSort(key);
      setDir(key === 'name' || key === 'alliance' || key === 'fid' ? 'asc' : 'desc');
    }
    setPage(0);
  };

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
      const blob = kind === 'csv' ? await tyrantApi.admin.exportCsv(round.id) : await tyrantApi.admin.exportXlsx(round.id);
      const slug = round.name.replace(/[^A-Za-z0-9]+/g, '_').toLowerCase() || 'round';
      downloadBlob(blob, `tyrant_${slug}.${kind}`);
    } catch (e) {
      setError(errorText(t, e, 'tyrant:admin.exportError'));
    }
  };

  const th = (key: SortKey | null, label: string) => (
    <th className="px-2 py-3 text-start font-semibold text-theme-dim whitespace-nowrap">
      {key ? (
        <button
          type="button"
          onClick={() => toggleSort(key)}
          data-testid={`sort-${key}`}
          data-active={sort === key ? dir : undefined}
          className="inline-flex items-center gap-1 hover:text-theme-text"
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

  return (
    <div className="space-y-6">
      {error && (
        <div className="p-3 bg-danger/10 border border-danger/30 rounded-lg flex items-center gap-2 text-danger" role="alert">
          <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
          {error}
        </div>
      )}

      {/* tyrantpoll's stats cards */}
      {summary && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <StatCard testId="stat-total" label={t('tyrant:admin.stats.total')} value={summary.total} />
            <StatCard testId="stat-opening-rush" label={t('tyrant:admin.stats.openingRush')} value={summary.opening_rush} />
            <StatCard testId="stat-discord-vc" label={t('tyrant:admin.stats.discordVc')} value={summary.discord_vc} />
            <StatCard testId="stat-alliances" label={t('tyrant:admin.stats.alliances')} value={summary.alliances.filter((a) => a.alliance).length} />
            <StatCard testId="stat-gems" label={t('tyrant:admin.stats.gems')} value={summary.gem_spend_total.toLocaleString()} />
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Bars
              testId="by-window"
              title={t('tyrant:admin.byWindow')}
              total={summary.total}
              rows={summary.windows.map((w) => ({
                key: w.id,
                n: w.count,
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
              rows={ROLES.map((r) => ({ key: r, n: summary.roles[r] ?? 0, label: t(`tyrant:roles.${r}`) }))}
            />
            <Bars
              testId="by-alliance"
              title={t('tyrant:admin.byAlliance')}
              total={summary.total}
              rows={summary.alliances.map((a) => ({ key: a.alliance ?? 'none', n: a.count, label: a.alliance ?? t('tyrant:admin.none') }))}
            />
            <div className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-5" data-testid="by-troop">
              <h3 className="font-semibold text-accent mb-3">{t('tyrant:admin.byTroop')}</h3>
              <div className="space-y-3 text-sm">
                {TROOP_TYPES.map((k) => (
                  <div key={k} data-testid={`by-troop-${k}`}>
                    <div className="text-theme-text font-medium mb-1">{t(`tyrant:step4.${k}`)}</div>
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(summary.troop_tiers[k] ?? {}).map(([tier, n]) => (
                        <span key={tier} className="px-2 py-0.5 rounded bg-dark-bg border border-theme-border text-theme-text" data-tier={tier}>
                          {tier === 'none' ? t('tyrant:admin.none') : tier}: <b>{n}</b>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      <div className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-5">
        <div className="flex flex-wrap items-end gap-3 mb-4">
          <div className="flex-1 min-w-[min(14rem,100%)]">
            <label htmlFor="tyrant-search" className="sr-only">
              {t('tyrant:admin.search')}
            </label>
            <div className="relative">
              <Search className="w-4 h-4 absolute top-1/2 -translate-y-1/2 start-3 text-theme-dim" aria-hidden="true" />
              <input
                id="tyrant-search"
                data-testid="tyrant-search"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder={t('tyrant:admin.search')}
                className="w-full ps-9 pe-3 py-3 bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim focus:ring-2 focus:ring-accent"
              />
            </div>
          </div>
          <div>
            <label htmlFor="alliance-filter" className="block text-sm font-medium text-theme-text mb-2">
              {t('tyrant:admin.allianceFilter')}
            </label>
            <select
              id="alliance-filter"
              data-testid="alliance-filter"
              value={alliance}
              onChange={(e) => {
                setAlliance(e.target.value);
                setPage(0);
              }}
              className="px-4 py-3 bg-dark-input border border-theme-border rounded-lg text-theme-text"
            >
              <option value="">{t('tyrant:admin.allAlliances')}</option>
              {allAlliances.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>
          <div className="w-44">
            <FurnaceLevelSelect
              id="furnace-filter"
              label={t('tyrant:admin.minFurnace')}
              emptyLabel={t('tyrant:admin.anyFurnace')}
              value={minFurnace}
              onChange={(code) => {
                setMinFurnace(code);
                setPage(0);
              }}
            />
          </div>
          <button
            type="button"
            onClick={() => doExport('csv')}
            data-testid="export-csv"
            className="flex items-center gap-2 px-4 py-2 bg-accent/20 text-accent rounded-lg hover:bg-accent/30 font-medium"
          >
            <FileText className="w-4 h-4" aria-hidden="true" />
            {t('tyrant:admin.exportCsv')}
          </button>
          <button
            type="button"
            onClick={() => doExport('xlsx')}
            data-testid="export-excel"
            className="flex items-center gap-2 px-4 py-2 bg-success text-white rounded-lg hover:bg-success-dark font-medium"
          >
            <FileSpreadsheet className="w-4 h-4" aria-hidden="true" />
            {t('tyrant:admin.exportExcel')}
          </button>
        </div>

        <p className="text-sm text-theme-dim mb-2" data-testid="result-count">
          {t('tyrant:admin.showing', { n: total })}
        </p>

        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="tyrant-table">
            <thead className="border-b border-theme-border">
              <tr>
                {th('name', t('tyrant:fields.ingameName'))}
                {th('fid', t('admin:fid'))}
                {th('alliance', t('tyrant:fields.alliance'))}
                {th(null, t('tyrant:fields.discordId'))}
                {th('furnace', t('tyrant:step3.furnaceLevel'))}
                {th('power', t('tyrant:admin.col.power'))}
                {th('gems', t('tyrant:admin.col.gems'))}
                {th(null, t('tyrant:admin.col.windows'))}
                {th(null, t('tyrant:admin.col.vc'))}
                {th(null, t('tyrant:step4.title'))}
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
                  <tr key={a.id} className="border-b border-theme-border/50 hover:bg-dark-card-hover" data-testid={`player-row-${a.fid}`}>
                    <td className="px-2 py-2 font-medium text-theme-text">
                      <bdi>{a.profile.game_name}</bdi>
                    </td>
                    <td className="px-2 py-2 text-theme-dim">{a.fid}</td>
                    <td className="px-2 py-2 text-accent font-semibold">{a.profile.alliance}</td>
                    <td className="px-2 py-2 text-theme-text">
                      <bdi>{a.profile.discord_id || '—'}</bdi>
                    </td>
                    <td className="px-2 py-2">
                      {a.profile.furnace_level ? (
                        <span className="px-2 py-0.5 rounded bg-accent/20 text-accent text-xs font-semibold" data-testid="furnace-badge">
                          {a.profile.furnace_level}
                        </span>
                      ) : (
                        '—'
                      )}
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
                    <td className="px-2 py-2 text-xs text-theme-text whitespace-nowrap">
                      {TROOP_TYPES.map((k) => (
                        <div key={k}>
                          <span className="text-theme-dim">{t(`tyrant:admin.troopShort.${k}`)}</span>{' '}
                          <bdi dir="ltr">
                            {troops[k].furnace_level || '—'} / {troops[k].tier ? `T${troops[k].tier}` : '—'}
                          </bdi>
                        </div>
                      ))}
                    </td>
                    <td className="px-2 py-2 text-xs text-theme-text">
                      {(a.answers.roles ?? []).map((r) => t(`tyrant:roles.${r}`)).join(', ') || '—'}
                    </td>
                    <td className="px-2 py-2 text-xs text-theme-dim whitespace-nowrap">{new Date(a.created_at).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}</td>
                    {!readOnly && (
                      <td className="px-2 py-2">
                        <button
                          type="button"
                          onClick={() => remove(a)}
                          data-testid={`delete-${a.fid}`}
                          aria-label={t('admin:delete')}
                          className="p-2 text-danger hover:bg-danger/10 rounded-lg"
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
                    {t('tyrant:admin.noPlayers')}
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
              className="px-3 py-1 border border-theme-border rounded-lg text-theme-text disabled:opacity-40"
            >
              {t('tyrant:admin.prev')}
            </button>
            <span className="text-theme-dim">{t('tyrant:admin.page', { page: page + 1, pages })}</span>
            <button
              type="button"
              disabled={page + 1 >= pages}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1 border border-theme-border rounded-lg text-theme-text disabled:opacity-40"
            >
              {t('tyrant:admin.next')}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
