import { useTranslation } from 'react-i18next';
import type { PlayerAssignments } from '../../shared/api';
import { activeDaysInOrder } from '../../shared/days';
import { formatTimeInTimezone } from '../../shared/timezone';

// The player's own ministry assignments in the current round (v1.4's "Your
// Current Assignments" box). The API lists PUBLISHED days only (v1.4 also showed
// drafts), so this shows the round's active days that are published; with none
// published yet it says so instead of a misleading "None" per day.

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
  const published = data.published_days ?? Object.keys(data.assignments ?? {});
  const days = activeDaysInOrder(researchDay).filter((d) => published.includes(d));
  return (
    <div className="bg-success/10 border border-success/30 rounded-lg p-4 sm:p-5" data-testid="my-assignments">
      <h3 className="text-lg font-semibold text-success mb-3">{t('ministry:update.currentAssignments')}</h3>
      {days.length === 0 && (
        <p className="text-theme-dim text-sm italic" data-testid="my-assignments-none">{t('ministry:update.noAssignments')}</p>
      )}
      <div className="space-y-2">
        {days.map((day) => {
          const slots = data.assignments?.[day] || [];
          return (
            <div key={day} className="flex flex-wrap items-center gap-3" data-testid={`my-assignments-${day}`}>
              <span className="font-medium text-theme-text sm:min-w-[200px]">{t(`admin:${day}`)}:</span>
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
