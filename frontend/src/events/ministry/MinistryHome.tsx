import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { FileText, Shield, Calendar, HelpCircle, Clock, Sparkles, CalendarOff } from 'lucide-react';
import api, { MinistrySettings, Round, isApiError } from '../../shared/api';
import { activeDaysInOrder, sortDaysByWeek } from '../../shared/days';
import { MINISTRY_PATHS } from './paths';
import { usePageTitle } from '../../shared/usePageTitle';
import Tile, { LinkButton, PageHero } from '../../shared/Tile';

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
    <div className="min-h-[70vh] flex items-start sm:items-center justify-center px-3 py-4 sm:p-4">
      <div className="max-w-4xl w-full">
        <div className="text-center mb-4">
          {stateNumber && (
            <p className="text-lg sm:text-2xl text-theme-text font-semibold" data-testid="welcome">
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

        <PageHero title={t('ministry:home.title')} subtitle={t('ministry:home.subtitle')} />

        {noRound && (
          <div
            className="mb-6 sm:mb-8 p-4 sm:p-5 rounded-2xl border border-theme-border bg-dark-card flex items-center justify-center gap-3 text-center"
            data-testid="no-round-banner"
          >
            <CalendarOff className="w-6 h-6 text-theme-dim shrink-0" aria-hidden="true" />
            <p className="text-theme-text">{t('ministry:apply.notOpenBody')}</p>
          </div>
        )}

        {publishedDays.length > 0 && (
          <div className="mb-6 sm:mb-8 space-y-3">
            {publishedDays.map((day) => (
              <button
                key={day}
                data-testid={`schedule-link-${day}`}
                onClick={() => navigate(MINISTRY_PATHS.schedule(day))}
                className="w-full bg-accent/10 border-2 border-accent/40 rounded-2xl p-4 sm:p-5 hover:bg-accent/20 transition-all duration-300 group"
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

        <div className="grid md:grid-cols-2 gap-3 sm:gap-6">
          {/* Apply or edit: one FID-first flow decides "new" vs "edit". */}
          <Tile
            testId="ministry-apply-tile"
            onClick={() => !noRound && navigate(MINISTRY_PATHS.apply)}
            disabled={noRound}
            icon={FileText}
            title={t('ministry:home.applyTile')}
            description={
              noRound
                ? t('ministry:apply.notOpenTitle')
                : isClosed
                  ? t('ministry:home.applyTileClosedDesc')
                  : t('ministry:home.applyTileDesc')
            }
          />
          <Tile
            testId="ministry-admin-tile"
            onClick={() => navigate(MINISTRY_PATHS.admin)}
            icon={Shield}
            title={t('admin:title')}
            description={t('ministry:home.adminDesc')}
          />
        </div>

        <div className="mt-4 sm:mt-6 flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
          <LinkButton icon={HelpCircle} accent onClick={() => navigate(MINISTRY_PATHS.guide)}>
            {t('guide:player.linkText')}
          </LinkButton>
          <LinkButton icon={Sparkles} onClick={() => navigate('/changelog')}>
            {t('changelog:linkText')}
          </LinkButton>
        </div>

        <div className="mt-4 text-center text-theme-dim text-sm">
          <p>{t('ministry:home.utcNote')}</p>
        </div>
      </div>
    </div>
  );
}
