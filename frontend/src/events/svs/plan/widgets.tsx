// Planner widgets: hero slots (drop + click-to-place), the ratio editor, the pet-buff control and player names with
// their sign-up info on hover.
import { useEffect, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDroppable } from '@dnd-kit/core';
import { AlertTriangle, Headphones, Plus, UserX, X } from 'lucide-react';
import { TroopIcon } from '../../../shared/heroes/HeroCard';
import { usePlanner, type SignupInfo } from './PlannerContext';
import { RatioBar, petBuffLabel } from './bits';
import { PET_BUFFS, RATIO_KEYS, RATIO_TROOP, TROOPS, getSlotHero, ratioTotal, sameSlot, slotId } from './model';
import type { HeroSlot, PetBuff, PlayerRef, Ratio, RatioKey } from './model';

// ------------------------------------------------------------------ hero slot

const SLOT_BOX = { lg: 'w-[5.25rem]', md: 'w-16', sm: 'w-12' };

/** A hero slot: drop a hero from the palette, or click it (it lights up) and then click a hero. x clears it. */
export function HeroSlotBox({ slot, size = 'lg', label, testid }: { slot: HeroSlot; size?: 'lg' | 'md' | 'sm'; label: string; testid: string }) {
  const { t } = useTranslation();
  const ctx = usePlanner();
  const slug = getSlotHero(ctx.doc, slot);
  const hero = slug ? ctx.heroes.get(slug) : undefined;
  const { setNodeRef, isOver } = useDroppable({
    id: slotId(slot),
    data: { type: 'heroSlot', accepts: ['hero'], slot },
    disabled: ctx.readOnly,
  });
  const armed = sameSlot(ctx.armedSlot, slot);
  const aboveGen = !!hero && hero.generation != null && hero.generation > ctx.stateGen;

  const onClick = () => {
    if (ctx.readOnly) return;
    if (ctx.armedHero) {
      ctx.placeHero(slot, ctx.armedHero);
      return;
    }
    ctx.setArmedSlot(armed ? null : slot);
    if (!armed) ctx.setSidebarTab('heroes');
  };

  return (
    <div ref={setNodeRef} className={`relative ${SLOT_BOX[size]} shrink-0`} data-testid={testid} data-hero={slug ?? ''} data-armed={armed || undefined}>
      <button
        type="button"
        onClick={onClick}
        disabled={ctx.readOnly}
        aria-pressed={armed}
        aria-label={hero ? t('svs:plan.slotFilled', { slot: label, hero: hero.name }) : t('svs:plan.slotEmpty', { slot: label })}
        title={hero ? `${label}: ${hero.name}` : label}
        className={`block w-full rounded-lg border-2 overflow-hidden transition-colors aspect-square ${
          armed
            ? 'border-accent ring-2 ring-accent/60 bg-accent/10'
            : isOver
              ? 'border-success ring-2 ring-success/50 bg-success/10'
              : hero
                ? aboveGen
                  ? 'border-warning'
                  : 'border-theme-border hover:border-accent'
                : 'border-dashed border-theme-border/70 bg-dark-input hover:border-accent hover:bg-accent/5'
        }`}
      >
        {hero ? (
          <img src={hero.image} alt="" draggable={false} className="block w-full h-full object-cover" />
        ) : (
          <span className="flex w-full h-full items-center justify-center text-theme-dim">
            <Plus className={size === 'sm' ? 'w-4 h-4' : 'w-6 h-6'} aria-hidden="true" />
          </span>
        )}
      </button>
      {hero && !ctx.readOnly && (
        <button
          type="button"
          onClick={() => ctx.placeHero(slot, null)}
          aria-label={t('svs:plan.clearSlot', { slot: label })}
          data-testid={`${testid}-clear`}
          className="absolute -top-1.5 -end-1.5 w-6 h-6 rounded-full bg-dark-card border border-theme-border text-theme-dim hover:text-danger hover:border-danger flex items-center justify-center shadow"
        >
          <X className="w-3.5 h-3.5" aria-hidden="true" />
        </button>
      )}
      {size !== 'sm' && (
        <div className="mt-0.5 text-center leading-tight">
          <bdi className={`block truncate ${size === 'lg' ? 'text-xs' : 'text-[11px]'} ${hero ? 'text-theme-text font-medium' : 'text-theme-dim'}`}>
            {hero ? hero.name : label}
          </bdi>
          {hero && size === 'lg' && (
            <span className={`flex items-center justify-center gap-0.5 text-[10px] ${aboveGen ? 'text-warning font-semibold' : 'text-theme-dim'}`}>
              <TroopIcon troop={hero.troop} className="w-3 h-3" />
              {hero.generation != null ? t('common:heroes.gen', { n: hero.generation }) : t(`common:heroes.rarity.${hero.rarity}`)}
            </span>
          )}
        </div>
      )}
      {size === 'sm' && hero && (
        <bdi className="block mt-0.5 text-[10px] leading-tight text-center truncate text-theme-text">{hero.name}</bdi>
      )}
      {aboveGen && (
        <span className="sr-only" data-testid={`${testid}-above-gen`}>
          {t('svs:plan.aboveGen', { gen: ctx.stateGen })}
        </span>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ ratio

type Draft = Record<RatioKey, string>;
const toDraft = (r: Ratio | null): Draft => ({ inf: r ? String(r.inf) : '', lan: r ? String(r.lan) : '', mks: r ? String(r.mks) : '' });

/** Three whole-number inputs that must total 100 (saved only when they do) + the stacked bar preview. */
export function RatioEditor({
  value,
  onChange,
  testid,
  label,
}: {
  value: Ratio | null;
  onChange: (r: Ratio | null) => void;
  testid: string;
  label: string;
}) {
  const { t } = useTranslation();
  const { readOnly } = usePlanner();
  const [draft, setDraft] = useState<Draft>(() => toDraft(value));
  const id = useId();
  const key = value ? `${value.inf}/${value.lan}/${value.mks}` : '';
  useEffect(() => {
    // An outside change (reload, other editor) resets the inputs.
    setDraft((d) => {
      const cur = toDraft(value);
      const same = RATIO_KEYS.every((k) => (Number(d[k]) || 0) === (Number(cur[k]) || 0));
      return same ? d : cur;
    });
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps

  const total = ratioTotal(draft);
  const empty = RATIO_KEYS.every((k) => draft[k] === '');
  const valid = total === 100 && RATIO_KEYS.every((k) => /^\d{1,3}$/.test(draft[k] || '0'));

  const set = (k: RatioKey, raw: string) => {
    const v = raw.replace(/[^\d]/g, '').slice(0, 3);
    const next = { ...draft, [k]: v };
    setDraft(next);
    const allEmpty = RATIO_KEYS.every((x) => next[x] === '');
    if (allEmpty) onChange(null);
    else if (ratioTotal(next) === 100) onChange({ inf: Number(next.inf) || 0, lan: Number(next.lan) || 0, mks: Number(next.mks) || 0 });
  };

  return (
    <fieldset className="min-w-0" data-testid={testid} data-valid={valid || empty}>
      <legend className="sr-only">{label}</legend>
      <div className="flex flex-wrap items-center gap-2">
        {RATIO_KEYS.map((k) => (
          <label key={k} htmlFor={`${id}-${k}`} className="inline-flex items-center gap-1 text-xs text-theme-dim">
            <TroopIcon troop={RATIO_TROOP[k]} className="w-4 h-4" />
            <span>{t(`tyrant:admin.troopShort.${RATIO_TROOP[k]}`)}</span>
            <input
              id={`${id}-${k}`}
              inputMode="numeric"
              value={draft[k]}
              disabled={readOnly}
              onChange={(e) => set(k, e.target.value)}
              onFocus={(e) => e.target.select()}
              data-testid={`${testid}-${k}`}
              aria-label={`${label}: ${t(`tyrant:admin.troopName.${RATIO_TROOP[k]}`)} %`}
              className="w-12 min-h-[36px] px-1.5 text-center text-sm font-semibold bg-dark-input border border-theme-border rounded-md text-theme-text focus:ring-2 focus:ring-accent focus:border-accent"
              dir="ltr"
            />
            <span aria-hidden="true">%</span>
          </label>
        ))}
        <span
          className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
            empty ? 'text-theme-dim' : valid ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger'
          }`}
          data-testid={`${testid}-total`}
          role={!empty && !valid ? 'alert' : undefined}
        >
          {empty ? t('svs:plan.ratioHint') : valid ? '= 100%' : t('svs:plan.ratioTotal', { n: total })}
        </span>
      </div>
      {valid && (
        <div className="mt-1.5">
          <RatioBar ratio={{ inf: Number(draft.inf) || 0, lan: Number(draft.lan) || 0, mks: Number(draft.mks) || 0 }} compact />
        </div>
      )}
    </fieldset>
  );
}

// ------------------------------------------------------------------ pet buffs

export function PetBuffControl({ value, onChange, testid }: { value: PetBuff | null; onChange: (p: PetBuff | null) => void; testid: string }) {
  const { t } = useTranslation();
  const { petTimes, readOnly } = usePlanner();
  return (
    <div role="group" aria-label={t('svs:plan.petBuffs')} className="flex flex-wrap gap-1.5" data-testid={testid} data-value={value ?? ''}>
      {PET_BUFFS.map((p) => (
        <button
          key={p}
          type="button"
          disabled={readOnly}
          aria-pressed={value === p}
          onClick={() => onChange(value === p ? null : p)}
          data-testid={`${testid}-${p}`}
          className={`min-h-[36px] px-2.5 py-1 rounded-lg border text-xs font-medium transition-colors ${
            value === p ? 'border-accent bg-accent/20 text-accent' : 'border-theme-border text-theme-text hover:bg-dark-card-hover'
          }`}
        >
          {petBuffLabel(t, p, petTimes[p])}
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ players

/** "Inf FC10 T11 · Lan FC9 T10 · Mks FC8 T11". */
export function TroopLine({ troops, className = '' }: { troops: SignupInfo['troops'] | null | undefined; className?: string }) {
  const { t } = useTranslation();
  if (!troops) return null;
  return (
    <span className={className}>
      {TROOPS.map((k, i) => (
        <span key={k} className="whitespace-nowrap">
          {i > 0 && <span aria-hidden="true"> · </span>}
          {t(`tyrant:admin.troopShort.${k}`)}{' '}
          <bdi dir="ltr" className="text-theme-text">
            {troops[k]?.furnace_level || '—'} {troops[k]?.tier ? `T${troops[k].tier}` : '—'}
          </bdi>
        </span>
      ))}
    </span>
  );
}

/** "11:00-13:00, 15:00" from hour starts. */
export function hoursText(hours: string[], all: string[]): string {
  if (!hours.length) return '—';
  const idx = hours.map((h) => all.indexOf(h)).filter((i) => i >= 0).sort((a, b) => a - b);
  const parts: string[] = [];
  let start = idx[0];
  let prev = idx[0];
  const end = (i: number) => {
    const [h, m] = all[i].split(':').map(Number);
    return `${String((h + 1) % 24).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  };
  for (const i of [...idx.slice(1), -99]) {
    if (i === prev + 1) {
      prev = i;
      continue;
    }
    parts.push(`${all[start]}-${end(prev)}`);
    start = i;
    prev = i;
  }
  return parts.join(', ');
}

export function SignupDetails({ s }: { s: SignupInfo }) {
  const { t } = useTranslation();
  const { battleHours } = usePlanner();
  return (
    <div className="space-y-1 text-xs text-theme-dim">
      <div>
        <TroopLine troops={s.troops} />
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5">
        {s.strength != null && (
          <span>
            {t('svs:plan.strength')} <span className="text-theme-text font-semibold">{s.strength}</span>
          </span>
        )}
        <span>
          {t('svs:plan.hoursLabel')}{' '}
          <bdi dir="ltr" className="text-theme-text">
            {hoursText(s.hours, battleHours)}
          </bdi>
        </span>
        <span className={s.vc ? 'text-success' : ''}>{s.vc ? t('svs:plan.vcYes') : s.vc === false ? t('svs:plan.vcNo') : ''}</span>
      </div>
    </div>
  );
}

/** A placed player's name; hover/focus shows the sign-up (troops, hours, role, VC). Quick-adds say "not signed up". */
export function PlayerName({ player, warn, testid }: { player: PlayerRef; warn?: string | null; testid?: string }) {
  const { t } = useTranslation();
  const ctx = usePlanner();
  const [open, setOpen] = useState(false);
  const s = player.fid ? ctx.signups.get(player.fid) : undefined;
  const person = player.fid ? ctx.people[player.fid] : undefined;
  const alliance = s?.alliance ?? person?.alliance ?? null;
  const notSignedUp = !s;
  return (
    <span
      className="relative inline-flex min-w-0 items-center gap-1.5"
      onPointerEnter={(e) => e.pointerType === 'mouse' && setOpen(true)}
      onPointerLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      data-testid={testid}
      data-name={ctx.playerName(player)}
    >
      <span tabIndex={0} className="min-w-0 truncate font-semibold text-theme-text focus:outline-none focus:ring-2 focus:ring-accent rounded">
        {alliance && <span className="text-accent font-normal">[{alliance}] </span>}
        <bdi>{ctx.playerName(player)}</bdi>
      </span>
      {s?.vc && <Headphones className="w-3.5 h-3.5 shrink-0 text-success" aria-label={t('svs:plan.vcYes')} role="img" />}
      {notSignedUp && (
        <span className="shrink-0 inline-flex items-center gap-0.5 px-1.5 rounded bg-warning/15 text-warning text-[10px] font-semibold" data-testid="not-signed-up">
          <UserX className="w-3 h-3" aria-hidden="true" />
          {t('svs:plan.notSignedUp')}
        </span>
      )}
      {warn && (
        <span className="shrink-0 inline-flex items-center gap-0.5 px-1.5 rounded bg-warning/15 text-warning text-[10px] font-semibold" title={warn} data-testid="below-minimum">
          <AlertTriangle className="w-3 h-3" aria-hidden="true" />
          {t('svs:plan.belowMin')}
          <span className="sr-only">: {warn}</span>
        </span>
      )}
      {open && (s || notSignedUp) && (
        <span
          role="tooltip"
          className="absolute z-40 top-full start-0 mt-1 w-72 p-3 bg-dark-bg border border-accent/40 rounded-lg shadow-xl pointer-events-none text-start"
          data-testid="player-hover"
        >
          <span className="block font-semibold text-accent truncate">
            <bdi>{ctx.playerName(player)}</bdi>
            {player.fid && <span className="ms-2 text-xs text-theme-dim font-normal">FID {player.fid}</span>}
          </span>
          {s ? <SignupDetails s={s} /> : <span className="block text-xs text-theme-dim mt-1">{t('svs:plan.notSignedUpHint')}</span>}
          {warn && <span className="block mt-1 text-xs text-warning">{warn}</span>}
        </span>
      )}
    </span>
  );
}
