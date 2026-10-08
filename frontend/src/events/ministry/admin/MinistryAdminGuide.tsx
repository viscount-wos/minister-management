import { useTranslation } from 'react-i18next';
import { Users, Calendar, Upload, Download, Lock, GripVertical, FileSpreadsheet, Globe, Settings } from 'lucide-react';

// Ministry admin guide (body only; the shared guide page in admin/AdminGuidePage
// adds the title, back button and event switch).
export default function MinistryAdminGuide() {
  const { t } = useTranslation();

  return (
    <div data-testid="admin-guide-ministry">
      <p className="text-theme-dim mb-8">{t('guide:admin.subtitle')}</p>

      <div className="space-y-8">
        {/* Overview */}
        <section className="bg-dark-card rounded-xl border border-theme-border p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
              <Settings className="w-5 h-5 text-accent" />
            </div>
            <h2 className="text-2xl font-bold text-theme-text">{t('guide:admin.overviewTitle')}</h2>
          </div>
          <p className="text-theme-dim leading-relaxed">{t('guide:admin.overviewBody')}</p>
        </section>

        {/* Player Management */}
        <section className="bg-dark-card rounded-xl border border-theme-border p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
              <Users className="w-5 h-5 text-accent" />
            </div>
            <h2 className="text-2xl font-bold text-theme-text">{t('guide:admin.playersTitle')}</h2>
          </div>
          <div className="text-theme-dim leading-relaxed space-y-4">
            <div>
              <h3 className="text-lg font-semibold text-theme-text mb-2">{t('guide:admin.playersViewHeader')}</h3>
              <ul className="list-disc list-inside space-y-1 ms-2">
                <li>{t('guide:admin.playersView1')}</li>
                <li>{t('guide:admin.playersView2')}</li>
                <li>{t('guide:admin.playersView3')}</li>
                <li>{t('guide:admin.playersView4')}</li>
              </ul>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-theme-text mb-2">{t('guide:admin.playersEditHeader')}</h3>
              <ul className="list-disc list-inside space-y-1 ms-2">
                <li>{t('guide:admin.playersEdit1')}</li>
                <li>{t('guide:admin.playersEdit2')}</li>
                <li>{t('guide:admin.playersEdit3')}</li>
              </ul>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-theme-text mb-2">{t('guide:admin.playersDeleteHeader')}</h3>
              <p>{t('guide:admin.playersDeleteBody')}</p>
            </div>
          </div>
        </section>

        {/* Export / Import */}
        <section className="bg-dark-card rounded-xl border border-theme-border p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
              <Download className="w-5 h-5 text-accent" />
            </div>
            <h2 className="text-2xl font-bold text-theme-text">{t('guide:admin.exportImportTitle')}</h2>
          </div>
          <div className="text-theme-dim leading-relaxed space-y-4">
            <div>
              <h3 className="text-lg font-semibold text-theme-text mb-2 flex items-center gap-2">
                <Download className="w-4 h-4" /> {t('guide:admin.exportHeader')}
              </h3>
              <p>{t('guide:admin.exportBody')}</p>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-theme-text mb-2 flex items-center gap-2">
                <Upload className="w-4 h-4" /> {t('guide:admin.importHeader')}
              </h3>
              <p>{t('guide:admin.importBody')}</p>
            </div>
          </div>
        </section>

        {/* Assignment Management */}
        <section className="bg-dark-card rounded-xl border border-theme-border p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
              <Calendar className="w-5 h-5 text-accent" />
            </div>
            <h2 className="text-2xl font-bold text-theme-text">{t('guide:admin.assignTitle')}</h2>
          </div>
          <div className="text-theme-dim leading-relaxed space-y-4">
            <div>
              <h3 className="text-lg font-semibold text-theme-text mb-2">{t('guide:admin.autoAssignHeader')}</h3>
              <ul className="list-disc list-inside space-y-1 ms-2">
                <li>{t('guide:admin.autoAssign1')}</li>
                <li>{t('guide:admin.autoAssign2')}</li>
                <li>{t('guide:admin.autoAssign3')}</li>
                <li>{t('guide:admin.autoAssign4')}</li>
              </ul>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-theme-text mb-2 flex items-center gap-2">
                <GripVertical className="w-4 h-4" /> {t('guide:admin.dragDropHeader')}
              </h3>
              <ul className="list-disc list-inside space-y-1 ms-2">
                <li>{t('guide:admin.dragDrop1')}</li>
                <li>{t('guide:admin.dragDrop2')}</li>
                <li>{t('guide:admin.dragDrop3')}</li>
              </ul>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-theme-text mb-2 flex items-center gap-2">
                <Lock className="w-4 h-4" /> {t('guide:admin.stickyHeader')}
              </h3>
              <ul className="list-disc list-inside space-y-1 ms-2">
                <li>{t('guide:admin.sticky1')}</li>
                <li>{t('guide:admin.sticky2')}</li>
                <li>{t('guide:admin.sticky3')}</li>
                <li>{t('guide:admin.sticky4')}</li>
              </ul>
            </div>
          </div>
        </section>

        {/* Research Day Toggle */}
        <section className="bg-dark-card rounded-xl border border-theme-border p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
              <Globe className="w-5 h-5 text-accent" />
            </div>
            <h2 className="text-2xl font-bold text-theme-text">{t('guide:admin.researchDayTitle')}</h2>
          </div>
          <p className="text-theme-dim leading-relaxed">{t('guide:admin.researchDayBody')}</p>
        </section>

        {/* Settings Tab */}
        <section className="bg-dark-card rounded-xl border border-theme-border p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
              <Settings className="w-5 h-5 text-accent" />
            </div>
            <h2 className="text-2xl font-bold text-theme-text">{t('guide:admin.settingsTitle')}</h2>
          </div>
          <div className="text-theme-dim leading-relaxed space-y-3">
            <p>{t('guide:admin.settingsBody')}</p>
            <ul className="list-disc list-inside space-y-1 ms-2">
              <li>{t('guide:admin.settingsState')}</li>
              <li>{t('guide:admin.settingsClosing')}</li>
              <li>{t('guide:admin.settingsResearch')}</li>
              <li>{t('guide:admin.settingsFireCrystals')}</li>
            </ul>
          </div>
        </section>

        {/* Publishing */}
        <section className="bg-dark-card rounded-xl border border-theme-border p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-success/20 rounded-full flex items-center justify-center">
              <Calendar className="w-5 h-5 text-success" />
            </div>
            <h2 className="text-2xl font-bold text-theme-text">{t('guide:admin.publishTitle')}</h2>
          </div>
          <div className="text-theme-dim leading-relaxed space-y-3">
            <p>{t('guide:admin.publishBody')}</p>
            <ul className="list-disc list-inside space-y-1 ms-2">
              <li>{t('guide:admin.publish1')}</li>
              <li>{t('guide:admin.publish2')}</li>
              <li>{t('guide:admin.publish3')}</li>
            </ul>
          </div>
        </section>

        {/* Excel Export */}
        <section className="bg-dark-card rounded-xl border border-theme-border p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
              <FileSpreadsheet className="w-5 h-5 text-accent" />
            </div>
            <h2 className="text-2xl font-bold text-theme-text">{t('guide:admin.excelTitle')}</h2>
          </div>
          <div className="text-theme-dim leading-relaxed space-y-3">
            <p>{t('guide:admin.excelBody')}</p>
            <ul className="list-disc list-inside space-y-1 ms-2">
              <li>{t('guide:admin.excel1')}</li>
              <li>{t('guide:admin.excel2')}</li>
              <li>{t('guide:admin.excel3')}</li>
            </ul>
          </div>
        </section>

        {/* Workflow Tips */}
        <section className="bg-accent/10 border border-accent/30 rounded-xl p-6">
          <h2 className="text-2xl font-bold text-accent mb-4">{t('guide:admin.workflowTitle')}</h2>
          <ol className="space-y-2 text-theme-dim list-decimal list-inside">
            <li>{t('guide:admin.workflow1')}</li>
            <li>{t('guide:admin.workflow2')}</li>
            <li>{t('guide:admin.workflow3')}</li>
            <li>{t('guide:admin.workflow4')}</li>
            <li>{t('guide:admin.workflow5')}</li>
            <li>{t('guide:admin.workflow6')}</li>
            <li>{t('guide:admin.workflow7')}</li>
            <li>{t('guide:admin.workflow8')}</li>
          </ol>
        </section>
      </div>
    </div>
  );
}
