// A main / counter group column (name, alliance tag, joining minimums, notes, its leaders) and the light "extra"
// group card (name, players, notes).
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { Plus, StickyNote, Trash2, UserPlus, X } from 'lucide-react';
import { TroopIcon } from '../../../shared/heroes/HeroCard';
import { FC_LEVELS } from '../../../shared/furnace';
import { usePlanner } from './PlannerContext';
import LeaderCard from './LeaderCard';
import PlayerSearch from './PlayerSearch';
import { PlayerName } from './widgets';
import { TEAM } from './bits';
import { TROOPS, blankLeader, leadersOf, renumber } from './model';
import type { PlanGroup, TroopKey } from './model';

function GroupFields({ group }: { group: PlanGroup }) {
  const { t } = useTranslation();
  const { update, readOnly, groupLabel } = usePlanner();
  const G = (fn: (g: PlanGroup) => void) =>
    update((d) => {
      const g = d.groups.find((x) => x.id === group.id);
      if (g) fn(g);
    });
  return (
    <div className="flex flex-wrap gap-2">
      <input
        value={group.name ?? ''}
        disabled={readOnly}
        maxLength={40}
        placeholder={groupLabel({ ...group, name: null })}
        aria-label={t('svs:plan.groupName')}
        onChange={(e) => G((g) => (g.name = e.target.value || null))}
        data-testid="group-name"
        className="flex-1 min-w-[8rem] min-h-[36px] px-2 text-base font-bold bg-dark-input border border-theme-border rounded-md text-theme-text"
      />
      <input
        value={group.alliance_tag ?? ''}
        disabled={readOnly}
        maxLength={10}
        placeholder={t('svs:plan.tagPlaceholder')}
        aria-label={t('svs:plan.allianceTag')}
        onChange={(e) => G((g) => (g.alliance_tag = e.target.value || null))}
        data-testid="group-tag"
        className="w-24 min-h-[36px] px-2 text-sm font-semibold uppercase bg-dark-input border border-theme-border rounded-md text-accent"
      />
    </div>
  );
}

function Notes({ group }: { group: PlanGroup }) {
  const { t } = useTranslation();
  const { update, readOnly } = usePlanner();
  const [open, setOpen] = useState(!!group.notes);
  if (!open && !group.notes) {
    return readOnly ? null : (
      <button type="button" onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 text-xs text-theme-dim hover:text-accent" data-testid="notes-open">
        <StickyNote className="w-4 h-4" aria-hidden="true" />
        {t('svs:plan.addNotes')}
      </button>
    );
  }
  return (
    <label className="block">
      <span className="flex items-center gap-1.5 text-xs text-theme-dim mb-1">
        <StickyNote className="w-4 h-4" aria-hidden="true" />
        {t('svs:plan.notes')}
      </span>
      <textarea
        value={group.notes ?? ''}
        disabled={readOnly}
        maxLength={2000}
        rows={2}
        placeholder={t('svs:plan.notesPlaceholder')}
        onChange={(e) =>
          update((d) => {
            const g = d.groups.find((x) => x.id === group.id);
            if (g) g.notes = e.target.value || null;
          })
        }
        data-testid="group-notes"
        className="w-full px-2 py-1.5 text-sm bg-dark-input border border-theme-border rounded-md text-theme-text"
      />
    </label>
  );
}

const FC_ONLY = FC_LEVELS;

function Minimums({ group }: { group: PlanGroup }) {
  const { t } = useTranslation();
  const { update, readOnly } = usePlanner();
  const mins = group.min_requirements!;
  const set = (k: TroopKey, field: 'min_camp' | 'min_tier', v: string) =>
    update((d) => {
      const g = d.groups.find((x) => x.id === group.id);
      if (!g?.min_requirements) return;
      g.min_requirements[k] = { ...g.min_requirements[k], [field]: v === '' ? null : field === 'min_tier' ? Number(v) : v };
    });
  return (
    <fieldset className="rounded-lg border border-theme-border/60 p-2" data-testid="group-minimums">
      <legend className="px-1 text-xs font-bold uppercase tracking-wide text-theme-dim">{t('svs:plan.minimums')}</legend>
      <p className="text-[11px] text-theme-dim mb-1.5">{t('svs:plan.minimumsHint')}</p>
      <div className="grid grid-cols-3 gap-2">
        {TROOPS.map((k) => (
          <div key={k} className="min-w-0">
            <div className="flex items-center gap-1 text-xs text-theme-text mb-1">
              <TroopIcon troop={k} className="w-3.5 h-3.5" />
              <span className="truncate">{t(`tyrant:admin.troopName.${k}`)}</span>
            </div>
            <div className="flex gap-1">
              <select
                value={mins[k]?.min_camp ?? ''}
                disabled={readOnly}
                onChange={(e) => set(k, 'min_camp', e.target.value)}
                aria-label={t('svs:plan.minCamp', { troop: t(`tyrant:admin.troopName.${k}`) })}
                data-testid={`min-${k}-camp`}
                className="min-w-0 flex-1 min-h-[32px] px-1 text-xs bg-dark-input border border-theme-border rounded text-theme-text"
              >
                <option value="">{t('svs:plan.anyCamp')}</option>
                {FC_ONLY.map((c) => (
                  <option key={c} value={c}>
                    {c}+
                  </option>
                ))}
              </select>
              <select
                value={mins[k]?.min_tier ?? ''}
                disabled={readOnly}
                onChange={(e) => set(k, 'min_tier', e.target.value)}
                aria-label={t('svs:plan.minTier', { troop: t(`tyrant:admin.troopName.${k}`) })}
                data-testid={`min-${k}-tier`}
                className="w-14 min-h-[32px] px-1 text-xs bg-dark-input border border-theme-border rounded text-theme-text"
              >
                <option value="">{t('svs:plan.anyTier')}</option>
                <option value="11">T11</option>
                <option value="10">T10+</option>
              </select>
            </div>
          </div>
        ))}
      </div>
    </fieldset>
  );
}

export function GroupColumn({ group, wide = false }: { group: PlanGroup; wide?: boolean }) {
  const { t } = useTranslation();
  const ctx = usePlanner();
  const leaders = leadersOf(ctx.doc, group.id);
  const team = TEAM[group.kind];
  const { setNodeRef: colRef, isOver: colOver } = useDroppable({
    id: `groupcol-${group.id}`,
    data: { type: 'group', accepts: ['leader'], groupId: group.id },
    disabled: ctx.readOnly,
  });
  const { setNodeRef: newRef, isOver: newOver } = useDroppable({
    id: `newleader-${group.id}`,
    data: { type: 'playerTarget', accepts: ['player'], target: { kind: 'newLeader', groupId: group.id } },
    disabled: ctx.readOnly,
  });

  return (
    <section
      ref={colRef}
      className={`min-w-0 rounded-xl border-2 ${team.border} ${colOver ? `${team.bg} ring-2 ${team.ring}` : 'bg-dark-card/40'} transition-colors`}
      data-testid={`group-${group.kind}`}
      data-group-id={group.id}
      aria-label={ctx.groupLabel(group)}
    >
      <header className={`rounded-t-[10px] ${team.bg} border-b ${team.border} p-3 space-y-2`}>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded-md ${team.bar} text-dark-bg text-xs font-extrabold uppercase tracking-wider`}>
            {t(`svs:plan.kind.${group.kind}`)}
          </span>
          <span className="text-xs text-theme-dim" data-testid="leader-count">
            {t('svs:plan.leaderCount', { n: leaders.length })}
          </span>
        </div>
        <GroupFields group={group} />
        <Minimums group={group} />
        <Notes group={group} />
      </header>
      <div className="p-3 space-y-3">
        <SortableContext items={leaders.map((l) => l.id)} strategy={verticalListSortingStrategy}>
          <div className={wide ? 'grid grid-cols-1 xl:grid-cols-2 gap-3 items-start' : 'space-y-3'}>
            {leaders.map((l, i) => (
              <LeaderCard key={l.id} leader={l} group={group} number={i + 1} />
            ))}
          </div>
        </SortableContext>
        {!ctx.readOnly && (
          <div
            ref={newRef}
            className={`rounded-xl border-2 border-dashed p-3 flex flex-wrap items-center gap-3 ${
              newOver ? 'border-success bg-success/10' : 'border-theme-border/60'
            }`}
            data-testid="new-leader-drop"
          >
            <button
              type="button"
              onClick={() =>
                ctx.update((d) => {
                  d.leaders.push(blankLeader(group.id));
                  renumber(d);
                })
              }
              data-testid="add-leader"
              className={`inline-flex items-center gap-2 min-h-[40px] px-3 rounded-lg ${team.bar} text-dark-bg text-sm font-bold hover:opacity-90`}
            >
              <Plus className="w-4 h-4" aria-hidden="true" />
              {t('svs:plan.addLeader')}
            </button>
            <span className="text-xs text-theme-dim">{t('svs:plan.dropToAddLeader')}</span>
          </div>
        )}
      </div>
    </section>
  );
}

export function ExtraGroupCard({ group }: { group: PlanGroup }) {
  const { t } = useTranslation();
  const ctx = usePlanner();
  const team = TEAM.extra;
  const players = group.players ?? [];
  const { setNodeRef, isOver } = useDroppable({
    id: `extragroup-${group.id}`,
    data: { type: 'playerTarget', accepts: ['player'], target: { kind: 'extraGroup', groupId: group.id } },
    disabled: ctx.readOnly,
  });
  return (
    <section
      ref={setNodeRef}
      className={`min-w-0 rounded-xl border-2 ${team.border} ${isOver ? 'bg-success/10' : 'bg-dark-card/40'} p-3 space-y-2`}
      data-testid="group-extra"
      data-group-id={group.id}
      aria-label={ctx.groupLabel(group)}
    >
      <div className="flex items-center gap-2">
        <span className={`px-2 py-0.5 rounded-md ${team.bar} text-dark-bg text-xs font-extrabold uppercase tracking-wider`}>{t('svs:plan.kind.extra')}</span>
        <span className="text-xs text-theme-dim">{t('svs:plan.playerCount', { n: players.length })}</span>
        {!ctx.readOnly && (
          <button
            type="button"
            onClick={() => {
              if (window.confirm(t('svs:plan.confirmDeleteGroup', { name: ctx.groupLabel(group) })))
                ctx.update((d) => void (d.groups = d.groups.filter((g) => g.id !== group.id)));
            }}
            aria-label={t('svs:plan.deleteGroup', { name: ctx.groupLabel(group) })}
            data-testid="delete-group"
            className="ms-auto w-8 h-8 rounded-md text-theme-dim hover:text-danger flex items-center justify-center"
          >
            <Trash2 className="w-4 h-4" aria-hidden="true" />
          </button>
        )}
      </div>
      <GroupFields group={group} />
      <Notes group={group} />
      <ul className="flex flex-wrap gap-1.5">
        {players.map((p, i) => (
          <li key={i} className="inline-flex items-center gap-1 ps-2 pe-1 py-0.5 rounded-full bg-dark-input border border-theme-border text-xs" data-testid="extra-group-chip">
            <PlayerName player={p} />
            {!ctx.readOnly && (
              <button
                type="button"
                onClick={() =>
                  ctx.update((d) => {
                    d.groups.find((g) => g.id === group.id)?.players?.splice(i, 1);
                  })
                }
                aria-label={t('svs:plan.removePlayer', { name: ctx.playerName(p) })}
                className="w-5 h-5 rounded-full text-theme-dim hover:text-danger flex items-center justify-center"
              >
                <X className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            )}
          </li>
        ))}
      </ul>
      {!ctx.readOnly && (
        <div className="flex items-center gap-2">
          <UserPlus className="w-4 h-4 text-theme-dim shrink-0" aria-hidden="true" />
          <PlayerSearch target={{ kind: 'extraGroup', groupId: group.id }} placeholder={t('svs:plan.addToGroup')} testid="extra-group-search" />
        </div>
      )}
    </section>
  );
}
