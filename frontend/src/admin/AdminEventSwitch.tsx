import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ADMIN_EVENTS } from './registry';

// Event switch at the top of the admin (dashboard and guide): one tab per
// registered event. Switching only changes ?event= in the URL, so the admin
// token stays and a reload keeps the event.
export default function AdminEventSwitch({ current, hrefFor }: { current: string; hrefFor: (event: string) => string }) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  return (
    <div
      role="tablist"
      aria-label={t('admin:shell.eventSwitch')}
      data-testid="admin-event-switch"
      className="inline-flex flex-wrap rounded-lg border border-theme-border bg-dark-bg p-1 gap-1"
    >
      {ADMIN_EVENTS.map(({ key, label, icon: Icon }) => (
        <button
          key={key}
          type="button"
          role="tab"
          aria-selected={current === key}
          data-testid={`admin-event-${key}`}
          onClick={() => current !== key && navigate(hrefFor(key))}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-semibold transition-colors ${
            current === key ? 'bg-accent text-dark-bg' : 'text-theme-dim hover:text-theme-text hover:bg-dark-card-hover'
          }`}
        >
          <Icon className="w-4 h-4" aria-hidden="true" />
          {t(label)}
        </button>
      ))}
    </div>
  );
}
