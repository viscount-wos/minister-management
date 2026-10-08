import { useTranslation } from 'react-i18next';
import { LogIn, RefreshCw, PlusCircle, Pencil, Clock, UserPlus, Filter, Hash, Link2, Gauge } from 'lucide-react';
import { GuideList, GuideSection } from '../shared/guide/GuideBits';

// "Event Management basics" (guide:basics.*): what works the same in every event (AdminShell, AdminLogin,
// StartNewRoundDialog, RenameRound, AddPlayerDialog, the closing-time inputs, HeroGenerationSetting, rate limits).
// Shown by AdminGuidePage at /admin/guide?event=<key>&topic=basics. See docs/GUIDES.md.
export default function EventBasicsGuide() {
  const { t } = useTranslation();
  const k = (key: string) => t(`guide:basics.${key}`);

  return (
    <div data-testid="admin-guide-basics">
      <p className="text-theme-dim mb-6 sm:mb-8">{k('subtitle')}</p>
      <div className="space-y-6 sm:space-y-8">
        <GuideSection icon={LogIn} title={k('loginTitle')}>
          <GuideList t={k} keys={['login1', 'login2', 'login3', 'login4']} />
        </GuideSection>
        <GuideSection icon={RefreshCw} title={k('roundsTitle')}>
          <p>{k('roundsBody')}</p>
          <GuideList t={k} keys={['rounds1', 'rounds2', 'rounds3', 'rounds4']} />
        </GuideSection>
        <GuideSection icon={PlusCircle} title={k('startTitle')}>
          <GuideList t={k} ordered keys={['start1', 'start2', 'start3', 'start4']} />
        </GuideSection>
        <GuideSection icon={Pencil} title={k('renameTitle')}>
          <p>{k('rename1')}</p>
        </GuideSection>
        <GuideSection icon={Clock} title={k('closingTitle')}>
          <GuideList t={k} keys={['closing1', 'closing2', 'closing3', 'closing4']} />
        </GuideSection>
        <GuideSection icon={UserPlus} title={k('addTitle')}>
          <GuideList t={k} ordered keys={['add1', 'add2', 'add3', 'add4']} />
        </GuideSection>
        <GuideSection icon={Filter} title={k('exportTitle')}>
          <GuideList t={k} keys={['export1', 'export2', 'export3']} />
        </GuideSection>
        <GuideSection icon={Hash} title={k('stateTitle')}>
          <GuideList t={k} keys={['state1', 'state2']} />
        </GuideSection>
        <GuideSection icon={Link2} title={k('linksTitle')}>
          <GuideList t={k} keys={['links1', 'links2', 'links3']} />
        </GuideSection>
        <GuideSection icon={Gauge} title={k('limitsTitle')}>
          <GuideList t={k} keys={['limits1', 'limits2', 'limits3']} />
        </GuideSection>
      </div>
    </div>
  );
}
