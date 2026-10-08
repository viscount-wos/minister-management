import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

// Ministry | Frost Dragon Tyrant switch at the top of the admin dashboard.
// The event is in the URL (?event=tyrant) so a reload stays on the same event.

export type AdminEvent = 'ministry' | 'tyrant';

const EVENTS: { key: AdminEvent; label: string; path: string }[] = [
  { key: 'ministry', label: 'ministry:event.name', path: '/admin/dashboard' },
  { key: 'tyrant', label: 'tyrant:name', path: '/admin/dashboard?event=tyrant' },
];

export default function AdminEventSwitch({ current }: { current: AdminEvent }) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  return (
    <div
      role="tablist"
      aria-label={t('tyrant:admin.eventSwitch')}
      data-testid="admin-event-switch"
      className="inline-flex rounded-lg border border-theme-border bg-dark-bg p-1 gap-1"
    >
      {EVENTS.map((e) => (
        <button
          key={e.key}
          type="button"
          role="tab"
          aria-selected={current === e.key}
          data-testid={`admin-event-${e.key}`}
          onClick={() => current !== e.key && navigate(e.path)}
          className={`px-4 py-2 rounded-md text-sm font-semibold transition-colors ${
            current === e.key ? 'bg-accent text-dark-bg' : 'text-theme-dim hover:text-theme-text hover:bg-dark-card-hover'
          }`}
        >
          {t(e.label)}
        </button>
      ))}
    </div>
  );
}
