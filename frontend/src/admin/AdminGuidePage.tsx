import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, BookOpen, Compass } from 'lucide-react';
import { usePageTitle } from '../shared/usePageTitle';
import { useScrollToHash } from '../shared/guide/GuideBits';
import { GuideLoading, useGuidesReady } from '../shared/guide/useGuidesReady';
import AdminEventSwitch from './AdminEventSwitch';
import EventBasicsGuide from './EventBasicsGuide';
import { resolveAdminEvent } from './registry';
import { ADMIN_PATHS } from './paths';

// /admin/guide?event=<key>: the admin guide of one event, with the same event
// switch as the dashboard. The dashboard's guide button opens the current
// event's guide; plain /admin/guide shows the last event administered here.
// &topic=basics shows "Event Management basics" (shared by every event), linked
// at the top of every event's guide.
export default function AdminGuidePage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const event = resolveAdminEvent(params.get('event'));
  const basics = params.get('topic') === 'basics';
  const Guide = event.Guide;
  const ready = useGuidesReady();
  useScrollToHash(ready);

  useEffect(() => {
    if (params.get('event') !== event.key) {
      const next = new URLSearchParams(params);
      next.set('event', event.key);
      setParams(next, { replace: true });
    }
  }, [params, event.key, setParams]);

  usePageTitle(ready && (basics ? t('guide:basics.title') : t('guide:admin.title')), t(event.label));

  const topicTab = (on: boolean, label: string, href: string, testId: string, Icon: typeof BookOpen) => (
    <button
      type="button"
      role="tab"
      aria-selected={on}
      data-testid={testId}
      onClick={() => !on && navigate(href)}
      className={`shrink-0 inline-flex items-center gap-2 min-h-[44px] px-3 py-2 rounded-md text-sm font-semibold transition-colors text-start ${
        on ? 'bg-accent/20 text-accent' : 'text-theme-dim hover:text-theme-text hover:bg-dark-card-hover'
      }`}
    >
      <Icon className="w-4 h-4 shrink-0" aria-hidden="true" />
      {label}
    </button>
  );

  return (
    <div
      className="min-h-screen bg-dark-bg py-4 sm:py-8 px-3 sm:px-4"
      data-testid="admin-guide"
      data-event={event.key}
      data-topic={basics ? 'basics' : 'event'}
    >
      <div className="max-w-3xl mx-auto">
        <button
          onClick={() => navigate(ADMIN_PATHS.dashboard(event.key))}
          data-testid="guide-back"
          className="flex items-center gap-2 min-h-[44px] text-theme-dim hover:text-accent transition-colors mb-4 sm:mb-6"
        >
          <ArrowLeft className="w-5 h-5 rtl:rotate-180" aria-hidden="true" />
          {t('guide:admin.backToDashboard')}
        </button>

        {!ready ? (
          <GuideLoading />
        ) : (
          <>
            <h1 className="text-3xl sm:text-4xl font-bold text-accent mb-4 break-words" data-testid="admin-guide-title">
              {basics ? t('guide:basics.title') : t('guide:admin.title')}
            </h1>
            <div className="mb-3">
              <AdminEventSwitch current={event.key} hrefFor={basics ? ADMIN_PATHS.basics : ADMIN_PATHS.guide} />
            </div>

            {/* Event guide | Event Management basics */}
            <div className="mb-3 flex flex-wrap gap-1" role="tablist" aria-label={t('guide:admin.title')} data-testid="guide-topics">
              {topicTab(!basics, t('guide:basics.eventTab', { event: t(event.label) }), ADMIN_PATHS.guide(event.key), 'guide-topic-event', BookOpen)}
              {topicTab(basics, t('guide:basics.title'), ADMIN_PATHS.basics(event.key), 'guide-topic-basics', Compass)}
            </div>
            {!basics && (
              <p className="mb-6 text-sm text-theme-dim" data-testid="guide-basics-hint">
                {t('guide:basics.hint')}
              </p>
            )}

            {basics ? <EventBasicsGuide /> : <Guide key={event.key} />}
          </>
        )}
      </div>
    </div>
  );
}
