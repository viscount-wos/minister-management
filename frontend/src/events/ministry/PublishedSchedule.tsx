import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, Calendar, AlertTriangle } from 'lucide-react';
import api from '../../shared/api';
import TimezoneSelector from '../../shared/TimezoneSelector';
import { useTimezone } from '../../shared/TimezoneContext';
import { getSlotDisplayTime, generateAssignmentSlots, TimeSlotScheme } from '../../shared/timezone';
import { MINISTRY_PATHS } from './paths';

interface PublishedPlayer {
  game_name: string;
  alliance: string;
}

interface PublishedData {
  published: boolean;
  day?: string;
  day_label?: string;
  assignments?: { [slot: string]: PublishedPlayer[] };
}

export default function PublishedSchedule() {
  const navigate = useNavigate();
  const { day } = useParams<{ day: string }>();
  const { t } = useTranslation();
  const [data, setData] = useState<PublishedData | null>(null);
  const [loading, setLoading] = useState(true);
  const { timezone, setTimezone } = useTimezone();
  const [appsStillOpen, setAppsStillOpen] = useState(false);
  const [scheme, setScheme] = useState<TimeSlotScheme>('exact_alignment');

  useEffect(() => {
    if (!day) {
      setData({ published: false });
      setLoading(false);
      return;
    }
    api.ministry.scheduleDay(day)
      .then(res => setData(res))
      .catch(() => setData({ published: false }))
      .finally(() => setLoading(false));

    // Disclaimer while the round is still taking new applications.
    api.currentRound('ministry')
      .then(r => {
        setAppsStillOpen(!!r.closing_time && !r.is_closed_for_new);
        // Draw the round's own slot grid (max_slots has :20/:50 slots).
        setScheme(r.settings.time_slot_scheme);
      })
      .catch(() => {});
  }, [day]);

  const allSlots = generateAssignmentSlots(scheme);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <p className="text-theme-dim">{t('ministry:form.loading')}</p>
      </div>
    );
  }

  if (!data?.published) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="bg-dark-card rounded-2xl p-12 border border-theme-border max-w-md w-full text-center">
          <Calendar className="w-16 h-16 text-theme-dim mx-auto mb-6" />
          <h2 className="text-2xl font-bold text-theme-text mb-4">{t('ministry:schedule.noSchedule')}</h2>
          <p className="text-theme-dim mb-6">{t('ministry:schedule.noScheduleDesc')}</p>
          <button
            onClick={() => navigate(MINISTRY_PATHS.home)}
            className="flex items-center gap-2 mx-auto text-accent hover:text-accent-dim"
          >
            <ArrowLeft className="w-5 h-5 rtl:rotate-180" aria-hidden="true" />
            {t('ministry:update.backHome')}
          </button>
        </div>
      </div>
    );
  }

  const assignments = data.assignments || {};
  // Show all slots - populated ones with player cards, empty ones with blank placeholder
  const hasAnyAssignments = allSlots.some(slot => (assignments[slot] || []).length > 0);

  // Translate the day label
  const dayKey = data.day || '';
  const translatedDayLabel = t(`admin:${dayKey}`, { defaultValue: data.day_label || dayKey });

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="bg-dark-card rounded-2xl p-8 border border-theme-border max-w-5xl w-full">
        <button
          onClick={() => navigate(MINISTRY_PATHS.home)}
          className="flex items-center gap-2 text-theme-dim hover:text-theme-text mb-6"
        >
          <ArrowLeft className="w-5 h-5 rtl:rotate-180" aria-hidden="true" />
          {t('ministry:update.backHome')}
        </button>

        <div className="text-center mb-6">
          <h2 className="text-3xl font-bold text-accent mb-2">
            {t('ministry:schedule.title')}
          </h2>
          <p className="text-xl text-theme-dim">{translatedDayLabel}</p>
        </div>

        {appsStillOpen && (
          <div className="mb-6 p-4 bg-warning/10 border border-warning/30 rounded-lg flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-warning flex-shrink-0" />
            <p className="text-warning text-sm font-medium">{t('ministry:schedule.disclaimer')}</p>
          </div>
        )}

        <div className="flex justify-end mb-4">
          <TimezoneSelector value={timezone} onChange={setTimezone} />
        </div>

        {!hasAnyAssignments ? (
          <p className="text-center text-theme-dim py-8">{t('ministry:schedule.noAssignments')}</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
            {allSlots.map(slot => {
              const players = assignments[slot] || [];
              const displayTime = getSlotDisplayTime(slot, timezone);
              const isEmpty = players.length === 0;
              return (
                <div
                  key={slot}
                  className={`border rounded-lg p-3 ${
                    isEmpty
                      ? 'border-theme-border/40 bg-dark-bg/50'
                      : 'border-theme-border bg-dark-bg'
                  }`}
                >
                  <div className={`font-semibold mb-2 text-center ${
                    isEmpty ? 'text-theme-dim' : 'text-accent'
                  }`}>
                    {displayTime}
                    {slot === '23:50+' && <span className="text-xs opacity-60 ml-1">(+1d)</span>}
                    {timezone !== 'UTC' && (
                      <span className="block text-xs text-theme-dim font-normal">
                        {slot.replace('+', '')} UTC
                      </span>
                    )}
                  </div>
                  {isEmpty ? (
                    <div className="p-2 border border-dashed border-theme-border/30 rounded-lg text-center">
                      <span className="text-theme-dim/50 text-sm">{t('ministry:schedule.unfilled')}</span>
                    </div>
                  ) : (
                    players.map((player, idx) => (
                      <div
                        key={idx}
                        className="p-2 bg-accent/10 border border-accent/30 rounded-lg text-center"
                      >
                        <div className="font-medium text-theme-text">
                          {player.alliance && (
                            <span className="text-accent">[{player.alliance}] </span>
                          )}
                          {player.game_name}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              );
            })}
          </div>
        )}

        <div className="mt-6 text-center text-sm text-theme-dim">
          <p>{t('ministry:schedule.timesNote')}</p>
        </div>
      </div>
    </div>
  );
}
