import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { FileText, Shield, Clock, Sparkles, CalendarOff, ArrowLeft, HelpCircle } from 'lucide-react';
import api, { Round, isApiError } from '../../shared/api';
import { SvsSettings, svsApi } from './api';
import { SVS_PATHS } from './paths';
import { usePageTitle } from '../../shared/usePageTitle';
import Tile, { LinkButton, PageHero } from '../../shared/Tile';
import { useFormatDateTime } from '../../shared/DateTime';
import { useTimezone } from '../../shared/TimezoneContext';
import { timezoneShortLabel } from '../../shared/timezone';

// SVS landing page (same layout as Frost Dragon Tyrant's). Generic sign-up strings are shared with the Tyrant
// namespace (tyrant:home.*); SVS wording lives in svs:*.
export default function SvsPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const fmt = useFormatDateTime();
  const { timezone } = useTimezone();
  const [stateNumber, setStateNumber] = useState('');
  const [round, setRound] = useState<Round<SvsSettings> | null>(null);
  const [noRound, setNoRound] = useState(false);
  const [isClosed, setIsClosed] = useState(false);
  usePageTitle(t('svs:name'));

  useEffect(() => {
    api.publicSettings()
      .then((s) => setStateNumber(s.state_number || ''))
      .catch(() => {});
    svsApi
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

        <PageHero title={t('svs:name')} subtitle={t('svs:home.subtitle')} />

        {noRound && (
          <div
            className="mb-6 sm:mb-8 p-4 sm:p-5 rounded-2xl border border-theme-border bg-dark-card flex items-center justify-center gap-3 text-center"
            data-testid="no-round-banner"
          >
            <CalendarOff className="w-6 h-6 text-theme-dim shrink-0" aria-hidden="true" />
            <p className="text-theme-text">{t('svs:apply.notOpenBody')}</p>
          </div>
        )}

        <div className="max-w-md mx-auto">
          <Tile
            testId="svs-apply-tile"
            onClick={() => !noRound && navigate(SVS_PATHS.apply)}
            disabled={noRound}
            icon={FileText}
            title={t('tyrant:home.applyTile')}
            description={
              noRound
                ? t('svs:apply.notOpenTitle')
                : isClosed
                  ? t('tyrant:home.applyTileClosedDesc')
                  : t('tyrant:home.applyTileDesc')
            }
          />
        </div>

        <div className="mt-4 sm:mt-6 flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
          <LinkButton icon={HelpCircle} accent onClick={() => navigate(SVS_PATHS.guide)} testId="svs-guide-link">
            {t('common:guideLinks.playerLink')}
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
          <LinkButton icon={Shield} onClick={() => navigate(SVS_PATHS.admin)} testId="svs-admin-tile" muted>
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
