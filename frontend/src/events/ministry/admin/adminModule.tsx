import { Crown, Users, Calendar, Settings } from 'lucide-react';
import type { AdminEventModule } from '../../../admin/types';
import { MINISTRY_PATHS } from '../paths';
import PlayerManagement from './PlayerManagement';
import AssignmentManagement from './AssignmentManagement';
import AdminSettings from './AdminSettings';
import MinistryAdminGuide from './MinistryAdminGuide';

// Ministry's plug-in for the shared admin shell (admin/registry.ts).
const ministryAdmin: AdminEventModule = {
  key: 'ministry',
  label: 'ministry:event.name',
  subtitle: 'ministry:event.adminSubtitle',
  icon: Crown,
  publicPath: MINISTRY_PATHS.home,
  Guide: MinistryAdminGuide,
  defaultRoundName: (t, date) => t('admin:round.defaultName', { date }),
  tabs: [
    {
      key: 'players',
      label: 'admin:players',
      icon: Users,
      needsRound: true,
      render: ({ round, readOnly, reloadRounds }) =>
        round && <PlayerManagement key={round.id} round={round} readOnly={readOnly} onChanged={() => reloadRounds()} />,
    },
    {
      key: 'assignments',
      label: 'admin:assignments',
      icon: Calendar,
      needsRound: true,
      render: ({ round, readOnly, onRoundUpdated }) =>
        round && <AssignmentManagement key={round.id} round={round} readOnly={readOnly} onRoundUpdated={onRoundUpdated} />,
    },
    {
      // Also holds the global state number, so it works without a round.
      key: 'settings',
      label: 'admin:settings',
      icon: Settings,
      render: ({ round, readOnly, onRoundUpdated }) => (
        <AdminSettings key={round?.id ?? 'none'} round={round} readOnly={readOnly} onRoundUpdated={onRoundUpdated} />
      ),
    },
  ],
};

export default ministryAdmin;
