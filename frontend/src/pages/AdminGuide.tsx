import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, Users, Calendar, Upload, Download, Lock, GripVertical, FileSpreadsheet, Globe, Settings } from 'lucide-react';

export default function AdminGuide() {
  const navigate = useNavigate();
  const { t } = useTranslation();

  return (
    <div className="min-h-screen bg-dark-bg py-8 px-4">
      <div className="max-w-3xl mx-auto">
        <button
          onClick={() => navigate('/admin/dashboard')}
          className="flex items-center gap-2 text-theme-dim hover:text-accent transition-colors mb-6"
        >
          <ArrowLeft className="w-5 h-5" />
          {t('adminGuide.backToDashboard')}
        </button>

        <h1 className="text-4xl font-bold text-accent mb-2">{t('adminGuide.title')}</h1>
        <p className="text-theme-dim mb-8">{t('adminGuide.subtitle')}</p>

        <div className="space-y-8">
          {/* Overview */}
          <section className="bg-dark-card rounded-xl border border-theme-border p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
                <Settings className="w-5 h-5 text-accent" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text">{t('adminGuide.overviewTitle')}</h2>
            </div>
            <p className="text-theme-dim leading-relaxed">{t('adminGuide.overviewBody')}</p>
          </section>

          {/* Player Management */}
          <section className="bg-dark-card rounded-xl border border-theme-border p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
                <Users className="w-5 h-5 text-accent" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text">{t('adminGuide.playersTitle')}</h2>
            </div>
            <div className="text-theme-dim leading-relaxed space-y-4">
              <div>
                <h3 className="text-lg font-semibold text-theme-text mb-2">{t('adminGuide.playersViewHeader')}</h3>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>{t('adminGuide.playersView1')}</li>
                  <li>{t('adminGuide.playersView2')}</li>
                  <li>{t('adminGuide.playersView3')}</li>
                  <li>{t('adminGuide.playersView4')}</li>
                </ul>
              </div>
              <div>
                <h3 className="text-lg font-semibold text-theme-text mb-2">{t('adminGuide.playersEditHeader')}</h3>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>{t('adminGuide.playersEdit1')}</li>
                  <li>{t('adminGuide.playersEdit2')}</li>
                  <li>{t('adminGuide.playersEdit3')}</li>
                </ul>
              </div>
              <div>
                <h3 className="text-lg font-semibold text-theme-text mb-2">{t('adminGuide.playersDeleteHeader')}</h3>
                <p>{t('adminGuide.playersDeleteBody')}</p>
              </div>
            </div>
          </section>

          {/* Export / Import */}
          <section className="bg-dark-card rounded-xl border border-theme-border p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
                <Download className="w-5 h-5 text-accent" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text">{t('adminGuide.exportImportTitle')}</h2>
            </div>
            <div className="text-theme-dim leading-relaxed space-y-4">
              <div>
                <h3 className="text-lg font-semibold text-theme-text mb-2 flex items-center gap-2">
                  <Download className="w-4 h-4" /> {t('adminGuide.exportHeader')}
                </h3>
                <p>{t('adminGuide.exportBody')}</p>
              </div>
              <div>
                <h3 className="text-lg font-semibold text-theme-text mb-2 flex items-center gap-2">
                  <Upload className="w-4 h-4" /> {t('adminGuide.importHeader')}
                </h3>
                <p>{t('adminGuide.importBody')}</p>
              </div>
            </div>
          </section>

          {/* Assignment Management */}
          <section className="bg-dark-card rounded-xl border border-theme-border p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
                <Calendar className="w-5 h-5 text-accent" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text">{t('adminGuide.assignTitle')}</h2>
            </div>
            <div className="text-theme-dim leading-relaxed space-y-4">
              <div>
                <h3 className="text-lg font-semibold text-theme-text mb-2">{t('adminGuide.autoAssignHeader')}</h3>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>{t('adminGuide.autoAssign1')}</li>
                  <li>{t('adminGuide.autoAssign2')}</li>
                  <li>{t('adminGuide.autoAssign3')}</li>
                  <li>{t('adminGuide.autoAssign4')}</li>
                </ul>
              </div>
              <div>
                <h3 className="text-lg font-semibold text-theme-text mb-2 flex items-center gap-2">
                  <GripVertical className="w-4 h-4" /> {t('adminGuide.dragDropHeader')}
                </h3>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>{t('adminGuide.dragDrop1')}</li>
                  <li>{t('adminGuide.dragDrop2')}</li>
                  <li>{t('adminGuide.dragDrop3')}</li>
                </ul>
              </div>
              <div>
                <h3 className="text-lg font-semibold text-theme-text mb-2 flex items-center gap-2">
                  <Lock className="w-4 h-4" /> {t('adminGuide.stickyHeader')}
                </h3>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>{t('adminGuide.sticky1')}</li>
                  <li>{t('adminGuide.sticky2')}</li>
                  <li>{t('adminGuide.sticky3')}</li>
                  <li>{t('adminGuide.sticky4')}</li>
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
              <h2 className="text-2xl font-bold text-theme-text">{t('adminGuide.researchDayTitle')}</h2>
            </div>
            <p className="text-theme-dim leading-relaxed">{t('adminGuide.researchDayBody')}</p>
          </section>

          {/* Settings Tab */}
          <section className="bg-dark-card rounded-xl border border-theme-border p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
                <Settings className="w-5 h-5 text-accent" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text">{t('adminGuide.settingsTitle')}</h2>
            </div>
            <div className="text-theme-dim leading-relaxed space-y-3">
              <p>{t('adminGuide.settingsBody')}</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>{t('adminGuide.settingsState')}</li>
                <li>{t('adminGuide.settingsClosing')}</li>
                <li>{t('adminGuide.settingsResearch')}</li>
                <li>{t('adminGuide.settingsFireCrystals')}</li>
              </ul>
            </div>
          </section>

          {/* Publishing */}
          <section className="bg-dark-card rounded-xl border border-theme-border p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-success/20 rounded-full flex items-center justify-center">
                <Calendar className="w-5 h-5 text-success" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text">{t('adminGuide.publishTitle')}</h2>
            </div>
            <div className="text-theme-dim leading-relaxed space-y-3">
              <p>{t('adminGuide.publishBody')}</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>{t('adminGuide.publish1')}</li>
                <li>{t('adminGuide.publish2')}</li>
                <li>{t('adminGuide.publish3')}</li>
              </ul>
            </div>
          </section>

          {/* Excel Export */}
          <section className="bg-dark-card rounded-xl border border-theme-border p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
                <FileSpreadsheet className="w-5 h-5 text-accent" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text">{t('adminGuide.excelTitle')}</h2>
            </div>
            <div className="text-theme-dim leading-relaxed space-y-3">
              <p>{t('adminGuide.excelBody')}</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>{t('adminGuide.excel1')}</li>
                <li>{t('adminGuide.excel2')}</li>
                <li>{t('adminGuide.excel3')}</li>
              </ul>
            </div>
          </section>

          {/* Workflow Tips */}
          <section className="bg-accent/10 border border-accent/30 rounded-xl p-6">
            <h2 className="text-2xl font-bold text-accent mb-4">{t('adminGuide.workflowTitle')}</h2>
            <ol className="space-y-2 text-theme-dim list-decimal list-inside">
              <li>{t('adminGuide.workflow1')}</li>
              <li>{t('adminGuide.workflow2')}</li>
              <li>{t('adminGuide.workflow3')}</li>
              <li>{t('adminGuide.workflow4')}</li>
              <li>{t('adminGuide.workflow5')}</li>
              <li>{t('adminGuide.workflow6')}</li>
              <li>{t('adminGuide.workflow7')}</li>
              <li>{t('adminGuide.workflow8')}</li>
            </ol>
          </section>
        </div>
      </div>
    </div>
  );
}
