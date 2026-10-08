import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { FileText, Shield, Clock, Sparkles, CalendarOff, ArrowLeft } from 'lucide-react';
import api, { Round, isApiError } from '../../shared/api';
import { TyrantSettings, tyrantApi } from './api';
import { TYRANT_PATHS } from './paths';

// Frost Dragon Tyrant landing page (same layout as the ministry home).
export default function TyrantPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [stateNumber, setStateNumber] = useState('2694');
  const [round, setRound] = useState<Round<TyrantSettings> | null>(null);
  const [noRound, setNoRound] = useState(false);
  const [isClosed, setIsClosed] = useState(false);

  useEffect(() => {
    api.publicSettings()
      .then((s) => setStateNumber(s.state_number || '2694'))
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
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="max-w-4xl w-full">
        <div className="text-center mb-4">
          <p className="text-2xl text-theme-text font-semibold">{t('tyrant:home.welcome', { state: stateNumber })}</p>
          {round && (
            <p className="mt-2 text-theme-text" data-testid="current-round">
              {t('tyrant:home.currentRound', { round: round.name })}
            </p>
          )}
          {closingTime && (
            <div className={`mt-2 flex items-center justify-center gap-2 text-sm font-medium ${isClosed ? 'text-danger' : 'text-success'}`}>
              <Clock className="w-4 h-4" aria-hidden="true" />
              {isClosed ? t('tyrant:home.closed') : t('tyrant:home.closeAt', { time: new Date(closingTime).toLocaleString() })}
            </div>
          )}
        </div>

        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-accent mb-4">{t('tyrant:name')}</h1>
          <p className="text-xl text-theme-dim">{t('tyrant:home.subtitle')}</p>
        </div>

        {noRound && (
          <div
            className="mb-8 p-5 rounded-2xl border border-theme-border bg-dark-card flex items-center justify-center gap-3 text-center"
            data-testid="no-round-banner"
          >
            <CalendarOff className="w-6 h-6 text-theme-dim shrink-0" aria-hidden="true" />
            <p className="text-theme-text">{t('tyrant:apply.notOpenBody')}</p>
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-6">
          <button
            onClick={() => !noRound && navigate(TYRANT_PATHS.apply)}
            disabled={noRound}
            data-testid="tyrant-apply-tile"
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
              <h2 className="text-2xl font-bold text-theme-text mb-3">{t('tyrant:home.applyTile')}</h2>
              <p className="text-theme-dim">
                {noRound
                  ? t('tyrant:apply.notOpenTitle')
                  : isClosed
                    ? t('tyrant:home.applyTileClosedDesc')
                    : t('tyrant:home.applyTileDesc')}
              </p>
            </div>
          </button>

          <button
            onClick={() => navigate('/admin')}
            data-testid="tyrant-admin-tile"
            className="bg-dark-card rounded-2xl p-8 border border-theme-border hover:bg-dark-card-hover transform hover:-translate-y-2 transition-all duration-300 group"
          >
            <div className="flex flex-col items-center text-center">
              <div className="w-20 h-20 bg-accent/20 rounded-full flex items-center justify-center mb-6 group-hover:bg-accent/30 transition-colors">
                <Shield className="w-10 h-10 text-accent" aria-hidden="true" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text mb-3">{t('admin:title')}</h2>
              <p className="text-theme-dim">{t('tyrant:home.adminDesc')}</p>
            </div>
          </button>
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-3">
          <button
            onClick={() => navigate('/')}
            className="inline-flex items-center gap-2 text-accent hover:text-accent-dim transition-colors text-sm font-medium"
          >
            <ArrowLeft className="w-4 h-4 rtl:rotate-180" aria-hidden="true" />
            {t('common:nav.home')}
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
          <p>{t('tyrant:home.utcNote')}</p>
        </div>
      </div>
    </div>
  );
}
