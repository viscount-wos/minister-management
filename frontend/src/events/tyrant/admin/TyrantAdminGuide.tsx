import { useTranslation } from 'react-i18next';
import { LucideIcon, Settings, RefreshCw, Clock, CalendarClock, BarChart3, Filter, FileSpreadsheet, Trash2 } from 'lucide-react';

// Frost Dragon Tyrant admin guide (body only; admin/AdminGuidePage adds the
// title, back button and event switch). Same layout as the ministry guide.

function Section({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: React.ReactNode }) {
  return (
    <section className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
          <Icon className="w-5 h-5 text-accent" aria-hidden="true" />
        </div>
        <h2 className="text-2xl font-bold text-theme-text">{title}</h2>
      </div>
      <div className="text-theme-dim leading-relaxed space-y-3">{children}</div>
    </section>
  );
}

export default function TyrantAdminGuide() {
  const { t } = useTranslation();
  const k = (key: string) => t(`guide:tyrantAdmin.${key}`);
  const list = (...keys: string[]) => (
    <ul className="list-disc list-inside space-y-1 ms-2">
      {keys.map((key) => (
        <li key={key}>{k(key)}</li>
      ))}
    </ul>
  );

  return (
    <div data-testid="admin-guide-tyrant">
      <p className="text-theme-dim mb-8">{t('guide:tyrantAdmin.subtitle')}</p>

      <div className="space-y-8">
        <Section icon={Settings} title={t('guide:tyrantAdmin.overviewTitle')}>
          <p>{t('guide:tyrantAdmin.overviewBody')}</p>
        </Section>

        <Section icon={RefreshCw} title={t('guide:tyrantAdmin.roundsTitle')}>
          {list('rounds1', 'rounds2', 'rounds3', 'rounds4')}
        </Section>

        <Section icon={CalendarClock} title={t('guide:tyrantAdmin.windowsTitle')}>
          <p>{t('guide:tyrantAdmin.windowsBody')}</p>
          {list('windows1', 'windows2', 'windows3', 'windows4')}
        </Section>

        <Section icon={Clock} title={t('guide:tyrantAdmin.closingTitle')}>
          <p>{t('guide:tyrantAdmin.closingBody')}</p>
        </Section>

        <Section icon={BarChart3} title={t('guide:tyrantAdmin.statsTitle')}>
          <p>{t('guide:tyrantAdmin.statsBody')}</p>
          {list('stats1', 'stats2', 'stats3')}
        </Section>

        <Section icon={Filter} title={t('guide:tyrantAdmin.filtersTitle')}>
          {list('filters1', 'filters2', 'filters3', 'filters4')}
        </Section>

        <Section icon={FileSpreadsheet} title={t('guide:tyrantAdmin.exportTitle')}>
          <p>{t('guide:tyrantAdmin.exportBody')}</p>
          {list('export1', 'export2')}
        </Section>

        <Section icon={Trash2} title={t('guide:tyrantAdmin.deleteTitle')}>
          <p>{t('guide:tyrantAdmin.deleteBody')}</p>
        </Section>

        <section className="bg-accent/10 border border-accent/30 rounded-xl p-4 sm:p-6">
          <h2 className="text-2xl font-bold text-accent mb-4">{t('guide:tyrantAdmin.workflowTitle')}</h2>
          <ol className="space-y-2 text-theme-dim list-decimal list-inside">
            {['workflow1', 'workflow2', 'workflow3', 'workflow4', 'workflow5', 'workflow6'].map((key) => (
              <li key={key}>{k(key)}</li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );
}
