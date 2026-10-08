import { useTranslation } from 'react-i18next';
import { Lightbulb, ListOrdered, Shield, Crown, Edit, Map as MapIcon, EyeOff } from 'lucide-react';
import { SVS_PATHS } from './paths';
import { usePageTitle } from '../../shared/usePageTitle';
import { GuideList, GuideNote, GuideSection, GuideTips, PlayerGuideFrame } from '../../shared/guide/GuideBits';
import { RatioBar } from './plan/bits';

// /svs/guide: the SVS player guide (guide:svsPlayer.*): the sign-up (SvsWizard.tsx) and how to read the shared
// battle plan (plan/SvsPlanView.tsx; its help link opens #plan). Static text only: it never shows a real plan.
// Keep it in step with those screens: see docs/GUIDES.md.
export default function SvsGuide() {
  const { t } = useTranslation();
  const k = (key: string) => t(`guide:svsPlayer.${key}`);
  usePageTitle(k('title'), t('svs:name'));

  return (
    <PlayerGuideFrame
      testId="player-guide-svs"
      backTo={SVS_PATHS.home}
      backLabel={t('svs:apply.backHome')}
      title={k('title')}
      subtitle={k('subtitle')}
    >
      <GuideSection icon={Lightbulb} title={k('whatIsTitle')}>
        <p>{k('whatIsBody')}</p>
      </GuideSection>

      <GuideSection icon={ListOrdered} title={k('stepsTitle')} id="apply">
        <GuideNote>{k('roundsNote')}</GuideNote>
        <p>{k('open')}</p>
        <GuideList t={k} ordered keys={['s1', 's2', 's3', 's4', 's5']} />
      </GuideSection>

      <GuideSection icon={Shield} title={k('troopsTitle')}>
        <GuideList t={k} keys={['troops1', 'troops2', 'troops3']} />
      </GuideSection>

      <GuideSection icon={Crown} title={k('leadersTitle')}>
        <GuideList t={k} keys={['leaders1', 'leaders2']} />
      </GuideSection>

      <GuideSection icon={Edit} title={k('editTitle')} tone="success">
        <GuideList t={k} keys={['edit1', 'edit2']} />
      </GuideSection>

      <GuideSection icon={MapIcon} title={k('planTitle')} id="plan" testId="guide-plan-section">
        <p>{k('planIntro')}</p>
        <GuideList t={k} ordered keys={['planFind', 'planGroups', 'planLeader', 'planSplit', 'planJoiners', 'planEveryone', 'planPet', 'planTimes']} />
        <div className="rounded-lg bg-dark-bg border border-theme-border p-3">
          <p className="text-xs text-theme-dim mb-2">{k('ratioExample')}</p>
          <RatioBar ratio={{ inf: 50, lan: 20, mks: 30 }} />
        </div>
      </GuideSection>

      <GuideSection icon={EyeOff} title={k('disguiseTitle')} id="secret" tone="warning">
        <GuideList t={k} keys={['disguise1', 'disguise2', 'disguise3', 'disguise4']} />
      </GuideSection>

      <GuideTips t={k} title={k('tipsTitle')} keys={['tip1', 'tip2', 'tip3']} />
    </PlayerGuideFrame>
  );
}
