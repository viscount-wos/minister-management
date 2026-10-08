import type { ComponentType, ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import type { TFunction } from 'i18next';
import type { EventKey, Round } from '../shared/api';

// Contract between the shared admin shell ("Event Management") and one event's
// admin screens. An event plugs in by exporting an AdminEventModule and adding
// it to ADMIN_EVENTS in ./registry.ts; nothing else in the shell changes.

/** What the shell hands to every tab of the selected event. */
export interface AdminTabContext {
  /** Selected round (the current one by default); null when the event has no rounds yet. */
  round: Round | null;
  /** True for past (closed) rounds and when there is no round. */
  readOnly: boolean;
  /** Reload the round list (e.g. application counts changed); optionally select a round. */
  reloadRounds: (select?: number) => void;
  /** Merge an updated round (settings, closing time, name) into the shell's list. */
  onRoundUpdated: (round: Round) => void;
}

export interface AdminTab {
  /** Test id `tab-<key>`; must be unique within the event. */
  key: string;
  /** i18n key of the tab label. */
  label: string;
  icon: LucideIcon;
  /** Show the shared "no rounds yet" card instead of render() when there is no round. */
  needsRound?: boolean;
  /** Desktop-first boards (the SVS battle planner) get the full screen width instead of the 7xl column. */
  wide?: boolean;
  render: (ctx: AdminTabContext) => ReactNode;
}

export interface AdminEventModule {
  key: EventKey;
  /** i18n key of the event name (switch, titles). */
  label: string;
  /** i18n key of the contextual dashboard subtitle, e.g. "Ministry: applications and assignments". */
  subtitle: string;
  icon: LucideIcon;
  /** The event's public page (logout and "back" go here). */
  publicPath: string;
  tabs: AdminTab[];
  /** Body of this event's admin guide (rendered under the shared guide header). */
  Guide: ComponentType;
  /** Suggested name in the Start new round dialog (default: admin:round.defaultName). */
  defaultRoundName?: (t: TFunction, date: string) => string;
}
