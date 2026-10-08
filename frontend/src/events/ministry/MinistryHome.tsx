import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { FileText, Shield, Calendar, HelpCircle, Clock, Sparkles, CalendarOff } from 'lucide-react';
import api, { MinistrySettings, Round, isApiError } from '../../shared/api';
import { activeDaysInOrder, sortDaysByWeek } from '../../shared/days';
import { MINISTRY_PATHS } from './paths';
import { usePageTitle } from '../../shared/usePageTitle';

export default function MinistryHome() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [stateNumber, setStateNumber] = useState('');
  const [round, setRound] = useState<Round<MinistrySettings> | null>(null);
  const [noRound, setNoRound] = useState(false);
  const [isClosed, setIsClosed] = useState(false);
  usePageTitle(t('ministry:event.name'));

  useEffect(() => {
    api.publicSettings()
      .then((s) => setStateNumber(s.state_number || ''))
      .catch(() => {});
    api.currentRound<MinistrySettings>('ministry')
      .then((r) => {
        setRound(r);
        setIsClosed(r.is_closed_for_new);
      })
      .catch((e) => {
        if (isApiError(e, 'NO_CURRENT_ROUND')) setNoRound(true);
      });
  }, []);

  // Client-side check every 30s so the banner flips when the closing time passes.
  const closingTime = round?.closing_time ?? '';
  useEffect(() => {
    if (!closingTime) return;
    const check = () => setIsClosed(new Date() >= new Date(closingTime));
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, [closingTime]);

  // Only the round's active days (see docs/BACKEND_ISSUES.md #1: a stale research day can linger).
  const publishedDays = sortDaysByWeek(
    (round?.settings.published_days ?? []).filter((d) => activeDaysInOrder(round?.settings.research_day ?? 'tuesday').includes(d)),
  );

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="max-w-4xl w-full">
        <div className="text-center mb-4">
          {stateNumber && (
            <p className="text-2xl text-theme-text font-semibold" data-testid="welcome">
              {t('ministry:home.welcome', { state: stateNumber })}
            </p>
          )}
          {round && (
            <p className="mt-2 text-theme-text" data-testid="current-round">
              {t('ministry:home.currentRound', { round: round.name })}
            </p>
          )}
          {closingTime && (
            <div
              className={`mt-2 flex items-center justify-center gap-2 text-sm font-medium ${isClosed ? 'text-danger' : 'text-success'}`}
            >
              <Clock className="w-4 h-4" aria-hidden="true" />
              {isClosed
                ? t('ministry:home.applicationsClosed')
                : t('ministry:home.applicationsCloseAt', { time: new Date(closingTime).toLocaleString() })}
            </div>
          )}
        </div>

        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-accent mb-4">{t('ministry:home.title')}</h1>
          <p className="text-xl text-theme-dim">{t('ministry:home.subtitle')}</p>
        </div>

        {noRound && (
          <div
            className="mb-8 p-5 rounded-2xl border border-theme-border bg-dark-card flex items-center justify-center gap-3 text-center"
            data-testid="no-round-banner"
          >
            <CalendarOff className="w-6 h-6 text-theme-dim shrink-0" aria-hidden="true" />
            <p className="text-theme-text">{t('ministry:apply.notOpenBody')}</p>
          </div>
        )}

        {publishedDays.length > 0 && (
          <div className="mb-8 space-y-3">
            {publishedDays.map((day) => (
              <button
                key={day}
                data-testid={`schedule-link-${day}`}
                onClick={() => navigate(MINISTRY_PATHS.schedule(day))}
                className="w-full bg-accent/10 border-2 border-accent/40 rounded-2xl p-5 hover:bg-accent/20 transition-all duration-300 group"
              >
                <div className="flex items-center justify-center gap-4">
                  <Calendar className="w-7 h-7 text-accent" aria-hidden="true" />
                  <div className="text-center">
                    <h2 className="text-lg font-bold text-accent">{t('ministry:schedule.viewSchedule')}</h2>
                    <p className="text-theme-dim">{t(`admin:${day}`)}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-6">
          {/* Apply or edit: one FID-first flow decides "new" vs "edit". */}
          <button
            onClick={() => !noRound && navigate(MINISTRY_PATHS.apply)}
            disabled={noRound}
            data-testid="ministry-apply-tile"
            className={`bg-dark-card rounded-2xl p-8 border border-theme-border transition-all duration-300 group ${
              noRound ? 'opacity-50 cursor-not-allowed' : 'hover:bg-dark-card-hover transform hover:-translate-y-2'
            }`}
          >
            <div className="flex flex-col items-center text-center">
              <div
                className={`w-20 h-20 rounded-full flex items-center justify-center mb-6 transition-colors ${
                  noRound ? 'bg-theme-dim/20' : 'bg-accent/20 group-hover:bg-accent/30'
                }`}
              >
                <FileText className={`w-10 h-10 ${noRound ? 'text-theme-dim' : 'text-accent'}`} aria-hidden="true" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text mb-3">{t('ministry:home.applyTile')}</h2>
              <p className="text-theme-dim">
                {noRound
                  ? t('ministry:apply.notOpenTitle')
                  : isClosed
                    ? t('ministry:home.applyTileClosedDesc')
                    : t('ministry:home.applyTileDesc')}
              </p>
            </div>
          </button>

          <button
            onClick={() => navigate(MINISTRY_PATHS.admin)}
            data-testid="ministry-admin-tile"
            className="bg-dark-card rounded-2xl p-8 border border-theme-border hover:bg-dark-card-hover transform hover:-translate-y-2 transition-all duration-300 group"
          >
            <div className="flex flex-col items-center text-center">
              <div className="w-20 h-20 bg-accent/20 rounded-full flex items-center justify-center mb-6 group-hover:bg-accent/30 transition-colors">
                <Shield className="w-10 h-10 text-accent" aria-hidden="true" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text mb-3">{t('admin:title')}</h2>
              <p className="text-theme-dim">{t('ministry:home.adminDesc')}</p>
            </div>
          </button>
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-3">
          <button
            onClick={() => navigate(MINISTRY_PATHS.guide)}
            className="inline-flex items-center gap-2 text-accent hover:text-accent-dim transition-colors text-sm font-medium"
          >
            <HelpCircle className="w-4 h-4" aria-hidden="true" />
            {t('guide:player.linkText')}
          </button>
          <button
            onClick={() => navigate('/changelog')}
            className="inline-flex items-center gap-2 text-theme-dim hover:text-accent transition-colors text-sm font-medium"
          >
            <Sparkles className="w-4 h-4" aria-hidden="true" />
            {t('changelog:linkText')}
          </button>
        </div>

        <div className="mt-4 text-center text-theme-dim text-sm">
          <p>{t('ministry:home.utcNote')}</p>
        </div>
      </div>
    </div>
  );
}
