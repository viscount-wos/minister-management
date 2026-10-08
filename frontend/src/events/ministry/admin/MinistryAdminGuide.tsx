import { useTranslation } from 'react-i18next';
import { Settings, Users, Calendar, Lock, Globe, FileSpreadsheet, Download, Move, Wand2, UserPlus } from 'lucide-react';
import { GuideList, GuideSection } from '../../../shared/guide/GuideBits';

// Minister admin guide (guide:admin.*; body only, admin/AdminGuidePage adds the title, the basics link and the
// event switch). Describes PlayerManagement, AssignmentManagement and AdminSettings: see docs/GUIDES.md.
export default function MinistryAdminGuide() {
  const { t } = useTranslation();
  const k = (key: string) => t(`guide:admin.${key}`);
  const h3 = (key: string) => <h3 className="text-lg font-semibold text-theme-text mb-2">{k(key)}</h3>;

  return (
    <div data-testid="admin-guide-ministry">
      <p className="text-theme-dim mb-6 sm:mb-8">{k('subtitle')}</p>
      <div className="space-y-6 sm:space-y-8">
        <GuideSection icon={Settings} title={k('overviewTitle')}>
          <p>{k('overviewBody')}</p>
        </GuideSection>

        <GuideSection icon={Users} title={k('playersTitle')}>
          <div>
            {h3('playersViewHeader')}
            <GuideList t={k} keys={['playersView1', 'playersView2', 'playersView3', 'playersView4']} />
          </div>
          <div>
            {h3('playersEditHeader')}
            <GuideList t={k} keys={['playersEdit1', 'playersEdit2', 'playersEdit3']} />
          </div>
          <div>
            {h3('playersDeleteHeader')}
            <p>{k('playersDeleteBody')}</p>
          </div>
        </GuideSection>

        <GuideSection icon={UserPlus} title={k('addTitle')}>
          <p>{k('addBody')}</p>
        </GuideSection>

        <GuideSection icon={Download} title={k('exportImportTitle')}>
          <div>
            {h3('exportHeader')}
            <p>{k('exportBody')}</p>
          </div>
          <div>
            {h3('importHeader')}
            <p>{k('importBody')}</p>
          </div>
        </GuideSection>

        <GuideSection icon={Wand2} title={k('assignTitle')}>
          <div>
            {h3('autoAssignHeader')}
            <GuideList t={k} keys={['autoAssign1', 'autoAssign2', 'autoAssign3', 'autoAssign4']} />
          </div>
        </GuideSection>

        <GuideSection icon={Move} title={k('dragDropHeader')}>
          <GuideList t={k} keys={['dragDrop1', 'dragDrop2', 'dragDrop3', 'dragDrop4']} />
        </GuideSection>

        <GuideSection icon={Lock} title={k('stickyHeader')}>
          <GuideList t={k} keys={['sticky1', 'sticky2', 'sticky3', 'sticky4']} />
        </GuideSection>

        <GuideSection icon={Calendar} title={k('settingsTitle')}>
          <p>{k('settingsBody')}</p>
          <GuideList
            t={k}
            keys={['settingsState', 'settingsHeroes', 'settingsClosing', 'settingsResearch', 'settingsFireCrystals', 'settingsScheme', 'settingsPublished']}
          />
        </GuideSection>

        <GuideSection icon={Globe} title={k('publishTitle')}>
          <p>{k('publishBody')}</p>
          <GuideList t={k} keys={['publish1', 'publish2', 'publish3', 'publish4']} />
        </GuideSection>

        <GuideSection icon={FileSpreadsheet} title={k('excelTitle')}>
          <p>{k('excelBody')}</p>
          <GuideList t={k} keys={['excel1', 'excel2', 'excel3']} />
        </GuideSection>

        <section className="bg-accent/10 border border-accent/30 rounded-xl p-4 sm:p-6">
          <h2 className="text-xl sm:text-2xl font-bold text-accent mb-4">{k('workflowTitle')}</h2>
          <GuideList t={k} ordered keys={['workflow1', 'workflow2', 'workflow3', 'workflow4', 'workflow5', 'workflow6', 'workflow7', 'workflow8']} />
        </section>
      </div>
    </div>
  );
}
