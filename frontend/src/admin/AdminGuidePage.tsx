import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft } from 'lucide-react';
import { usePageTitle } from '../shared/usePageTitle';
import AdminEventSwitch from './AdminEventSwitch';
import { resolveAdminEvent } from './registry';
import { ADMIN_PATHS } from './paths';

// /admin/guide?event=<key>: the admin guide of one event, with the same event
// switch as the dashboard. The dashboard's guide button opens the current
// event's guide; plain /admin/guide shows the last event administered here.
export default function AdminGuidePage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const event = resolveAdminEvent(params.get('event'));
  const Guide = event.Guide;

  useEffect(() => {
    if (params.get('event') !== event.key) setParams({ event: event.key }, { replace: true });
  }, [params, event.key, setParams]);

  usePageTitle(t('guide:admin.title'), t(event.label));

  return (
    <div className="min-h-screen bg-dark-bg py-4 sm:py-8 px-3 sm:px-4" data-testid="admin-guide" data-event={event.key}>
      <div className="max-w-3xl mx-auto">
        <button
          onClick={() => navigate(ADMIN_PATHS.dashboard(event.key))}
          data-testid="guide-back"
          className="flex items-center gap-2 min-h-[44px] text-theme-dim hover:text-accent transition-colors mb-4 sm:mb-6"
        >
          <ArrowLeft className="w-5 h-5 rtl:rotate-180" aria-hidden="true" />
          {t('guide:admin.backToDashboard')}
        </button>

        <h1 className="text-3xl sm:text-4xl font-bold text-accent mb-4 break-words" data-testid="admin-guide-title">
          {t('guide:admin.title')}
        </h1>
        <div className="mb-4">
          <AdminEventSwitch current={event.key} hrefFor={ADMIN_PATHS.guide} />
        </div>

        <Guide key={event.key} />
      </div>
    </div>
  );
}
