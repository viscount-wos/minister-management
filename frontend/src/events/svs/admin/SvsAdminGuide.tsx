import { useTranslation } from 'react-i18next';
import {
  Settings, RefreshCw, CalendarClock, BarChart3, Filter, FileSpreadsheet, UserPlus, Users, Image, Swords, Table,
  Crown, Drama, UserCheck, Sparkles, Save, Share2,
} from 'lucide-react';
import { GuideList, GuideSection } from '../../../shared/guide/GuideBits';

// SVS admin guide (guide:svsAdmin.*; body only, admin/AdminGuidePage adds the title, the basics link and the event
// switch). Describes SvsPlayers, SvsRoundSettings, SvsHeroes and the planner (../plan/*): see docs/GUIDES.md.
export default function SvsAdminGuide() {
  const { t } = useTranslation();
  const k = (key: string) => t(`guide:svsAdmin.${key}`);

  return (
    <div data-testid="admin-guide-svs">
      <p className="text-theme-dim mb-4">{k('subtitle')}</p>
      {/* Jump links: this guide is long (the Battle plan alone has seven sections) */}
      <nav className="mb-6 sm:mb-8 flex flex-wrap gap-2" aria-label={k('subtitle')} data-testid="guide-toc">
        {(
          [
            ['players', 'tableTitle'],
            ['plan', 'planTitle'],
            ['share', 'shareTitle'],
            ['heroes', 'heroesTitle'],
          ] as const
        ).map(([id, title]) => (
          <a
            key={id}
            href={`#${id}`}
            className="inline-flex items-center min-h-[44px] px-3 rounded-full border border-theme-border text-sm text-accent hover:bg-dark-card-hover"
          >
            {k(title)}
          </a>
        ))}
      </nav>
      <div className="space-y-6 sm:space-y-8">
        <GuideSection icon={Settings} title={k('overviewTitle')}>
          <p>{k('overviewBody')}</p>
        </GuideSection>
        <GuideSection icon={RefreshCw} title={k('roundsTitle')}>
          <GuideList t={k} keys={['rounds1', 'rounds2', 'rounds3']} />
        </GuideSection>
        <GuideSection icon={CalendarClock} title={k('battleTitle')}>
          <p>{k('battleBody')}</p>
          <GuideList t={k} keys={['battle1', 'battle2', 'battle3']} />
        </GuideSection>
        <GuideSection icon={Users} title={k('signupTitle')}>
          <GuideList t={k} keys={['signup1', 'signup2', 'signup3', 'signup4']} />
        </GuideSection>

        {/* Players tab. To document a new Players feature, add a key (table4, ...) to this list in all 9 languages. */}
        <GuideSection icon={Table} title={k('tableTitle')} id="players">
          <GuideList t={k} keys={['table1', 'table2', 'table3', 'table4', 'table5', 'table6']} />
        </GuideSection>
        <GuideSection icon={BarChart3} title={k('statsTitle')}>
          <p>{k('statsBody')}</p>
        </GuideSection>
        <GuideSection icon={Filter} title={k('filtersTitle')}>
          <GuideList t={k} keys={['filters1', 'filters2', 'filters3']} />
        </GuideSection>
        <GuideSection icon={FileSpreadsheet} title={k('exportTitle')}>
          <p>{k('exportBody')}</p>
        </GuideSection>
        <GuideSection icon={UserPlus} title={k('addTitle')}>
          <p>{k('addBody')}</p>
        </GuideSection>

        {/* Battle plan tab */}
        <GuideSection icon={Swords} title={k('planTitle')} id="plan">
          <p>{k('planBody')}</p>
          <GuideList t={k} keys={['strategy1', 'strategy2', 'strategy3']} />
        </GuideSection>
        <GuideSection icon={Crown} title={k('leadersTitle')}>
          <GuideList t={k} keys={['leaders1', 'leaders2', 'leaders3', 'leaders4', 'leaders5']} />
        </GuideSection>
        <GuideSection icon={Drama} title={k('disguiseTitle')}>
          <GuideList t={k} keys={['disguise1', 'disguise2']} />
        </GuideSection>
        <GuideSection icon={UserCheck} title={k('joinersTitle')}>
          <GuideList t={k} keys={['joiners1', 'joiners2', 'joiners3', 'joiners4', 'joiners5']} />
        </GuideSection>
        <GuideSection icon={Sparkles} title={k('heroPickTitle')}>
          <GuideList t={k} keys={['heroPick1', 'heroPick2']} />
        </GuideSection>
        <GuideSection icon={Save} title={k('saveTitle')}>
          <GuideList t={k} keys={['save1', 'save2', 'save3', 'save4']} />
        </GuideSection>
        <GuideSection icon={Share2} title={k('shareTitle')} id="share">
          <GuideList t={k} keys={['share1', 'share2', 'share3', 'share4']} />
        </GuideSection>

        {/* Heroes tab */}
        <GuideSection icon={Image} title={k('heroesTitle')} id="heroes">
          <p>{k('heroesBody')}</p>
        </GuideSection>

        <section className="bg-accent/10 border border-accent/30 rounded-xl p-4 sm:p-6">
          <h2 className="text-xl sm:text-2xl font-bold text-accent mb-4">{k('workflowTitle')}</h2>
          <GuideList t={k} ordered keys={['workflow1', 'workflow2', 'workflow3', 'workflow4', 'workflow5', 'workflow6']} />
        </section>
      </div>
    </div>
  );
}
