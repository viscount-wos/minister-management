import { useTranslation } from 'react-i18next';
import { Lightbulb, ListOrdered, Shield, Globe, Edit, AlarmClock } from 'lucide-react';
import { TYRANT_PATHS } from './paths';
import { useGuidesReady } from '../../shared/guide/useGuidesReady';
import { usePageTitle } from '../../shared/usePageTitle';
import { GuideList, GuideNote, GuideSection, GuideTips, PlayerGuideFrame } from '../../shared/guide/GuideBits';

// /tyrant/guide: the Frost Dragon Tyrant player guide (guide:tyrantPlayer.*). Keep it in step with
// TyrantWizard.tsx and TyrantPage.tsx: see docs/GUIDES.md.
export default function TyrantGuide() {
  const { t } = useTranslation();
  const k = (key: string) => t(`guide:tyrantPlayer.${key}`);
  const ready = useGuidesReady();
  usePageTitle(ready && k('title'), t('tyrant:name'));

  return (
    <PlayerGuideFrame
      ready={ready}
      testId="player-guide-tyrant"
      backTo={TYRANT_PATHS.home}
      backLabel={t('tyrant:apply.backHome')}
      title={k('title')}
      subtitle={k('subtitle')}
    >
      <GuideSection icon={Lightbulb} title={k('whatIsTitle')}>
        <p>{k('whatIsBody')}</p>
      </GuideSection>

      <GuideSection icon={ListOrdered} title={k('stepsTitle')} id="apply">
        <GuideNote>{k('roundsNote')}</GuideNote>
        <p>{k('open')}</p>
        <GuideList t={k} ordered keys={['s1', 's2', 's3', 's4', 's5', 's6']} />
      </GuideSection>

      <GuideSection icon={Shield} title={k('campsTitle')} id="camps">
        <GuideList t={k} keys={['camps1', 'camps2', 'camps3', 'camps4']} />
      </GuideSection>

      <GuideSection icon={Globe} title={k('timesTitle')}>
        <GuideList t={k} keys={['times1', 'times2']} />
      </GuideSection>

      <GuideSection icon={Edit} title={k('editTitle')} tone="success">
        <GuideList t={k} ordered keys={['edit1', 'edit2', 'edit3']} />
      </GuideSection>

      <GuideSection icon={AlarmClock} title={k('deadlineTitle')}>
        <GuideList t={k} keys={['deadline1', 'deadline2']} />
      </GuideSection>

      <GuideTips t={k} title={k('tipsTitle')} keys={['tip1', 'tip2', 'tip3']} />
    </PlayerGuideFrame>
  );
}
