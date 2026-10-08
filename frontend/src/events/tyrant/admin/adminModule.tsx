import { Flame, Users, Settings } from 'lucide-react';
import type { Round } from '../../../shared/api';
import type { AdminEventModule } from '../../../admin/types';
import type { TyrantSettings } from '../api';
import { TYRANT_PATHS } from '../paths';
import TyrantPlayers from './TyrantPlayers';
import TyrantRoundSettings from './TyrantRoundSettings';
import TyrantAdminGuide from './TyrantAdminGuide';

// The shell is event-agnostic (Round defaults to ministry settings); this event's rounds carry TyrantSettings.
type TRound = Round<TyrantSettings>;

// Frost Dragon Tyrant's plug-in for the shared admin shell (admin/registry.ts).
// Players tab = tyrantpoll's admin page (stats cards, search, filters, sortable
// table, delete, CSV + Excel); Settings tab = time windows + closing time.
const tyrantAdmin: AdminEventModule = {
  key: 'tyrant',
  label: 'tyrant:name',
  subtitle: 'tyrant:admin.adminSubtitle',
  icon: Flame,
  publicPath: TYRANT_PATHS.home,
  Guide: TyrantAdminGuide,
  defaultRoundName: (t, date) => t('tyrant:admin.defaultRoundName', { date }),
  tabs: [
    {
      key: 'players',
      label: 'admin:players',
      icon: Users,
      needsRound: true,
      render: ({ round, readOnly, reloadRounds }) =>
        round && <TyrantPlayers key={round.id} round={round as unknown as TRound} readOnly={readOnly} onChanged={() => reloadRounds()} />,
    },
    {
      key: 'settings',
      label: 'admin:settings',
      icon: Settings,
      needsRound: true,
      render: ({ round, readOnly, onRoundUpdated }) =>
        round && (
          <TyrantRoundSettings
            key={round.id}
            round={round as unknown as TRound}
            readOnly={readOnly}
            onSaved={(r) => onRoundUpdated(r as unknown as Round)}
          />
        ),
    },
  ],
};

export default tyrantAdmin;
