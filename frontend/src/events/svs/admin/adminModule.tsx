import { Castle, Users, Settings, Image, Swords } from 'lucide-react';
import type { Round } from '../../../shared/api';
import type { AdminEventModule } from '../../../admin/types';
import type { SvsSettings } from '../api';
import { SVS_PATHS } from '../paths';
import SvsPlayers from './SvsPlayers';
import SvsRoundSettings from './SvsRoundSettings';
import SvsHeroes from './SvsHeroes';
import SvsAdminGuide from './SvsAdminGuide';
import SvsPlanner from '../plan/SvsPlanner';

type SRound = Round<SvsSettings>;

// SVS's plug-in for the shared admin shell (admin/registry.ts): Players (stats, breakdowns, chips, filters, table,
// exports, add player), Battle plan (the drag-and-drop planner, full width), Settings (battle start + duration, closing time) and Heroes (the hero library as planners
// will see it, plus the state's hero generation; needs no round).
const svsAdmin: AdminEventModule = {
  key: 'svs',
  label: 'svs:name',
  subtitle: 'svs:admin.adminSubtitle',
  icon: Castle,
  publicPath: SVS_PATHS.home,
  Guide: SvsAdminGuide,
  defaultRoundName: (t, date) => t('svs:admin.defaultRoundName', { date }),
  tabs: [
    {
      key: 'players',
      label: 'admin:players',
      icon: Users,
      needsRound: true,
      render: ({ round, readOnly, reloadRounds }) =>
        round && <SvsPlayers key={round.id} round={round as unknown as SRound} readOnly={readOnly} onChanged={() => reloadRounds()} />,
    },
    {
      key: 'plan',
      label: 'svs:plan.tab',
      icon: Swords,
      needsRound: true,
      wide: true,
      render: ({ round, readOnly }) => round && <SvsPlanner key={round.id} round={round as unknown as SRound} readOnly={readOnly} />,
    },
    {
      key: 'settings',
      label: 'admin:settings',
      icon: Settings,
      needsRound: true,
      render: ({ round, readOnly, onRoundUpdated }) =>
        round && (
          <SvsRoundSettings key={round.id} round={round as unknown as SRound} readOnly={readOnly} onSaved={(r) => onRoundUpdated(r as unknown as Round)} />
        ),
    },
    {
      key: 'heroes',
      label: 'admin:heroes.tab',
      icon: Image,
      render: () => <SvsHeroes />,
    },
  ],
};

export default svsAdmin;
