import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { FileText, Shield, Clock, Sparkles, CalendarOff, ArrowLeft, HelpCircle } from 'lucide-react';
import api, { Round, isApiError } from '../../shared/api';
import { TyrantSettings, tyrantApi } from './api';
import { TYRANT_PATHS } from './paths';
import { usePageTitle } from '../../shared/usePageTitle';
import Tile, { LinkButton, PageHero } from '../../shared/Tile';
import { useFormatDateTime } from '../../shared/DateTime';
import { useTimezone } from '../../shared/TimezoneContext';
import { timezoneShortLabel } from '../../shared/timezone';

// Frost Dragon Tyrant landing page (same layout as the ministry home).
export default function TyrantPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const fmt = useFormatDateTime();
  const { timezone } = useTimezone();
  const [stateNumber, setStateNumber] = useState('');
  const [round, setRound] = useState<Round<TyrantSettings> | null>(null);
  const [noRound, setNoRound] = useState(false);
  const [isClosed, setIsClosed] = useState(false);
  usePageTitle(t('tyrant:name'));

  useEffect(() => {
    api.publicSettings()
      .then((s) => setStateNumber(s.state_number || ''))
      .catch(() => {});
    tyrantApi
      .currentRound()
      .then((r) => {
        setRound(r);
        setIsClosed(r.is_closed_for_new);
      })
      .catch((e) => {
        if (isApiError(e, 'NO_CURRENT_ROUND')) setNoRound(true);
      });
  }, []);

  const closingTime = round?.closing_time ?? '';
  useEffect(() => {
    if (!closingTime) return;
    const check = () => setIsClosed(new Date() >= new Date(closingTime));
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, [closingTime]);

  return (
    <div className="min-h-[70vh] flex items-start sm:items-center justify-center px-3 py-4 sm:p-4">
      <div className="max-w-4xl w-full">
        <div className="text-center mb-4">
          {stateNumber && (
            <p className="text-lg sm:text-2xl text-theme-text font-semibold" data-testid="welcome">
              {t('tyrant:home.welcome', { state: stateNumber })}
            </p>
          )}
          {round && (
            <p className="mt-2 text-theme-text" data-testid="current-round">
              {t('tyrant:home.currentRound', { round: round.name })}
            </p>
          )}
          {closingTime && (
            <div data-testid="closing-time-banner" className={`mt-2 flex items-center justify-center gap-2 text-sm font-medium ${isClosed ? 'text-danger' : 'text-success'}`}>
              <Clock className="w-4 h-4" aria-hidden="true" />
              {isClosed ? t('tyrant:home.closed') : t('tyrant:home.closeAt', { time: fmt(closingTime) })}
            </div>
          )}
        </div>

        <PageHero title={t('tyrant:name')} subtitle={t('tyrant:home.subtitle')} />

        {noRound && (
          <div
            className="mb-6 sm:mb-8 p-4 sm:p-5 rounded-2xl border border-theme-border bg-dark-card flex items-center justify-center gap-3 text-center"
            data-testid="no-round-banner"
          >
            <CalendarOff className="w-6 h-6 text-theme-dim shrink-0" aria-hidden="true" />
            <p className="text-theme-text">{t('tyrant:apply.notOpenBody')}</p>
          </div>
        )}

        <div className="max-w-md mx-auto">
          <Tile
            testId="tyrant-apply-tile"
            onClick={() => !noRound && navigate(TYRANT_PATHS.apply)}
            disabled={noRound}
            icon={FileText}
            title={t('tyrant:home.applyTile')}
            description={
              noRound
                ? t('tyrant:apply.notOpenTitle')
                : isClosed
                  ? t('tyrant:home.applyTileClosedDesc')
                  : t('tyrant:home.applyTileDesc')
            }
          />
        </div>

        <div className="mt-4 sm:mt-6 flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
          <LinkButton icon={HelpCircle} accent onClick={() => navigate(TYRANT_PATHS.guide)} testId="tyrant-guide-link">
            {t('guide:common.playerLink')}
          </LinkButton>
          <LinkButton icon={ArrowLeft} accent flipInRtl onClick={() => navigate('/')}>
            {t('common:nav.home')}
          </LinkButton>
          <LinkButton icon={Sparkles} onClick={() => navigate('/changelog')}>
            {t('changelog:linkText')}
          </LinkButton>
        </div>

        {/* Event Management: a small, muted link for organisers, not a second big card */}
        <div className="mt-2 flex justify-center">
          <LinkButton icon={Shield} onClick={() => navigate(TYRANT_PATHS.admin)} testId="tyrant-admin-tile" muted>
            {t('admin:title')}
          </LinkButton>
        </div>

        <p className="mt-2 text-center text-theme-dim text-sm" data-testid="times-shown-in">
          {t('common:timesShownIn', { zone: timezoneShortLabel(timezone) })}
        </p>
      </div>
    </div>
  );
}
