// The planner's sticky side panel: the HERO PALETTE (drag a hero into any slot, or click a slot then a hero) and the
// list of sign-ups not placed yet (drag one onto a joiner row, an extra-joiners box or "new leader").
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDraggable } from '@dnd-kit/core';
import { Headphones, Search, X } from 'lucide-react';
import HeroCard, { HeroCredit, TroopIcon } from '../../../shared/heroes/HeroCard';
import { HERO_TROOPS, type Hero, type HeroTroop } from '../../../shared/heroes/api';
import { usePlanner, type SignupInfo } from './PlannerContext';
import { TroopLine, hoursText } from './widgets';
import type { HeroSlot } from './model';

/** Generation newest first; rare/epic heroes (no generation) after, epic before rare (owner: "listed after"). */
export function paletteOrder(a: Hero, b: Hero): number {
  const rank = (h: Hero) => (h.generation != null ? 0 : h.rarity === 'epic' ? 1 : 2);
  return rank(a) - rank(b) || (b.generation ?? 0) - (a.generation ?? 0) || a.name.localeCompare(b.name);
}

function PaletteHero({ hero }: { hero: Hero }) {
  const { t } = useTranslation();
  const ctx = usePlanner();
  const { setNodeRef, listeners, attributes, isDragging } = useDraggable({
    id: `hero-${hero.slug}`,
    data: { type: 'hero', slug: hero.slug },
    disabled: ctx.readOnly,
  });
  // Pointer/touch drag only: Enter/Space on a hero is click-to-place (keyboard users never need to drag).
  const { onKeyDown: _ignored, ...pointer } = (listeners ?? {}) as Record<string, (e: unknown) => void>;
  void _ignored;
  const armed = ctx.armedHero === hero.slug;
  const activate = () => {
    if (ctx.readOnly) return;
    if (ctx.armedSlot) ctx.placeHero(ctx.armedSlot, hero.slug);
    else ctx.setArmedHero(armed ? null : hero.slug);
  };
  return (
    <HeroCard
      ref={setNodeRef}
      hero={hero}
      size="sm"
      selected={armed}
      dimmed={isDragging}
      {...attributes}
      {...pointer}
      role="button"
      tabIndex={0}
      aria-pressed={armed}
      aria-label={t('svs:plan.paletteHero', { name: hero.name })}
      onClick={activate}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          activate();
        }
      }}
      data-palette-hero={hero.slug}
      className="cursor-grab active:cursor-grabbing touch-none hover:border-accent focus:outline-none focus:ring-2 focus:ring-accent !w-[5.75rem]"
    />
  );
}

function slotText(t: (k: string, o?: Record<string, unknown>) => string, s: HeroSlot, leaderName: string): string {
  const side = 'side' in s ? t(`svs:plan.side.${s.side}`) : '';
  switch (s.kind) {
    case 'pfp':
      return `${t('svs:plan.pfp')} · ${leaderName}`;
    case 'march':
      return `${t('svs:plan.heroN', { n: s.index + 1, side })} · ${leaderName}`;
    case 'joiner':
      return `${t('svs:plan.leadHero', { side, n: s.index + 1 })} · ${leaderName}`;
    case 'other':
      return `${t('svs:plan.otherHeroN', { n: s.index + 1, side })} · ${leaderName}`;
  }
}

function HeroPalette() {
  const { t } = useTranslation();
  const ctx = usePlanner();
  const [troop, setTroop] = useState<HeroTroop | ''>('');
  const [q, setQ] = useState('');
  const list = useMemo(
    () =>
      [...ctx.heroes.values()]
        .filter((h) => h.generation == null || h.generation <= ctx.stateGen)
        .filter((h) => !troop || h.troop === troop)
        .filter((h) => !q.trim() || h.name.toLowerCase().includes(q.trim().toLowerCase()))
        .sort(paletteOrder),
    [ctx.heroes, ctx.stateGen, troop, q],
  );
  const armedLeader = ctx.armedSlot ? ctx.doc.leaders.find((l) => l.id === ctx.armedSlot!.leaderId) : undefined;

  return (
    <div data-testid="hero-palette">
      {ctx.armedSlot && armedLeader && (
        <div className="mb-3 p-2 rounded-lg bg-accent/15 border border-accent/50 text-sm text-accent flex items-start gap-2" role="status" data-testid="armed-slot-banner">
          <span className="flex-1">{t('svs:plan.pickFor', { slot: slotText(t, ctx.armedSlot, ctx.leaderLabel(armedLeader)) })}</span>
          <button type="button" onClick={() => ctx.setArmedSlot(null)} aria-label={t('common:cancel')} className="shrink-0">
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>
      )}
      {ctx.armedHero && (
        <div className="mb-3 p-2 rounded-lg bg-accent/15 border border-accent/50 text-sm text-accent flex items-start gap-2" role="status" data-testid="armed-hero-banner">
          <span className="flex-1">{t('svs:plan.nowClickSlot', { name: ctx.heroes.get(ctx.armedHero)?.name ?? '' })}</span>
          <button type="button" onClick={() => ctx.setArmedHero(null)} aria-label={t('common:cancel')} className="shrink-0">
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>
      )}
      <div className="flex flex-wrap gap-1 mb-2" role="group" aria-label={t('tyrant:admin.filter.troop')}>
        {(['', ...HERO_TROOPS] as (HeroTroop | '')[]).map((k) => (
          <button
            key={k || 'all'}
            type="button"
            onClick={() => setTroop(k)}
            aria-pressed={troop === k}
            data-testid={`palette-troop-${k || 'all'}`}
            className={`inline-flex items-center gap-1 min-h-[34px] px-2.5 rounded-full border text-xs font-medium ${
              troop === k ? 'border-accent bg-accent/20 text-accent' : 'border-theme-border text-theme-text hover:bg-dark-card-hover'
            }`}
          >
            {k && <TroopIcon troop={k} className="w-3.5 h-3.5" />}
            {t(`tyrant:admin.troopName.${k || 'all'}`)}
          </button>
        ))}
      </div>
      <div className="relative mb-3">
        <Search className="absolute start-2 top-1/2 -translate-y-1/2 w-4 h-4 text-theme-dim pointer-events-none" aria-hidden="true" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t('svs:plan.searchHeroes')}
          aria-label={t('svs:plan.searchHeroes')}
          data-testid="palette-search"
          className="w-full min-h-[36px] ps-8 pe-2 text-sm bg-dark-input border border-theme-border rounded-lg text-theme-text"
        />
      </div>
      <p className="text-[11px] text-theme-dim mb-2">{t('svs:plan.paletteHint', { gen: ctx.stateGen })}</p>
      <div className="flex flex-wrap gap-2 justify-start" data-testid="palette-grid">
        {list.map((h) => (
          <PaletteHero key={h.slug} hero={h} />
        ))}
        {list.length === 0 && <p className="text-sm text-theme-dim">{t('svs:plan.noHeroes')}</p>}
      </div>
      <HeroCredit className="mt-3" />
    </div>
  );
}

function UnplacedItem({ s }: { s: SignupInfo }) {
  const { t } = useTranslation();
  const { readOnly, battleHours } = usePlanner();
  const { setNodeRef, listeners, attributes, isDragging } = useDraggable({
    id: `player-${s.fid}`,
    data: { type: 'player', ref: { fid: s.fid } },
    disabled: readOnly,
  });
  return (
    <li
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      data-testid={`unplaced-${s.fid}`}
      className={`p-2 rounded-lg border border-theme-border bg-dark-bg cursor-grab active:cursor-grabbing touch-none hover:border-accent ${isDragging ? 'opacity-40' : ''}`}
    >
      <div className="flex items-center gap-1.5 min-w-0 text-sm">
        <span className="min-w-0 truncate font-semibold text-theme-text">
          {s.alliance && <span className="text-accent font-normal">[{s.alliance}] </span>}
          <bdi>{s.name}</bdi>
        </span>
        {s.strength != null && (
          <span className="shrink-0 px-1.5 rounded text-[10px] font-semibold bg-accent/20 text-accent" title={t('svs:plan.strength')}>
            {s.strength}
          </span>
        )}
        {s.vc && <Headphones className="w-3.5 h-3.5 shrink-0 text-success" aria-label={t('svs:plan.vcYes')} role="img" />}
      </div>
      <div className="text-[11px] text-theme-dim mt-0.5">
        <TroopLine troops={s.troops} />
      </div>
      <div className="text-[11px] text-theme-dim">
        {t('svs:plan.hoursLabel')} <bdi dir="ltr">{hoursText(s.hours, battleHours)}</bdi>
      </div>
    </li>
  );
}

function Unplaced() {
  const { t } = useTranslation();
  const ctx = usePlanner();
  const [vcOnly, setVcOnly] = useState(false);
  const [hour, setHour] = useState('');
  const [q, setQ] = useState('');
  const left = useMemo(() => [...ctx.signups.values()].filter((s) => !ctx.placed.has(`fid:${s.fid}`)), [ctx.signups, ctx.placed]);
  // Strongest first (SVS sign-up asks no role: the planner picks leaders by troops, hours and voice chat).
  const shown = left
    .filter((s) => !vcOnly || s.vc)
    .filter((s) => !hour || s.hours.includes(hour))
    .filter((s) => !q.trim() || s.name.toLowerCase().includes(q.trim().toLowerCase()) || s.fid.startsWith(q.trim()))
    .sort((a, b) => (b.strength ?? -1) - (a.strength ?? -1) || a.name.localeCompare(b.name));
  return (
    <div data-testid="unplaced">
      <p className="text-sm text-theme-text mb-2" data-testid="unplaced-count">
        {t('svs:plan.unplacedCount', { n: left.length, total: ctx.signups.size })}
      </p>
      <div className="flex flex-wrap gap-1.5 mb-2">
        <button
          type="button"
          onClick={() => setVcOnly((v) => !v)}
          aria-pressed={vcOnly}
          data-testid="unplaced-vc"
          className={`inline-flex items-center gap-1 min-h-[34px] px-2.5 rounded-full border text-xs font-medium ${
            vcOnly ? 'border-accent bg-accent/20 text-accent' : 'border-theme-border text-theme-text hover:bg-dark-card-hover'
          }`}
        >
          <Headphones className="w-3.5 h-3.5" aria-hidden="true" />
          {t('svs:plan.vcOnly')}
        </button>
        <select
          value={hour}
          onChange={(e) => setHour(e.target.value)}
          aria-label={t('svs:admin.filter.hours')}
          data-testid="unplaced-hour"
          className="min-h-[34px] px-2 rounded-full border border-theme-border bg-dark-input text-xs text-theme-text"
        >
          <option value="">{t('svs:admin.filter.anyHour')}</option>
          {ctx.battleHours.map((h) => (
            <option key={h} value={h}>
              {h} UTC
            </option>
          ))}
        </select>
      </div>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={t('svs:plan.searchPlayers')}
        aria-label={t('svs:plan.searchPlayers')}
        data-testid="unplaced-search"
        className="w-full mb-2 min-h-[36px] px-2 text-sm bg-dark-input border border-theme-border rounded-lg text-theme-text"
      />
      <p className="text-[11px] text-theme-dim mb-2">{t('svs:plan.unplacedHint')}</p>
      <ul className="space-y-1.5">
        {shown.map((s) => (
          <UnplacedItem key={s.fid} s={s} />
        ))}
        {shown.length === 0 && <li className="text-sm text-theme-dim">{t('svs:plan.allPlaced')}</li>}
      </ul>
    </div>
  );
}

export default function Sidebar({ tab, setTab }: { tab: 'heroes' | 'players'; setTab: (t: 'heroes' | 'players') => void }) {
  const { t } = useTranslation();
  const ctx = usePlanner();
  const left = [...ctx.signups.values()].filter((s) => !ctx.placed.has(`fid:${s.fid}`)).length;
  return (
    <aside className="lg:sticky lg:top-2 lg:max-h-[calc(100vh-1rem)] flex flex-col bg-dark-card border border-theme-border rounded-xl" data-testid="planner-sidebar">
      <div className="flex border-b border-theme-border" role="tablist">
        {(['heroes', 'players'] as const).map((k) => (
          <button
            key={k}
            type="button"
            role="tab"
            aria-selected={tab === k}
            onClick={() => setTab(k)}
            data-testid={`sidebar-tab-${k}`}
            className={`flex-1 min-h-[44px] px-3 text-sm font-semibold border-b-2 ${tab === k ? 'border-accent text-accent' : 'border-transparent text-theme-dim hover:text-theme-text'}`}
          >
            {k === 'heroes' ? t('svs:plan.tabHeroes') : t('svs:plan.tabPlayers', { n: left })}
          </button>
        ))}
      </div>
      <div className="p-3 overflow-y-auto">{tab === 'heroes' ? <HeroPalette /> : <Unplaced />}</div>
    </aside>
  );
}
