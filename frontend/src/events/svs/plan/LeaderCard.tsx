// One rally leader in the planner: disguise (top, collapsed when empty), the player, rally (+ garrison when split)
// heroes and ratios, pet buffs, 4 named joiners with lead heroes, "everyone else may use" heroes and extra joiners.
// The grip handle drags the card (mouse, touch long-press, keyboard); the menu moves it without dragging.
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDroppable } from '@dnd-kit/core';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { ChevronDown, ChevronUp, Drama, Swords, GripVertical, MoreVertical, PawPrint, Trash2, Users, X, ArrowRightLeft, ArrowUp, ArrowDown, SlidersHorizontal } from 'lucide-react';
import { usePlanner } from './PlannerContext';
import { HeroSlotBox, PetBuffControl, PlayerName, RatioEditor } from './widgets';
import PlayerSearch from './PlayerSearch';
import { RatioBar, TEAM } from './bits';
import { EXTRA_JOINERS, NAMED_JOINERS, OTHER_HEROES, blankMarch, leadersOf, shortfalls } from './model';
import type { Leader, PlanGroup, PlayerTarget, Side } from './model';

function DropRow({ id, target, children, className = '', testid }: { id: string; target: PlayerTarget; children: React.ReactNode; className?: string; testid?: string }) {
  const { readOnly } = usePlanner();
  const { setNodeRef, isOver } = useDroppable({ id, data: { type: 'playerTarget', accepts: ['player'], target }, disabled: readOnly });
  return (
    <div ref={setNodeRef} className={`${className} ${isOver ? 'ring-2 ring-success bg-success/10 rounded-lg' : ''}`} data-testid={testid}>
      {children}
    </div>
  );
}

function SectionTitle({ icon: Icon, children, extra }: { icon: React.ComponentType<{ className?: string }>; children: React.ReactNode; extra?: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 mb-2">
      <Icon className="w-4 h-4 text-accent shrink-0" aria-hidden="true" />
      <h5 className="text-xs font-bold uppercase tracking-wide text-theme-dim">{children}</h5>
      {extra && <div className="ms-auto">{extra}</div>}
    </div>
  );
}

export default function LeaderCard({ leader, group, number }: { leader: Leader; group: PlanGroup; number: number }) {
  const { t } = useTranslation();
  const ctx = usePlanner();
  const { readOnly, update } = ctx;
  const [collapsed, setCollapsed] = useState(false);
  const [disguiseOpen, setDisguiseOpen] = useState(false);
  const [menu, setMenu] = useState(false);
  const [overrideOpen, setOverrideOpen] = useState<Record<number, boolean>>({});
  const menuRef = useRef<HTMLDivElement>(null);
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({
    id: leader.id,
    data: { type: 'leader', accepts: ['leader'], leaderId: leader.id, groupId: leader.group_id },
    disabled: readOnly,
  });

  useEffect(() => {
    if (!menu) return;
    const close = (e: PointerEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenu(false);
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [menu]);

  const L = (fn: (l: Leader) => void) =>
    update((d) => {
      const l = d.leaders.find((x) => x.id === leader.id);
      if (l) fn(l);
    });

  const label = ctx.leaderLabel(leader);
  const others = ctx.doc.groups.filter((g) => g.kind !== 'extra' && g.id !== leader.group_id);
  const siblings = leadersOf(ctx.doc, leader.group_id);
  const pos = siblings.findIndex((x) => x.id === leader.id);
  const hasDisguise = !!(leader.disguise.alias || leader.disguise.pfp_hero);
  const showDisguise = hasDisguise || disguiseOpen;
  const sides: Side[] = leader.split ? ['rally', 'garrison'] : ['rally'];
  const team = TEAM[group.kind];
  const sideName = (s: Side) => t(`svs:plan.side.${s}`);

  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.35 : 1 };

  return (
    <article
      ref={setNodeRef}
      style={style}
      className={`relative bg-dark-card border border-theme-border border-s-4 ${team.border} rounded-xl shadow-sm`}
      data-testid="leader-card"
      data-leader-id={leader.id}
      data-group={group.kind}
      data-name={leader.player ? ctx.playerName(leader.player) : ''}
      data-alias={leader.disguise.alias ?? ''}
      aria-label={t('svs:plan.leaderAria', { n: number, name: label })}
    >
      {/* header */}
      <header className="flex items-center gap-2 px-3 pt-3">
        {!readOnly && (
          <button
            ref={setActivatorNodeRef}
            type="button"
            {...attributes}
            {...listeners}
            aria-label={t('svs:plan.dragLeader', { name: label })}
            data-testid="leader-drag"
            className="shrink-0 w-8 h-9 -ms-1 flex items-center justify-center rounded-md text-theme-dim hover:text-accent hover:bg-dark-card-hover cursor-grab active:cursor-grabbing touch-none"
          >
            <GripVertical className="w-5 h-5" aria-hidden="true" />
          </button>
        )}
        <span className={`shrink-0 min-w-[2rem] h-8 px-1.5 rounded-lg ${team.bar} text-dark-bg font-bold text-sm flex items-center justify-center`} data-testid="leader-number">
          {number}
        </span>
        <div className="min-w-0 flex-1">
          {leader.player ? (
            <div className="flex items-center gap-1.5 min-w-0">
              <PlayerName player={leader.player} testid="leader-name" />
              {!readOnly && (
                <button
                  type="button"
                  onClick={() => L((l) => (l.player = null))}
                  aria-label={t('svs:plan.removePlayer', { name: ctx.playerName(leader.player) })}
                  data-testid="leader-player-clear"
                  className="shrink-0 w-6 h-6 rounded-full text-theme-dim hover:text-danger flex items-center justify-center"
                >
                  <X className="w-4 h-4" aria-hidden="true" />
                </button>
              )}
            </div>
          ) : (
            <DropRow id={`lp-${leader.id}`} target={{ kind: 'leader', leaderId: leader.id }}>
              <PlayerSearch
                target={{ kind: 'leader', leaderId: leader.id }}
                placeholder={t('svs:plan.pickLeader')}
                testid="leader-search"
                autoFocus={!leader.player && !hasDisguise && leader.rally.heroes.every((h) => !h)}
              />
            </DropRow>
          )}
        </div>
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          aria-expanded={!collapsed}
          aria-label={collapsed ? t('svs:plan.expand') : t('svs:plan.collapse')}
          data-testid="leader-collapse"
          className="shrink-0 w-8 h-8 rounded-md text-theme-dim hover:text-accent hover:bg-dark-card-hover flex items-center justify-center"
        >
          {collapsed ? <ChevronDown className="w-5 h-5" aria-hidden="true" /> : <ChevronUp className="w-5 h-5" aria-hidden="true" />}
        </button>
        {!readOnly && (
          <div className="relative shrink-0" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenu((m) => !m)}
              aria-haspopup="menu"
              aria-expanded={menu}
              aria-label={t('svs:plan.leaderMenu', { name: label })}
              data-testid="leader-menu"
              className="w-8 h-8 rounded-md text-theme-dim hover:text-accent hover:bg-dark-card-hover flex items-center justify-center"
            >
              <MoreVertical className="w-5 h-5" aria-hidden="true" />
            </button>
            {menu && (
              <div role="menu" className="absolute z-40 end-0 top-full mt-1 w-56 bg-dark-bg border border-theme-border rounded-lg shadow-2xl py-1" data-testid="leader-menu-items">
                {others.map((g) => (
                  <button
                    key={g.id}
                    role="menuitem"
                    type="button"
                    onClick={() => {
                      setMenu(false);
                      ctx.moveLeader(leader.id, g.id, null);
                    }}
                    data-testid={`move-to-${g.kind}`}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-theme-text hover:bg-dark-card-hover text-start"
                  >
                    <ArrowRightLeft className="w-4 h-4" aria-hidden="true" />
                    {t('svs:plan.moveTo', { group: ctx.groupLabel(g) })}
                  </button>
                ))}
                {pos > 0 && (
                  <button
                    role="menuitem"
                    type="button"
                    onClick={() => {
                      setMenu(false);
                      ctx.moveLeader(leader.id, leader.group_id, siblings[pos - 1].id);
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-theme-text hover:bg-dark-card-hover text-start"
                  >
                    <ArrowUp className="w-4 h-4" aria-hidden="true" />
                    {t('svs:plan.moveUp')}
                  </button>
                )}
                {pos < siblings.length - 1 && (
                  <button
                    role="menuitem"
                    type="button"
                    onClick={() => {
                      setMenu(false);
                      ctx.moveLeader(leader.id, leader.group_id, siblings[pos + 2]?.id ?? null);
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-theme-text hover:bg-dark-card-hover text-start"
                  >
                    <ArrowDown className="w-4 h-4" aria-hidden="true" />
                    {t('svs:plan.moveDown')}
                  </button>
                )}
                <button
                  role="menuitem"
                  type="button"
                  onClick={() => {
                    setMenu(false);
                    if (window.confirm(t('svs:plan.confirmDeleteLeader', { name: label }))) update((d) => void (d.leaders = d.leaders.filter((x) => x.id !== leader.id)));
                  }}
                  data-testid="leader-delete"
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-danger hover:bg-danger/10 text-start"
                >
                  <Trash2 className="w-4 h-4" aria-hidden="true" />
                  {t('svs:plan.deleteLeader')}
                </button>
              </div>
            )}
          </div>
        )}
      </header>

      {collapsed ? (
        <div className="px-3 pb-3 pt-2 flex items-center gap-3" data-testid="leader-summary">
          {leader.disguise.alias && <span className="text-sm font-semibold text-accent truncate">{leader.disguise.alias}</span>}
          <div className="flex gap-1">
            {leader.rally.heroes.map((h, i) => {
              const hero = h ? ctx.heroes.get(h) : undefined;
              return hero ? (
                <img key={i} src={hero.image} alt={hero.name} title={hero.name} className="w-8 h-8 rounded-md object-cover border border-theme-border" />
              ) : (
                <span key={i} className="w-8 h-8 rounded-md border border-dashed border-theme-border/60" aria-hidden="true" />
              );
            })}
          </div>
          <div className="flex-1 min-w-0">
            <RatioBar ratio={leader.rally.ratio} compact />
          </div>
          <span className="text-xs text-theme-dim whitespace-nowrap inline-flex items-center gap-1">
            <Users className="w-3.5 h-3.5" aria-hidden="true" />
            {leader.named_joiners.filter((j) => j.player).length + leader.extra_joiners.length}
          </span>
        </div>
      ) : (
        <div className="px-3 pb-3 pt-2 space-y-4">
          {/* Disguise: at the top, collapsed while empty */}
          {showDisguise ? (
            <section className="rounded-lg border border-accent/30 bg-accent/5 p-2.5" data-testid="disguise">
              <SectionTitle
                icon={Drama}
                extra={
                  !hasDisguise && (
                    <button type="button" onClick={() => setDisguiseOpen(false)} className="text-xs text-theme-dim hover:text-accent" aria-label={t('common:close')}>
                      <X className="w-4 h-4" aria-hidden="true" />
                    </button>
                  )
                }
              >
                {t('svs:plan.disguise')}
              </SectionTitle>
              <div className="flex items-start gap-3">
                <HeroSlotBox slot={{ kind: 'pfp', leaderId: leader.id }} size="md" label={t('svs:plan.pfp')} testid="slot-pfp" />
                <div className="flex-1 min-w-0">
                  <label className="block text-xs text-theme-dim mb-1" htmlFor={`alias-${leader.id}`}>
                    {t('svs:plan.alias')}
                  </label>
                  <input
                    id={`alias-${leader.id}`}
                    value={leader.disguise.alias ?? ''}
                    maxLength={30}
                    disabled={readOnly}
                    placeholder={t('svs:plan.aliasPlaceholder')}
                    onChange={(e) => L((l) => (l.disguise.alias = e.target.value || null))}
                    data-testid="alias-input"
                    className="w-full min-h-[36px] px-2 text-sm font-semibold bg-dark-input border border-theme-border rounded-md text-theme-text"
                  />
                  <p className="mt-1 text-[11px] text-theme-dim leading-snug">{t('svs:plan.disguiseHint')}</p>
                </div>
              </div>
            </section>
          ) : (
            !readOnly && (
              <button
                type="button"
                onClick={() => setDisguiseOpen(true)}
                data-testid="disguise-open"
                className="inline-flex items-center gap-1.5 text-xs font-medium text-theme-dim hover:text-accent"
              >
                <Drama className="w-4 h-4" aria-hidden="true" />
                {t('svs:plan.addDisguise')}
              </button>
            )
          )}

          {/* Marches */}
          <section>
            <SectionTitle
              icon={Swords}
              extra={
            <label className="flex items-center gap-2 text-xs text-theme-text cursor-pointer w-fit">
              <input
                type="checkbox"
                checked={leader.split}
                disabled={readOnly}
                onChange={(e) =>
                  L((l) => {
                    l.split = e.target.checked;
                    if (l.split && !l.garrison) l.garrison = blankMarch();
                  })
                }
                data-testid="split-toggle"
                className="w-4 h-4 accent-accent"
              />
              {t('svs:plan.split')}
            </label>
              }
            >
              {t('svs:plan.heroesAndRatio')}
            </SectionTitle>
            <div className={leader.split ? 'space-y-2' : ''}>
              {sides.map((side) => {
                const march = side === 'rally' ? leader.rally : leader.garrison ?? blankMarch();
                return (
                  <div key={side} className={leader.split ? 'rounded-lg border border-theme-border/60 p-2' : ''} data-testid={`march-${side}`}>
                    {leader.split && <h5 className={`text-xs font-bold uppercase tracking-wide mb-1.5 ${team.text}`}>{sideName(side)}</h5>}
                    <div className="flex gap-2 mb-2">
                      {[0, 1, 2].map((i) => (
                        <HeroSlotBox
                          key={i}
                          slot={{ kind: 'march', leaderId: leader.id, side, index: i }}
                          label={t('svs:plan.heroN', { n: i + 1, side: sideName(side) })}
                          testid={`slot-march-${side}-${i}`}
                        />
                      ))}
                    </div>
                    <RatioEditor
                      value={march.ratio}
                      label={t('svs:plan.ratioOf', { side: sideName(side) })}
                      testid={`ratio-${side}`}
                      onChange={(r) =>
                        L((l) => {
                          if (side === 'rally') l.rally.ratio = r;
                          else {
                            l.garrison = l.garrison ?? blankMarch();
                            l.garrison.ratio = r;
                          }
                        })
                      }
                    />
                  </div>
                );
              })}
            </div>
          </section>

          {/* Pet buffs */}
          <section>
            <SectionTitle icon={PawPrint}>{t('svs:plan.petBuffs')}</SectionTitle>
            <PetBuffControl value={leader.pet_buff} onChange={(p) => L((l) => (l.pet_buff = p))} testid="pet-buff" />
          </section>

          {/* Named joiners */}
          <section data-testid="named-joiners">
            <SectionTitle icon={Users}>{t('svs:plan.namedJoiners')}</SectionTitle>
            <p className="text-[11px] text-theme-dim -mt-1 mb-1">{t('svs:plan.namedJoinersHint')}</p>
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wide text-theme-dim mb-1" aria-hidden="true">
              <span className="flex-1" />
              {sides.map((sd) => (
                <span key={sd} className="w-12 flex justify-center whitespace-nowrap">
                  {leader.split ? sideName(sd) : t('svs:plan.leadHeroShort')}
                </span>
              ))}
              <span className="w-8" />
            </div>
            <ol className="space-y-2">
              {leader.named_joiners.slice(0, NAMED_JOINERS).map((j, idx) => {
                const s = j.player?.fid ? ctx.signups.get(j.player.fid) : undefined;
                const short = j.player ? shortfalls(s?.troops ?? null, group.min_requirements) : [];
                const warn = short.length
                  ? short
                      .map((x) => t('svs:plan.shortfall', { troop: t(`tyrant:admin.troopName.${x.troop}`), have: x.have, need: x.need }))
                      .join('; ')
                  : null;
                const target: PlayerTarget = { kind: 'joiner', leaderId: leader.id, index: idx };
                const open = overrideOpen[idx] ?? false;
                const overridden = sides.some((sd) => j[sd].ratio_override);
                return (
                  <li key={idx} data-testid={`joiner-${idx}`} data-name={j.player ? ctx.playerName(j.player) : ''}>
                    <DropRow id={`jr-${leader.id}-${idx}`} target={target} className="flex items-center gap-2 p-1 -m-1">
                      <span className="shrink-0 w-5 text-center text-xs font-bold text-theme-dim">{idx + 1}</span>
                      <div className="min-w-0 flex-1">
                        {j.player ? (
                          <div className="flex items-center gap-1 min-w-0">
                            <PlayerName player={j.player} warn={warn} testid="joiner-name" />
                            {!readOnly && (
                              <button
                                type="button"
                                onClick={() => L((l) => (l.named_joiners[idx].player = null))}
                                aria-label={t('svs:plan.removePlayer', { name: ctx.playerName(j.player) })}
                                data-testid="joiner-clear"
                                className="shrink-0 w-6 h-6 rounded-full text-theme-dim hover:text-danger flex items-center justify-center"
                              >
                                <X className="w-4 h-4" aria-hidden="true" />
                              </button>
                            )}
                          </div>
                        ) : (
                          <PlayerSearch target={target} placeholder={t('svs:plan.pickJoiner', { n: idx + 1 })} testid="joiner-search" />
                        )}
                      </div>
                      {sides.map((sd) => (
                        <HeroSlotBox
                          key={sd}
                          slot={{ kind: 'joiner', leaderId: leader.id, side: sd, index: idx }}
                          size="sm"
                          label={t('svs:plan.leadHero', { side: sideName(sd), n: idx + 1 })}
                          testid={`slot-joiner-${sd}-${idx}`}
                        />
                      ))}
                      <button
                        type="button"
                        onClick={() => setOverrideOpen((o) => ({ ...o, [idx]: !open }))}
                        aria-expanded={open}
                        aria-label={t('svs:plan.ratioOverride', { n: idx + 1 })}
                        title={t('svs:plan.ratioOverride', { n: idx + 1 })}
                        data-testid={`joiner-ratio-toggle-${idx}`}
                        className={`shrink-0 w-8 h-8 rounded-md flex items-center justify-center hover:bg-dark-card-hover ${overridden ? 'text-accent' : 'text-theme-dim'}`}
                      >
                        <SlidersHorizontal className="w-4 h-4" aria-hidden="true" />
                      </button>
                    </DropRow>
                    {open && (
                      <div className="mt-2 ms-7 p-2 rounded-lg border border-theme-border/60 space-y-2" data-testid={`joiner-ratio-${idx}`}>
                        <p className="text-[11px] text-theme-dim">{t('svs:plan.overrideHint')}</p>
                        {sides.map((sd) => (
                          <div key={sd}>
                            {leader.split && <div className="text-[11px] font-semibold text-accent mb-1">{sideName(sd)}</div>}
                            <RatioEditor
                              value={j[sd].ratio_override}
                              label={t('svs:plan.overrideOf', { side: sideName(sd), n: idx + 1 })}
                              testid={`joiner-${idx}-ratio-${sd}`}
                              onChange={(r) => L((l) => (l.named_joiners[idx][sd].ratio_override = r))}
                            />
                          </div>
                        ))}
                      </div>
                    )}
                  </li>
                );
              })}
            </ol>
          </section>

          {/* Everyone else */}
          <section data-testid="other-heroes">
            <SectionTitle icon={Users}>{t('svs:plan.everyoneElse')}</SectionTitle>
            <div className="space-y-2">
              {sides.map((sd) => (
                <div key={sd} className="flex items-center gap-2">
                  {leader.split && <span className="w-16 shrink-0 text-[11px] font-semibold text-accent">{sideName(sd)}</span>}
                  <div className="flex gap-1.5">
                    {Array.from({ length: OTHER_HEROES }, (_, i) => i)
                      .filter((i) => i <= leader.other_joiner_heroes[sd].length)
                      .map((i) => (
                        <HeroSlotBox
                          key={i}
                          slot={{ kind: 'other', leaderId: leader.id, side: sd, index: i }}
                          size="sm"
                          label={t('svs:plan.otherHeroN', { n: i + 1, side: sideName(sd) })}
                          testid={`slot-other-${sd}-${i}`}
                        />
                      ))}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Extra joiners */}
          <section data-testid="extra-joiners">
            <SectionTitle icon={Users} extra={<span className="text-xs text-theme-dim" data-testid="extra-count">{leader.extra_joiners.length}/{EXTRA_JOINERS}</span>}>
              {t('svs:plan.extraJoiners')}
            </SectionTitle>
            <DropRow id={`ex-${leader.id}`} target={{ kind: 'extra', leaderId: leader.id }} className="space-y-2">
              {leader.extra_joiners.length > 0 && (
                <ul className="flex flex-wrap gap-1.5">
                  {leader.extra_joiners.map((e, i) => (
                    <li key={i} className="inline-flex items-center gap-1 ps-2 pe-1 py-0.5 rounded-full bg-dark-input border border-theme-border text-xs" data-testid="extra-chip">
                      <PlayerName player={e.player} />
                      {!readOnly && (
                        <button
                          type="button"
                          onClick={() => L((l) => void l.extra_joiners.splice(i, 1))}
                          aria-label={t('svs:plan.removePlayer', { name: ctx.playerName(e.player) })}
                          className="w-5 h-5 rounded-full text-theme-dim hover:text-danger flex items-center justify-center"
                        >
                          <X className="w-3.5 h-3.5" aria-hidden="true" />
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              {leader.extra_joiners.length < EXTRA_JOINERS && (
                <PlayerSearch target={{ kind: 'extra', leaderId: leader.id }} placeholder={t('svs:plan.addExtra')} testid="extra-search" />
              )}
            </DropRow>
          </section>
        </div>
      )}
    </article>
  );
}
