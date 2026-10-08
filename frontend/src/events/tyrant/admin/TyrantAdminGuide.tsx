import { useTranslation } from 'react-i18next';
import { Settings, RefreshCw, Clock, CalendarClock, BarChart3, Filter, FileSpreadsheet, Trash2, UserPlus } from 'lucide-react';
import { GuideList, GuideSection } from '../../../shared/guide/GuideBits';

// Frost Dragon Tyrant admin guide (guide:tyrantAdmin.*; body only, admin/AdminGuidePage adds the title, the basics
// link and the event switch). Describes TyrantPlayers and TyrantRoundSettings: see docs/GUIDES.md.
export default function TyrantAdminGuide() {
  const { t } = useTranslation();
  const k = (key: string) => t(`guide:tyrantAdmin.${key}`);

  return (
    <div data-testid="admin-guide-tyrant">
      <p className="text-theme-dim mb-6 sm:mb-8">{k('subtitle')}</p>
      <div className="space-y-6 sm:space-y-8">
        <GuideSection icon={Settings} title={k('overviewTitle')}>
          <p>{k('overviewBody')}</p>
        </GuideSection>

        <GuideSection icon={RefreshCw} title={k('roundsTitle')}>
          <GuideList t={k} keys={['rounds1', 'rounds2', 'rounds3', 'rounds4']} />
        </GuideSection>

        <GuideSection icon={CalendarClock} title={k('windowsTitle')}>
          <p>{k('windowsBody')}</p>
          <GuideList t={k} keys={['windows1', 'windows2', 'windows3', 'windows4']} />
        </GuideSection>

        <GuideSection icon={Clock} title={k('closingTitle')}>
          <p>{k('closingBody')}</p>
        </GuideSection>

        <GuideSection icon={BarChart3} title={k('statsTitle')}>
          <p>{k('statsBody')}</p>
          <GuideList t={k} keys={['stats1', 'stats2', 'stats3']} />
        </GuideSection>

        <GuideSection icon={Filter} title={k('filtersTitle')}>
          <GuideList t={k} keys={['filters1', 'filters2', 'filters5', 'filters3', 'filters6', 'filters4']} />
        </GuideSection>

        <GuideSection icon={FileSpreadsheet} title={k('exportTitle')}>
          <p>{k('exportBody')}</p>
          <GuideList t={k} keys={['export1', 'export2']} />
        </GuideSection>

        <GuideSection icon={UserPlus} title={k('addTitle')}>
          <p>{k('addBody')}</p>
        </GuideSection>

        <GuideSection icon={Trash2} title={k('deleteTitle')}>
          <p>{k('deleteBody')}</p>
        </GuideSection>

        <section className="bg-accent/10 border border-accent/30 rounded-xl p-4 sm:p-6">
          <h2 className="text-xl sm:text-2xl font-bold text-accent mb-4">{k('workflowTitle')}</h2>
          <GuideList t={k} ordered keys={['workflow1', 'workflow2', 'workflow3', 'workflow4', 'workflow5', 'workflow6']} />
        </section>
      </div>
    </div>
  );
}
