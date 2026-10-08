import { useState, useEffect, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, Edit2, Trash2, X, Save, AlertCircle, Download, Upload } from 'lucide-react';
import api, { AdminApplication, Round, downloadBlob } from '../../../shared/api';
import FurnaceLevelSelect from '../../../shared/FurnaceLevelSelect';
import { toFurnaceCode } from '../../../shared/furnace';
import { errorText } from '../../../shared/apiErrors';
import { Field } from '../../../shared/fields';
import { useTimezone } from '../../../shared/TimezoneContext';
import { AnswersForm, CRYSTAL_FIELDS, answersToForm, formToAnswers, totalSlots } from '../answers';
import TimeSlotPicker from '../TimeSlotPicker';

// Applications of ONE round (the dashboard's selected round). Admin edits go
// to the application (answers) and the player's profile (name, alliance).

interface Row {
  app: AdminApplication;
  id: number;
  fid: string;
  game_name: string;
  alliance: string;
  furnace_level: string;
  avatar_image: string | null;
  monday_points: number;
  research_points: number;
  thursday_points: number;
  slots: number;
}

type SortField = 'game_name' | 'fid' | 'monday_points' | 'research_points' | 'thursday_points';
type SortDirection = 'asc' | 'desc';

interface EditState {
  app: AdminApplication;
  game_name: string;
  alliance: string;
  furnace_level: string;
  answers: AnswersForm;
}

const ADMIN_NUMBER_FIELDS = [
  { key: 'construction_speedups_days', label: 'admin:constructionDays' },
  { key: 'research_speedups_days', label: 'admin:researchDays' },
  { key: 'troop_training_speedups_days', label: 'admin:troopDays' },
  { key: 'general_speedups_days', label: 'admin:generalDays' },
] as const;

function toRow(app: AdminApplication): Row {
  const p = app.profile ?? app.profile_snapshot;
  return {
    app,
    id: app.id,
    fid: String(app.fid ?? ''),
    game_name: p?.game_name ?? '',
    alliance: p?.alliance ?? '',
    furnace_level: toFurnaceCode(p?.furnace_level),
    avatar_image: p?.avatar_image ?? null,
    monday_points: app.monday_points ?? 0,
    research_points: app.research_points ?? 0,
    thursday_points: app.thursday_points ?? 0,
    slots: totalSlots(answersToForm(app.answers).time_slots_by_day),
  };
}

export default function PlayerManagement({
  round,
  readOnly,
  onChanged,
}: {
  round: Round;
  readOnly: boolean;
  onChanged?: () => void;
}) {
  const { t } = useTranslation();
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState<SortField>('game_name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [editing, setEditing] = useState<EditState | null>(null);
  const [deleting, setDeleting] = useState<Row | null>(null);
  const [importMessage, setImportMessage] = useState('');
  const { timezone, setTimezone } = useTimezone();
  const researchDay = round.settings.research_day;

  const fetchRows = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.admin.applications(round.id);
      setRows(res.applications.map(toRow));
      setError('');
    } catch (err) {
      setError(errorText(t, err, 'admin:fetchError'));
    } finally {
      setLoading(false);
    }
  }, [round.id, t]);

  useEffect(() => {
    fetchRows();
  }, [fetchRows]);

  const handleSort = (field: SortField) => {
    if (sortField === field) setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const visibleRows = useMemo(() => {
    const q = searchQuery.toLowerCase();
    const filtered = rows.filter(
      (r) => r.game_name.toLowerCase().includes(q) || r.fid.toLowerCase().includes(q) || r.alliance.toLowerCase().includes(q),
    );
    filtered.sort((a, b) => {
      let av: string | number = a[sortField];
      let bv: string | number = b[sortField];
      if (typeof av === 'string') {
        av = av.toLowerCase();
        bv = String(bv).toLowerCase();
      }
      if (av < bv) return sortDirection === 'asc' ? -1 : 1;
      if (av > bv) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
    return filtered;
  }, [rows, searchQuery, sortField, sortDirection]);

  const handleDelete = async (row: Row) => {
    try {
      await api.admin.deleteApplication(row.id);
      setRows((rs) => rs.filter((r) => r.id !== row.id));
      setDeleting(null);
      onChanged?.();
    } catch (err) {
      setError(errorText(t, err, 'admin:deleteError'));
      setDeleting(null);
    }
  };

  const startEdit = (row: Row) =>
    setEditing({ app: row.app, game_name: row.game_name, alliance: row.alliance, furnace_level: row.furnace_level, answers: answersToForm(row.app.answers) });

  const handleSaveEdit = async () => {
    if (!editing) return;
    try {
      const updated = await api.admin.updateApplication(editing.app.id, {
        profile: { game_name: editing.game_name.trim(), alliance: editing.alliance.trim().toUpperCase(), furnace_level: editing.furnace_level || null },
        answers: formToAnswers(editing.answers),
      });
      setRows((rs) => rs.map((r) => (r.id === updated.id ? toRow(updated) : r)));
      setEditing(null);
      setError('');
    } catch (err) {
      setError(errorText(t, err, 'admin:playerUpdateError'));
    }
  };

  const handleExportJSON = async () => {
    try {
      const blob = await api.admin.ministry.exportJson(round.id);
      downloadBlob(blob, `minister_round_${round.id}_backup_${new Date().toISOString().slice(0, 10)}.json`);
    } catch (err) {
      setError(errorText(t, err, 'admin:exportError'));
    }
  };

  const handleImportJSON = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    let data: unknown;
    try {
      data = JSON.parse(await file.text());
    } catch {
      return setError(t('admin:importInvalidFile'));
    }
    if (!data || typeof data !== 'object' || !Array.isArray((data as { players?: unknown }).players)) {
      return setError(t('admin:importInvalidFile'));
    }
    try {
      const res = await api.admin.ministry.importJson(round.id, data);
      setImportMessage(
        t('admin:importSuccess', { imported: res.imported, updated: res.updated }) +
          (res.errors > 0 ? ` ${t('admin:importErrors', { n: res.errors })}` : ''),
      );
      await fetchRows();
      onChanged?.();
    } catch (err) {
      setError(errorText(t, err, 'admin:importError'));
    }
  };

  const SortButton = ({ field, label }: { field: SortField; label: string }) => (
    <button onClick={() => handleSort(field)} className="flex items-center gap-1 hover:text-accent transition-colors">
      {label}
      {sortField === field && <span className="text-xs">{sortDirection === 'asc' ? '↑' : '↓'}</span>}
    </button>
  );

  if (loading) {
    return (
      <div className="bg-dark-card rounded-xl border border-theme-border p-12 text-center">
        <p className="text-theme-dim">{t('ministry:form.loading')}</p>
      </div>
    );
  }

  const dayName = (key: string) => t(`admin:${key}`).split(' - ')[0];

  return (
    <div className="bg-dark-card rounded-xl border border-theme-border p-6" data-testid="players-panel">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-accent">{t('admin:playerManagement')}</h2>
          <p className="text-theme-dim mt-1" data-testid="players-total">
            {t('admin:totalPlayers')}: {rows.length}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleExportJSON}
            data-testid="export-json"
            className="flex items-center gap-2 px-4 py-2 bg-success text-dark-bg rounded-lg hover:bg-success/80 font-medium transition-colors"
          >
            <Download className="w-4 h-4" aria-hidden="true" />
            {t('admin:exportJSON')}
          </button>
          {!readOnly && (
            <label className="flex items-center gap-2 px-4 py-2 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors cursor-pointer">
              <Upload className="w-4 h-4" aria-hidden="true" />
              {t('admin:importJSON')}
              <input type="file" accept=".json" onChange={handleImportJSON} className="hidden" data-testid="import-json" />
            </label>
          )}
        </div>
      </div>

      <div className="mb-6">
        <label htmlFor="player-search" className="sr-only">
          {t('admin:search')}
        </label>
        <div className="relative">
          <Search className="absolute start-3 top-1/2 transform -translate-y-1/2 text-theme-dim w-5 h-5" aria-hidden="true" />
          <input
            id="player-search"
            data-testid="player-search"
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('admin:search')}
            className="w-full ps-10 pe-4 py-3 bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim focus:ring-2 focus:ring-accent focus:border-accent"
          />
        </div>
      </div>

      {importMessage && (
        <div className="mb-6 p-4 bg-success/10 border border-success/30 rounded-lg flex items-center justify-between">
          <p className="text-success">{importMessage}</p>
          <button onClick={() => setImportMessage('')} className="text-success hover:text-success/70" aria-label={t('common:close')}>
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>
      )}

      {error && (
        <div className="mb-6 p-4 bg-danger/10 border border-danger/30 rounded-lg flex items-center gap-3" role="alert">
          <AlertCircle className="w-5 h-5 text-danger" aria-hidden="true" />
          <p className="text-danger">{error}</p>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full" data-testid="players-table">
          <thead>
            <tr className="border-b-2 border-theme-border">
              <th className="text-start p-3 font-semibold text-theme-dim">
                <SortButton field="game_name" label={t('admin:gameName')} />
              </th>
              <th className="text-start p-3 font-semibold text-theme-dim">
                <SortButton field="fid" label={t('admin:fid')} />
              </th>
              <th className="text-center p-3 font-semibold text-theme-dim">
                <SortButton field="monday_points" label={dayName('monday')} />
              </th>
              <th className="text-center p-3 font-semibold text-theme-dim">
                <SortButton field="research_points" label={dayName(researchDay)} />
              </th>
              <th className="text-center p-3 font-semibold text-theme-dim">
                <SortButton field="thursday_points" label={dayName('thursday')} />
              </th>
              <th className="text-center p-3 font-semibold text-theme-dim">{t('admin:timeSlots')}</th>
              {!readOnly && <th className="text-center p-3 font-semibold text-theme-dim">{t('admin:actions')}</th>}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => (
              <tr key={row.id} className="border-b border-theme-border/50 hover:bg-dark-card-hover" data-testid={`player-row-${row.fid}`}>
                <td className="p-3 text-theme-text">
                  <div className="flex items-center gap-2">
                    {row.alliance && <span className="text-accent font-medium">[{row.alliance}]</span>} {row.game_name}
                    {row.furnace_level && (
                      <span className="px-1.5 py-0.5 rounded bg-accent/20 text-accent text-xs font-semibold" data-testid="furnace-badge">
                        {row.furnace_level}
                      </span>
                    )}
                  </div>
                </td>
                <td className="p-3 text-sm text-theme-dim">{row.fid}</td>
                <td className="p-3 text-center font-medium text-accent">{row.monday_points.toLocaleString()}</td>
                <td className="p-3 text-center font-medium text-success">{row.research_points.toLocaleString()}</td>
                <td className="p-3 text-center font-medium text-accent-light">{row.thursday_points.toLocaleString()}</td>
                <td className="p-3 text-center text-sm text-theme-dim">
                  {row.slots} {t('admin:selected')}
                </td>
                {!readOnly && (
                  <td className="p-3">
                    <div className="flex items-center justify-center gap-2">
                      <button
                        onClick={() => startEdit(row)}
                        data-testid={`edit-${row.fid}`}
                        className="p-2 text-accent hover:bg-accent/10 rounded-lg transition-colors"
                        title={t('admin:edit')}
                        aria-label={t('admin:edit')}
                      >
                        <Edit2 className="w-4 h-4" aria-hidden="true" />
                      </button>
                      <button
                        onClick={() => setDeleting(row)}
                        data-testid={`delete-${row.fid}`}
                        className="p-2 text-danger hover:bg-danger/10 rounded-lg transition-colors"
                        title={t('admin:delete')}
                        aria-label={t('admin:delete')}
                      >
                        <Trash2 className="w-4 h-4" aria-hidden="true" />
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>

        {visibleRows.length === 0 && <div className="text-center py-12 text-theme-dim">{t('admin:noPlayersFound')}</div>}
      </div>

      {editing && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-player-title"
            data-testid="edit-dialog"
            className="bg-dark-card rounded-xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto border border-theme-border"
          >
            <div className="flex items-center justify-between mb-6">
              <h3 id="edit-player-title" className="text-2xl font-bold text-accent">
                {t('admin:editPlayer')}
              </h3>
              <button onClick={() => setEditing(null)} className="text-theme-dim hover:text-theme-text" aria-label={t('common:close')}>
                <X className="w-6 h-6" aria-hidden="true" />
              </button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <Field
                  id="edit-game-name"
                  className="col-span-2"
                  label={t('admin:gameName')}
                  value={editing.game_name}
                  onChange={(e) => setEditing({ ...editing, game_name: e.target.value })}
                />
                <Field
                  id="edit-alliance"
                  label={t('admin:allianceLabel')}
                  maxLength={3}
                  inputClassName="uppercase"
                  placeholder={t('profile:alliancePlaceholder')}
                  value={editing.alliance}
                  onChange={(e) => setEditing({ ...editing, alliance: e.target.value.toUpperCase().slice(0, 3) })}
                />
              </div>
              <FurnaceLevelSelect
                id="edit-furnace-level"
                label={t('profile:furnaceLevel')}
                value={editing.furnace_level}
                onChange={(code) => setEditing({ ...editing, furnace_level: code })}
              />

              <div className="grid grid-cols-2 gap-4">
                {[...ADMIN_NUMBER_FIELDS, ...(round.settings.show_fire_crystals ? CRYSTAL_FIELDS : [])].map(({ key, label }) => (
                  <Field
                    key={key}
                    id={`edit-${key}`}
                    type="number"
                    min={0}
                    step={key.includes('speedups') ? 0.1 : 1}
                    placeholder="0"
                    label={t(label)}
                    value={editing.answers[key]}
                    onChange={(e) => setEditing({ ...editing, answers: { ...editing.answers, [key]: e.target.value } })}
                  />
                ))}
              </div>

              <div className="mt-6">
                <p className="block text-sm font-medium text-theme-text mb-2">{t('ministry:form.timePreferences')}</p>
                <TimeSlotPicker
                  compact
                  value={editing.answers.time_slots_by_day}
                  onChange={(next) => setEditing({ ...editing, answers: { ...editing.answers, time_slots_by_day: next } })}
                  researchDay={researchDay}
                  timezone={timezone}
                  onTimezoneChange={setTimezone}
                />
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  onClick={handleSaveEdit}
                  data-testid="save-edit"
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium"
                >
                  <Save className="w-5 h-5" aria-hidden="true" />
                  {t('common:save')}
                </button>
                <button
                  onClick={() => setEditing(null)}
                  className="flex-1 px-4 py-3 bg-dark-bg text-theme-text rounded-lg hover:bg-dark-card-hover font-medium border border-theme-border"
                >
                  {t('common:cancel')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {deleting && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-title"
            className="bg-dark-card rounded-xl p-6 max-w-md w-full border border-theme-border"
          >
            <h3 id="delete-title" className="text-xl font-bold text-theme-text mb-2">
              {t('admin:confirmDelete')}
            </h3>
            <p className="text-theme-dim text-sm mb-4">
              {deleting.alliance && `[${deleting.alliance}] `}
              {deleting.game_name} ({deleting.fid}) — {t('admin:deleteApplicationNote')}
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => handleDelete(deleting)}
                data-testid="confirm-delete"
                className="flex-1 px-4 py-3 bg-danger text-white rounded-lg hover:bg-danger-dark font-medium"
              >
                {t('common:yes')}
              </button>
              <button
                onClick={() => setDeleting(null)}
                className="flex-1 px-4 py-3 bg-dark-bg text-theme-text rounded-lg hover:bg-dark-card-hover font-medium border border-theme-border"
              >
                {t('common:no')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
