import { useTranslation } from 'react-i18next';
import { LucideIcon, Settings, RefreshCw, CalendarClock, BarChart3, Filter, FileSpreadsheet, UserPlus, Users, Image } from 'lucide-react';

// SVS admin guide (body only; admin/AdminGuidePage adds the title, back button and event switch).

function Section({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: React.ReactNode }) {
  return (
    <section className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center shrink-0">
          <Icon className="w-5 h-5 text-accent" aria-hidden="true" />
        </div>
        <h2 className="text-2xl font-bold text-theme-text">{title}</h2>
      </div>
      <div className="text-theme-dim leading-relaxed space-y-3">{children}</div>
    </section>
  );
}

export default function SvsAdminGuide() {
  const { t } = useTranslation();
  const k = (key: string) => t(`guide:svsAdmin.${key}`);
  const list = (...keys: string[]) => (
    <ul className="list-disc list-inside space-y-1 ms-2">
      {keys.map((key) => (
        <li key={key}>{k(key)}</li>
      ))}
    </ul>
  );

  return (
    <div data-testid="admin-guide-svs">
      <p className="text-theme-dim mb-8">{k('subtitle')}</p>
      <div className="space-y-8">
        <Section icon={Settings} title={k('overviewTitle')}>
          <p>{k('overviewBody')}</p>
        </Section>
        <Section icon={RefreshCw} title={k('roundsTitle')}>
          {list('rounds1', 'rounds2', 'rounds3')}
        </Section>
        <Section icon={CalendarClock} title={k('battleTitle')}>
          <p>{k('battleBody')}</p>
          {list('battle1', 'battle2')}
        </Section>
        <Section icon={Users} title={k('signupTitle')}>
          {list('signup1', 'signup2', 'signup3', 'signup4')}
        </Section>
        <Section icon={BarChart3} title={k('statsTitle')}>
          <p>{k('statsBody')}</p>
        </Section>
        <Section icon={Filter} title={k('filtersTitle')}>
          {list('filters1', 'filters2', 'filters3')}
        </Section>
        <Section icon={FileSpreadsheet} title={k('exportTitle')}>
          <p>{k('exportBody')}</p>
        </Section>
        <Section icon={UserPlus} title={k('addTitle')}>
          <p>{k('addBody')}</p>
        </Section>
        <Section icon={Image} title={k('heroesTitle')}>
          <p>{k('heroesBody')}</p>
        </Section>
      </div>
    </div>
  );
}
