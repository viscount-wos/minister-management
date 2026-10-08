import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LogOut, HelpCircle, RefreshCw, Lock, AlertCircle, Pencil } from 'lucide-react';
import api, { Round, adminSession, onUnauthorized } from '../shared/api';
import { errorText } from '../shared/apiErrors';
import { usePageTitle } from '../shared/usePageTitle';
import StartNewRoundDialog from './StartNewRoundDialog';
import RenameRound from './RenameRound';
import AdminEventSwitch from './AdminEventSwitch';
import { resolveAdminEvent } from './registry';
import { ADMIN_PATHS, lastAdminEvent } from './paths';
import type { AdminEventModule } from './types';

/** Rounds other than the open/draft ones are history: viewable, not editable. */
export const isReadOnlyRound = (r: Round | null) => !r || r.status === 'closed';

/**
 * "Event Management": the one admin dashboard for every event.
 * /admin/dashboard?event=<key>; the shared chrome (title, contextual subtitle,
 * event switch, guide, logout, round selector, Start new round, read-only
 * banner, tab bar) lives here and the event's tabs plug in from the registry.
 */
export default function AdminShell() {
  const [params, setParams] = useSearchParams();
  const event = resolveAdminEvent(params.get('event'));

  // Keep ?event= explicit in the URL (old /admin/dashboard links resolve here).
  useEffect(() => {
    if (params.get('event') !== event.key) {
      const next = new URLSearchParams(params);
      next.set('event', event.key);
      setParams(next, { replace: true });
    }
  }, [params, event.key, setParams]);

  // Remount per event so rounds, selection and tab start fresh on a switch.
  return <EventDashboard key={event.key} event={event} />;
}

function EventDashboard({ event }: { event: AdminEventModule }) {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const [activeTab, setActiveTab] = useState(event.tabs[0].key);
  const [rounds, setRounds] = useState<Round[] | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showStart, setShowStart] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [error, setError] = useState('');
  const hasToken = !!adminSession.token();

  usePageTitle(t(event.label), t('admin:title'));

  // A 401 anywhere (missing / forged / expired token) -> login, then back to this event.
  useEffect(() => {
    if (!hasToken) {
      navigate(ADMIN_PATHS.login(event.key), { replace: true });
      return;
    }
    lastAdminEvent.set(event.key);
    return onUnauthorized(() => navigate(ADMIN_PATHS.login(event.key, true), { replace: true }));
  }, [hasToken, navigate, event.key]);

  const loadRounds = useCallback(
    async (select?: number) => {
      try {
        const res = await api.admin.rounds(event.key);
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
    [t, event.key],
  );

  useEffect(() => {
    if (hasToken) loadRounds();
  }, [hasToken, loadRounds]);

  const handleLogout = () => {
    adminSession.clear();
    navigate(event.publicPath);
  };

  const onRoundUpdated = useCallback(
    (r: Round) =>
      setRounds((rs) => (rs ? rs.map((x) => (x.id === r.id ? { ...x, ...r, application_count: x.application_count } : x)) : rs)),
    [],
  );

  if (!hasToken) return null;

  const round = rounds?.find((r) => r.id === selectedId) ?? null;
  const currentOpen = rounds?.find((r) => r.status === 'open') ?? null;
  const readOnly = isReadOnlyRound(round);
  const tab = event.tabs.find((x) => x.key === activeTab) ?? event.tabs[0];
  const EventIcon = event.icon;

  return (
    <div className="min-h-screen bg-dark-bg py-3 sm:py-8 px-2 sm:px-4" data-testid="admin-shell" data-event={event.key}>
      <div className={`${tab.wide ? 'max-w-[110rem]' : 'max-w-7xl'} mx-auto`} data-testid={`${event.key}-admin`}>
        <div className="bg-dark-card rounded-xl border border-theme-border p-3 sm:p-6 mb-4 sm:mb-6">
          <div className="mb-4">
            <AdminEventSwitch current={event.key} hrefFor={ADMIN_PATHS.dashboard} />
          </div>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-accent" data-testid="admin-title">
                {t('admin:title')}
              </h1>
              <p className="text-theme-dim mt-1 flex items-center gap-2" data-testid="admin-subtitle">
                <EventIcon className="w-4 h-4 shrink-0" aria-hidden="true" />
                {t(event.subtitle)}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 sm:gap-3">
              <button
                onClick={() => navigate(ADMIN_PATHS.guide(event.key))}
                data-testid="admin-guide-link"
                className="flex items-center gap-2 min-h-[44px] px-4 py-2 bg-accent/20 text-accent rounded-lg hover:bg-accent/30 transition-colors"
              >
                <HelpCircle className="w-5 h-5" aria-hidden="true" />
                {t('guide:admin.linkText')}
              </button>
              <button
                onClick={handleLogout}
                data-testid="admin-logout"
                className="flex items-center gap-2 min-h-[44px] px-4 py-2 bg-danger text-white rounded-lg hover:bg-danger-dark transition-colors"
              >
                <LogOut className="w-5 h-5" aria-hidden="true" />
                {t('admin:logout')}
              </button>
            </div>
          </div>

          {/* Round selector: current round by default; past rounds are read-only */}
          <div className="mt-4 sm:mt-6 flex flex-wrap items-end gap-3 sm:gap-4">
            <div className="w-full sm:w-auto min-w-0">
              <label htmlFor="round-select" className="block text-sm font-medium text-theme-text mb-1">
                {t('admin:round.label')}
              </label>
              <select
                id="round-select"
                data-testid="round-select"
                value={selectedId ?? ''}
                disabled={!rounds || rounds.length === 0}
                onChange={(e) => {
                  setSelectedId(Number(e.target.value));
                  setRenaming(false);
                }}
                className="w-full sm:w-auto sm:min-w-[18rem] max-w-full min-h-[44px] px-3 py-2 text-base sm:text-sm bg-dark-input border border-theme-border rounded-lg text-theme-text focus:ring-2 focus:ring-accent focus:border-accent"
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
            {round && !renaming && (
              <button
                type="button"
                onClick={() => setRenaming(true)}
                data-testid="rename-round"
                className="flex items-center gap-2 min-h-[44px] px-3 py-2 text-sm text-theme-dim hover:text-accent border border-theme-border rounded-lg transition-colors"
              >
                <Pencil className="w-4 h-4" aria-hidden="true" />
                {t('admin:round.rename')}
              </button>
            )}
            <button
              onClick={() => setShowStart(true)}
              data-testid="start-new-round"
              disabled={!rounds}
              className="ms-auto flex items-center gap-2 min-h-[44px] px-4 py-2 bg-warning/20 text-warning border border-warning/40 rounded-lg hover:bg-warning/30 font-medium transition-colors disabled:opacity-50"
            >
              <RefreshCw className="w-4 h-4" aria-hidden="true" />
              {t('admin:round.start')}
            </button>
          </div>

          {round && renaming && (
            <RenameRound
              key={round.id}
              round={round}
              onCancel={() => setRenaming(false)}
              onRenamed={(r) => {
                onRoundUpdated(r);
                setRenaming(false);
              }}
            />
          )}

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

          <div className="flex gap-1 sm:gap-4 mt-4 sm:mt-6 border-b border-theme-border overflow-x-auto" role="tablist">
            {event.tabs.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                data-testid={`tab-${key}`}
                role="tab"
                aria-selected={tab.key === key}
                className={`shrink-0 whitespace-nowrap flex items-center gap-2 min-h-[44px] px-3 sm:px-4 py-3 font-medium transition-colors border-b-2 ${
                  tab.key === key ? 'border-accent text-accent' : 'border-transparent text-theme-dim hover:text-theme-text'
                }`}
              >
                <Icon className="w-5 h-5" aria-hidden="true" />
                {t(label)}
              </button>
            ))}
          </div>
        </div>

        {tab.needsRound && !round ? (
          <div className="bg-dark-card rounded-xl border border-theme-border p-6 sm:p-12 text-center text-theme-dim">
            {t('admin:round.noRoundsYet')}
          </div>
        ) : (
          tab.render({ round, readOnly, reloadRounds: (select) => void loadRounds(select), onRoundUpdated, selectTab: setActiveTab })
        )}
      </div>

      {showStart && (
        <StartNewRoundDialog
          event={event.key}
          defaultName={event.defaultRoundName?.(t, new Date().toLocaleDateString(i18n.language))}
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
