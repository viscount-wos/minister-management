import { useTranslation } from 'react-i18next';
import type { PlayerAssignments } from '../../shared/api';
import { activeDaysInOrder } from '../../shared/days';
import { formatTimeInTimezone } from '../../shared/timezone';

// The player's own ministry assignments in the current round. As in v1.4 this
// lists every active day (published or not) with the "subject to change" note.

export default function MyAssignments({
  data,
  researchDay,
  timezone,
}: {
  data: PlayerAssignments;
  researchDay: string;
  timezone: string;
}) {
  const { t } = useTranslation();
  return (
    <div className="bg-success/10 border border-success/30 rounded-lg p-5" data-testid="my-assignments">
      <h3 className="text-lg font-semibold text-success mb-3">{t('ministry:update.currentAssignments')}</h3>
      <div className="space-y-2">
        {activeDaysInOrder(researchDay).map((day) => {
          const slots = data.assignments[day] || [];
          return (
            <div key={day} className="flex flex-wrap items-center gap-3" data-testid={`my-assignments-${day}`}>
              <span className="font-medium text-theme-text min-w-[200px]">{t(`admin:${day}`)}:</span>
              {slots.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {slots.map((s, i) => (
                    <span key={i} className="px-3 py-1 bg-success/20 text-success rounded-full text-sm font-medium">
                      {formatTimeInTimezone(s.time_slot, timezone)}
                      {s.time_slot === '23:50+' && <span className="text-xs opacity-60 ms-1">(+1d)</span>}
                      {timezone !== 'UTC' && <span className="opacity-60 ms-1 text-xs">({s.time_slot} UTC)</span>}
                    </span>
                  ))}
                </div>
              ) : (
                <span className="text-theme-dim text-sm italic">{t('ministry:update.noneAssigned')}</span>
              )}
            </div>
          );
        })}
      </div>
      <p className="text-xs text-theme-dim mt-3 italic">{t('ministry:update.assignmentDisclaimer')}</p>
    </div>
  );
}
