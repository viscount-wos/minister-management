import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LogOut, Users, Calendar, HelpCircle, Settings, RefreshCw, Lock, AlertCircle } from 'lucide-react';
import api, { Round, adminSession, onUnauthorized } from '../../../shared/api';
import { errorText } from '../../../shared/apiErrors';
import PlayerManagement from './PlayerManagement';
import AssignmentManagement from './AssignmentManagement';
import AdminSettings from './AdminSettings';
import StartNewRoundDialog from './StartNewRoundDialog';
import { MINISTRY_PATHS } from '../paths';

type Tab = 'players' | 'assignments' | 'settings';

/** Rounds other than the open/draft ones are history: viewable, not editable. */
export const isReadOnlyRound = (r: Round | null) => !r || r.status === 'closed';

export default function AdminDashboard() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<Tab>('players');
  const [rounds, setRounds] = useState<Round[] | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showStart, setShowStart] = useState(false);
  const [error, setError] = useState('');
  const hasToken = !!adminSession.token();

  // A 401 anywhere (missing / forged / expired token) -> back to login.
  useEffect(() => {
    if (!hasToken) {
      navigate('/admin', { replace: true });
      return;
    }
    return onUnauthorized(() => navigate('/admin?expired=1', { replace: true }));
  }, [hasToken, navigate]);

  const loadRounds = useCallback(
    async (select?: number) => {
      try {
        const res = await api.admin.rounds('ministry');
        setRounds(res.rounds);
        const open = res.rounds.find((r) => r.status === 'open');
        setSelectedId((prev) => {
          const want = select ?? prev;
          if (want && res.rounds.some((r) => r.id === want)) return want;
          return open?.id ?? res.rounds[0]?.id ?? null;
        });
      } catch (e) {
        setError(errorText(t, e, 'admin:round.loadError'));
      }
    },
    [t],
  );

  useEffect(() => {
    if (hasToken) loadRounds();
  }, [hasToken, loadRounds]);

  const handleLogout = () => {
    adminSession.clear();
    navigate(MINISTRY_PATHS.home);
  };

  const onRoundUpdated = (r: Round) =>
    setRounds((rs) => (rs ? rs.map((x) => (x.id === r.id ? { ...x, ...r, application_count: x.application_count } : x)) : rs));

  if (!hasToken) return null;

  const round = rounds?.find((r) => r.id === selectedId) ?? null;
  const currentOpen = rounds?.find((r) => r.status === 'open') ?? null;
  const readOnly = isReadOnlyRound(round);

  const tabButton = (tab: Tab, Icon: typeof Users, label: string) => (
    <button
      onClick={() => setActiveTab(tab)}
      data-testid={`tab-${tab}`}
      role="tab"
      aria-selected={activeTab === tab}
      className={`flex items-center gap-2 px-4 py-3 font-medium transition-colors border-b-2 ${
        activeTab === tab ? 'border-accent text-accent' : 'border-transparent text-theme-dim hover:text-theme-text'
      }`}
    >
      <Icon className="w-5 h-5" aria-hidden="true" />
      {label}
    </button>
  );

  return (
    <div className="min-h-screen bg-dark-bg py-8 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="bg-dark-card rounded-xl border border-theme-border p-6 mb-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold text-accent">{t('admin:title')}</h1>
              <p className="text-theme-dim mt-1">{t('admin:managePlayers')}</p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate('/admin/guide')}
                className="flex items-center gap-2 px-4 py-2 bg-accent/20 text-accent rounded-lg hover:bg-accent/30 transition-colors"
              >
                <HelpCircle className="w-5 h-5" aria-hidden="true" />
                {t('guide:admin.linkText')}
              </button>
              <button
                onClick={handleLogout}
                data-testid="admin-logout"
                className="flex items-center gap-2 px-4 py-2 bg-danger text-white rounded-lg hover:bg-danger-dark transition-colors"
              >
                <LogOut className="w-5 h-5" aria-hidden="true" />
                {t('admin:logout')}
              </button>
            </div>
          </div>

          {/* Round selector: current round by default; past rounds are read-only */}
          <div className="mt-6 flex flex-wrap items-end gap-4">
            <div>
              <label htmlFor="round-select" className="block text-sm font-medium text-theme-text mb-1">
                {t('admin:round.label')}
              </label>
              <select
                id="round-select"
                data-testid="round-select"
                value={selectedId ?? ''}
                disabled={!rounds || rounds.length === 0}
                onChange={(e) => setSelectedId(Number(e.target.value))}
                className="px-3 py-2 bg-dark-input border border-theme-border rounded-lg text-theme-text min-w-[18rem] focus:ring-2 focus:ring-accent focus:border-accent"
              >
                {rounds?.length === 0 && <option value="">{t('admin:round.none')}</option>}
                {rounds?.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} — {t(`admin:round.status.${r.status}`)} ({t('admin:round.applicationCount', { n: r.application_count ?? 0 })})
                  </option>
                ))}
              </select>
            </div>
            {round && (
              <span
                data-testid="round-status"
                data-status={round.status}
                className={`px-3 py-1 rounded-full text-xs font-semibold ${
                  round.status === 'open' ? 'bg-success/20 text-success' : 'bg-dark-input border border-theme-border text-theme-dim'
                }`}
              >
                {t(`admin:round.status.${round.status}`)}
              </span>
            )}
            <button
              onClick={() => setShowStart(true)}
              data-testid="start-new-round"
              disabled={!rounds}
              className="ms-auto flex items-center gap-2 px-4 py-2 bg-warning/20 text-warning border border-warning/40 rounded-lg hover:bg-warning/30 font-medium transition-colors disabled:opacity-50"
            >
              <RefreshCw className="w-4 h-4" aria-hidden="true" />
              {t('admin:round.start')}
            </button>
          </div>

          {round && readOnly && (
            <div
              className="mt-4 p-3 bg-warning/10 border border-warning/30 rounded-lg flex items-center gap-2 text-warning text-sm"
              data-testid="read-only-banner"
            >
              <Lock className="w-4 h-4 shrink-0" aria-hidden="true" />
              {t('admin:round.readOnly')}
            </div>
          )}
          {rounds?.length === 0 && (
            <div className="mt-4 p-3 bg-accent/10 border border-accent/30 rounded-lg text-accent text-sm" data-testid="no-rounds">
              {t('admin:round.noRoundsYet')}
            </div>
          )}
          {error && (
            <div className="mt-4 p-3 bg-danger/10 border border-danger/30 rounded-lg flex items-center gap-2 text-danger" role="alert">
              <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
              {error}
            </div>
          )}

          <div className="flex gap-4 mt-6 border-b border-theme-border" role="tablist">
            {tabButton('players', Users, t('admin:players'))}
            {tabButton('assignments', Calendar, t('admin:assignments'))}
            {tabButton('settings', Settings, t('admin:settings'))}
          </div>
        </div>

        {activeTab === 'players' &&
          (round ? <PlayerManagement key={round.id} round={round} readOnly={readOnly} onChanged={() => loadRounds()} /> : <NoRoundCard />)}
        {activeTab === 'assignments' &&
          (round ? <AssignmentManagement key={round.id} round={round} readOnly={readOnly} onRoundUpdated={onRoundUpdated} /> : <NoRoundCard />)}
        {activeTab === 'settings' && (
          <AdminSettings key={round?.id ?? 'none'} round={round} readOnly={readOnly} onRoundUpdated={onRoundUpdated} />
        )}
      </div>

      {showStart && (
        <StartNewRoundDialog
          currentRound={currentOpen}
          onClose={() => setShowStart(false)}
          onStarted={(r) => {
            setShowStart(false);
            loadRounds(r.id);
          }}
        />
      )}
    </div>
  );
}

function NoRoundCard() {
  const { t } = useTranslation();
  return (
    <div className="bg-dark-card rounded-xl border border-theme-border p-12 text-center text-theme-dim">
      {t('admin:round.noRoundsYet')}
    </div>
  );
}
