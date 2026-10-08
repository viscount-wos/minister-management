import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, FileText, Edit, Clock, Palette, Globe, Lightbulb } from 'lucide-react';
import { MINISTRY_PATHS } from './paths';

export default function PlayerGuide() {
  const navigate = useNavigate();
  const { t } = useTranslation();

  return (
    <div className="min-h-screen bg-dark-bg py-8 px-4">
      <div className="max-w-3xl mx-auto">
        <button
          onClick={() => navigate(MINISTRY_PATHS.home)}
          className="flex items-center gap-2 text-theme-dim hover:text-accent transition-colors mb-6"
        >
          <ArrowLeft className="w-5 h-5" />
          {t('ministry:update.backHome')}
        </button>

        <h1 className="text-4xl font-bold text-accent mb-2">{t('guide:player.title')}</h1>
        <p className="text-theme-dim mb-8">{t('guide:player.subtitle')}</p>

        <div className="space-y-8">
          {/* What is this system? */}
          <section className="bg-dark-card rounded-xl border border-theme-border p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
                <Lightbulb className="w-5 h-5 text-accent" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text">{t('guide:player.whatIsTitle')}</h2>
            </div>
            <p className="text-theme-dim leading-relaxed">{t('guide:player.whatIsBody')}</p>
          </section>

          {/* Step 1: Submitting */}
          <section className="bg-dark-card rounded-xl border border-theme-border p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
                <FileText className="w-5 h-5 text-accent" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text">{t('guide:player.submitTitle')}</h2>
            </div>
            <div className="space-y-4 text-theme-dim leading-relaxed">
              <p className="p-3 bg-accent/10 border border-accent/30 rounded-lg text-accent text-sm">
                {t('guide:player.roundsNote')}
              </p>
              <div>
                <h3 className="text-lg font-semibold text-theme-text mb-2">{t('guide:player.step1Header')}</h3>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>{t('guide:player.step1Fid')}</li>
                  <li>{t('guide:player.step1Alliance')}</li>
                  <li>{t('guide:player.step1Speedups')}</li>
                  <li>{t('guide:player.step1General')}</li>
                </ul>
              </div>
              <div>
                <h3 className="text-lg font-semibold text-theme-text mb-2">{t('guide:player.step2Header')}</h3>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>{t('guide:player.step2Select')}</li>
                  <li>{t('guide:player.step2Days')}</li>
                  <li>{t('guide:player.step2Timezone')}</li>
                  <li>{t('guide:player.step2Tolerance')}</li>
                </ul>
              </div>
              <div>
                <h3 className="text-lg font-semibold text-theme-text mb-2">{t('guide:player.step3Header')}</h3>
                <p>{t('guide:player.step3Body')}</p>
              </div>
            </div>
          </section>

          {/* Heat Map */}
          <section className="bg-dark-card rounded-xl border border-theme-border p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
                <Palette className="w-5 h-5 text-accent" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text">{t('guide:player.heatmapTitle')}</h2>
            </div>
            <div className="text-theme-dim leading-relaxed space-y-3">
              <p>{t('guide:player.heatmapBody')}</p>
              <div className="flex flex-wrap gap-3 mt-3">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded bg-heat-low/40 border border-heat-low/70"></div>
                  <span className="text-sm">{t('guide:player.heatmapBlue')}</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded bg-heat-mid/40 border border-heat-mid/70"></div>
                  <span className="text-sm">{t('guide:player.heatmapYellow')}</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded bg-heat-high/40 border border-heat-high/70"></div>
                  <span className="text-sm">{t('guide:player.heatmapRed')}</span>
                </div>
              </div>
              <p className="text-sm italic">{t('guide:player.heatmapTip')}</p>
            </div>
          </section>

          {/* Viewing & Updating */}
          <section className="bg-dark-card rounded-xl border border-theme-border p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-success/20 rounded-full flex items-center justify-center">
                <Edit className="w-5 h-5 text-success" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text">{t('guide:player.updateTitle')}</h2>
            </div>
            <div className="text-theme-dim leading-relaxed space-y-3">
              <p>{t('guide:player.updateBody1')}</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>{t('guide:player.updateStep1')}</li>
                <li>{t('guide:player.updateStep2')}</li>
                <li>{t('guide:player.updateStep3')}</li>
                <li>{t('guide:player.updateStep4')}</li>
              </ul>
              <p className="text-sm italic">{t('guide:player.updateNote')}</p>
            </div>
          </section>

          {/* Understanding Assignments */}
          <section className="bg-dark-card rounded-xl border border-theme-border p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
                <Clock className="w-5 h-5 text-accent" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text">{t('guide:player.assignmentsTitle')}</h2>
            </div>
            <div className="text-theme-dim leading-relaxed space-y-3">
              <p>{t('guide:player.assignmentsBody')}</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>{t('guide:player.assignmentsPoint1')}</li>
                <li>{t('guide:player.assignmentsPoint2')}</li>
                <li>{t('guide:player.assignmentsPoint3')}</li>
                <li>{t('guide:player.assignmentsPoint4')}</li>
              </ul>
            </div>
          </section>

          {/* Timezone */}
          <section className="bg-dark-card rounded-xl border border-theme-border p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-accent/20 rounded-full flex items-center justify-center">
                <Globe className="w-5 h-5 text-accent" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text">{t('guide:player.timezoneTitle')}</h2>
            </div>
            <div className="text-theme-dim leading-relaxed space-y-3">
              <p>{t('guide:player.timezoneBody')}</p>
            </div>
          </section>

          {/* Tips */}
          <section className="bg-accent/10 border border-accent/30 rounded-xl p-6">
            <h2 className="text-2xl font-bold text-accent mb-4">{t('guide:player.tipsTitle')}</h2>
            <ul className="space-y-2 text-theme-dim">
              <li className="flex items-start gap-2">
                <span className="text-accent mt-1">✦</span>
                <span>{t('guide:player.tip1')}</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-accent mt-1">✦</span>
                <span>{t('guide:player.tip2')}</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-accent mt-1">✦</span>
                <span>{t('guide:player.tip3')}</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-accent mt-1">✦</span>
                <span>{t('guide:player.tip4')}</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-accent mt-1">✦</span>
                <span>{t('guide:player.tip5')}</span>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
