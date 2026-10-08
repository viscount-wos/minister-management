import { useTranslation } from 'react-i18next';
import { FileText, Edit, Clock, Palette, Globe, Lightbulb, Calendar, AlarmClock } from 'lucide-react';
import { MINISTRY_PATHS } from './paths';
import { useGuidesReady } from '../../shared/guide/useGuidesReady';
import { usePageTitle } from '../../shared/usePageTitle';
import { GuideList, GuideNote, GuideSection, GuideTips, PlayerGuideFrame } from '../../shared/guide/GuideBits';

// /minister/guide: the Minister player guide (guide:player.*). Keep it in step with the wizard
// (ApplicationWizard.tsx), MinistryHome and PublishedSchedule: see docs/GUIDES.md.
export default function PlayerGuide() {
  const { t } = useTranslation();
  const k = (key: string) => t(`guide:player.${key}`);
  const ready = useGuidesReady();
  usePageTitle(ready && k('title'), t('ministry:event.name'));

  return (
    <PlayerGuideFrame
      ready={ready}
      testId="player-guide-ministry"
      backTo={MINISTRY_PATHS.home}
      backLabel={t('ministry:update.backHome')}
      title={k('title')}
      subtitle={k('subtitle')}
    >
      <GuideSection icon={Lightbulb} title={k('whatIsTitle')}>
        <p>{k('whatIsBody')}</p>
      </GuideSection>

      <GuideSection icon={FileText} title={k('submitTitle')} id="apply">
        <GuideNote>{k('roundsNote')}</GuideNote>
        <div>
          <h3 className="text-lg font-semibold text-theme-text mb-2">{k('step1Header')}</h3>
          <GuideList t={k} keys={['step1Fid', 'step1Profile', 'step1Furnace', 'step1Speedups', 'step1General']} />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-theme-text mb-2">{k('step2Header')}</h3>
          <GuideList t={k} keys={['step2Select', 'step2Days', 'step2Timezone', 'step2Tolerance', 'step2Empty']} />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-theme-text mb-2">{k('step3Header')}</h3>
          <p>{k('step3Body')}</p>
        </div>
      </GuideSection>

      <GuideSection icon={Palette} title={k('heatmapTitle')}>
        <p>{k('heatmapBody')}</p>
        <div className="flex flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-heat-low/40 border border-heat-low/70"></div>
            <span className="text-sm">{k('heatmapBlue')}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-heat-mid/40 border border-heat-mid/70"></div>
            <span className="text-sm">{k('heatmapYellow')}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-heat-high/40 border border-heat-high/70"></div>
            <span className="text-sm">{k('heatmapRed')}</span>
          </div>
        </div>
        <p className="text-sm italic">{k('heatmapTip')}</p>
      </GuideSection>

      <GuideSection icon={AlarmClock} title={k('deadlineTitle')}>
        <GuideList t={k} keys={['deadline1', 'deadline2']} />
      </GuideSection>

      <GuideSection icon={Edit} title={k('updateTitle')} tone="success">
        <p>{k('updateBody1')}</p>
        <GuideList t={k} ordered keys={['updateStep1', 'updateStep2', 'updateStep3', 'updateStep4']} />
        <p className="text-sm italic">{k('updateNote')}</p>
      </GuideSection>

      <GuideSection icon={Clock} title={k('assignmentsTitle')}>
        <p>{k('assignmentsBody')}</p>
        <GuideList t={k} keys={['assignmentsPoint1', 'assignmentsPoint2', 'assignmentsPoint3', 'assignmentsPoint4']} />
      </GuideSection>

      <GuideSection icon={Calendar} title={k('scheduleTitle')}>
        <GuideList t={k} keys={['schedule1', 'schedule2', 'schedule3']} />
      </GuideSection>

      <GuideSection icon={Globe} title={k('timezoneTitle')}>
        <p>{k('timezoneBody')}</p>
      </GuideSection>

      <GuideTips t={k} title={k('tipsTitle')} keys={['tip1', 'tip2', 'tip3', 'tip4', 'tip5']} />
    </PlayerGuideFrame>
  );
}
