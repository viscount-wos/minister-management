import type React from 'react';
import { forwardRef, type HTMLAttributes, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Shield } from 'lucide-react';
import { CrossbowIcon, SpearIcon } from './TroopIcons';
import type { Hero, HeroTroop } from './api';

// Reusable hero card for the SVS planner (drag-and-drop picker comes later): a big picture, the name, a troop icon
// and a small "Gen N" line (owner: generation, not gender). Readable in every language incl. Arabic (RTL): the
// name is an isolate, numbers stay LTR. forwardRef + rest props so a drag-and-drop wrapper (dnd-kit's
// setNodeRef/listeners/attributes) can wrap it without changes; `selected` / `dimmed` / `badge` / `children` cover
// picker states. Hero art (c) Century Games: pages that show heroes render <HeroCredit /> once.

// Infantry = shield, Lancer = spear, Marksman = crossbow (owner request; lucide has no spear/crossbow).
const TROOP_ICON: Record<HeroTroop, React.ElementType> = { infantry: Shield, lancer: SpearIcon, marksman: CrossbowIcon };

export function TroopIcon({ troop, className = 'w-4 h-4' }: { troop: HeroTroop; className?: string }) {
  const { t } = useTranslation();
  const Icon = TROOP_ICON[troop];
  return <Icon className={className} aria-label={t(`tyrant:admin.troopName.${troop}`)} role="img" />;
}

export interface HeroCardProps extends Omit<HTMLAttributes<HTMLDivElement>, 'children'> {
  hero: Hero;
  size?: 'sm' | 'md' | 'lg';
  selected?: boolean;
  dimmed?: boolean;
  /** Small overlay in the top corner (e.g. a remove button or a count). */
  badge?: ReactNode;
  children?: ReactNode;
}

const SIZES = {
  sm: { box: 'w-24', name: 'text-xs' },
  md: { box: 'w-32', name: 'text-sm' },
  lg: { box: 'w-40', name: 'text-base' },
};

const HeroCard = forwardRef<HTMLDivElement, HeroCardProps>(function HeroCard(
  { hero, size = 'md', selected, dimmed, badge, children, className = '', ...rest },
  ref,
) {
  const { t } = useTranslation();
  const s = SIZES[size];
  const rarityRing = hero.rarity === 'mythic' ? 'border-warning/70' : hero.rarity === 'epic' ? 'border-accent/60' : 'border-theme-border';
  return (
    <div
      ref={ref}
      data-testid={`hero-${hero.slug}`}
      data-generation={hero.generation ?? ''}
      data-troop={hero.troop}
      className={`relative ${s.box} shrink-0 rounded-xl border-2 bg-dark-bg overflow-hidden transition-colors ${
        selected ? 'border-accent ring-2 ring-accent/50' : rarityRing
      } ${dimmed ? 'opacity-40' : ''} ${className}`}
      {...rest}
    >
      <img src={hero.image} alt="" loading="lazy" draggable={false} className="block w-full aspect-square object-cover bg-dark-input" />
      {badge && <div className="absolute top-1 end-1">{badge}</div>}
      <div className="px-2 py-1.5">
        <div className={`flex items-center gap-1 font-semibold text-theme-text ${s.name}`}>
          <span className="shrink-0 text-accent">
            <TroopIcon troop={hero.troop} className="w-4 h-4" />
          </span>
          <bdi className="min-w-0 truncate" data-testid="hero-name">
            {hero.name}
          </bdi>
        </div>
        <div className="text-[11px] text-theme-dim leading-4" data-testid="hero-gen">
          {hero.generation != null ? t('common:heroes.gen', { n: hero.generation }) : t(`common:heroes.rarity.${hero.rarity}`)}
        </div>
        {children}
      </div>
    </div>
  );
});

export default HeroCard;

/** "Hero art © Century Games": one small line on every page that shows heroes. */
export function HeroCredit({ className = '' }: { className?: string }) {
  const { t } = useTranslation();
  return (
    <p className={`text-xs text-theme-dim ${className}`} data-testid="hero-credit">
      {t('common:heroes.credit')}
    </p>
  );
}
