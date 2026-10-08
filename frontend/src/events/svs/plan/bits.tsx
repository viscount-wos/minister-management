// Small pieces shared by the planner (admin) and the shared plan view (phone).
import { useTranslation } from 'react-i18next';
import { TroopIcon } from '../../../shared/heroes/HeroCard';
import type { GroupKind, PetBuff, Ratio, TroopKey, ViewHero } from './model';
import { RATIO_KEYS, RATIO_TROOP, TROOPS } from './model';

/** Full class names per group kind (Tailwind needs them spelled out). Theme tokens only (tailwind.config.js). */
export const TEAM: Record<GroupKind, { border: string; bg: string; text: string; bar: string; ring: string }> = {
  main: { border: 'border-team-main', bg: 'bg-team-main/10', text: 'text-team-main', bar: 'bg-team-main', ring: 'ring-team-main' },
  counter: { border: 'border-team-counter', bg: 'bg-team-counter/10', text: 'text-team-counter', bar: 'bg-team-counter', ring: 'ring-team-counter' },
  extra: { border: 'border-team-extra', bg: 'bg-team-extra/10', text: 'text-team-extra', bar: 'bg-team-extra', ring: 'ring-team-extra' },
};

const SEG: Record<(typeof RATIO_KEYS)[number], string> = { inf: 'bg-troop-inf', lan: 'bg-troop-lan', mks: 'bg-troop-mks' };
const SEG_TEXT: Record<(typeof RATIO_KEYS)[number], string> = { inf: 'text-troop-inf', lan: 'text-troop-lan', mks: 'text-troop-mks' };

/** Stacked infantry / lancer / marksman bar with the percentages written under it. */
export function RatioBar({ ratio, compact = false, labels = true, testid }: { ratio: Ratio | null; compact?: boolean; labels?: boolean; testid?: string }) {
  const { t } = useTranslation();
  if (!ratio) {
    return (
      <p className="text-xs text-theme-dim italic" data-testid={testid}>
        {t('svs:plan.ratioNotSet')}
      </p>
    );
  }
  return (
    <div data-testid={testid} data-ratio={`${ratio.inf}/${ratio.lan}/${ratio.mks}`}>
      <div className={`flex w-full overflow-hidden rounded-full bg-dark-input ${compact ? 'h-2' : 'h-3'}`} aria-hidden="true">
        {RATIO_KEYS.map((k) => (ratio[k] > 0 ? <div key={k} className={SEG[k]} style={{ width: `${ratio[k]}%` }} /> : null))}
      </div>
      {labels && <div className={`mt-1 flex flex-wrap gap-x-3 gap-y-0.5 ${compact ? 'text-[11px]' : 'text-xs'}`}>
        {RATIO_KEYS.map((k) => (
          <span key={k} className="inline-flex items-center gap-1 whitespace-nowrap">
            <span className={SEG_TEXT[k]}>
              <TroopIcon troop={RATIO_TROOP[k]} className="w-3.5 h-3.5" />
            </span>
            <span className="text-theme-dim">{t(`tyrant:admin.troopShort.${RATIO_TROOP[k]}`)}</span>
            <bdi dir="ltr" className="font-semibold text-theme-text">
              {ratio[k]}%
            </bdi>
          </span>
        ))}
      </div>}
    </div>
  );
}

/** "At open (11:00 UTC)". */
export function petBuffLabel(t: (k: string, o?: Record<string, unknown>) => string, p: PetBuff, time: string): string {
  return t('svs:plan.petAt', { moment: t(`svs:plan.pet.${p}`), time });
}

/** Joining rules ("Infantry FC8+ T11") for a group's minimums; null entries are skipped. */
export function MinimumsList({ mins }: { mins: Record<TroopKey, { min_camp: string | null; min_tier: number | null }> }) {
  const { t } = useTranslation();
  const rows = TROOPS.filter((k) => mins[k]?.min_camp || mins[k]?.min_tier);
  if (!rows.length) return null;
  return (
    <ul className="flex flex-wrap gap-2" data-testid="minimums">
      {rows.map((k) => (
        <li key={k} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-dark-input border border-theme-border text-sm">
          <span className="text-accent">
            <TroopIcon troop={k} className="w-4 h-4" />
          </span>
          <span className="text-theme-text">{t(`tyrant:admin.troopName.${k}`)}</span>
          <bdi dir="ltr" className="font-semibold text-theme-text">
            {[mins[k].min_camp ? `${mins[k].min_camp}+` : null, mins[k].min_tier ? `T${mins[k].min_tier}${mins[k].min_tier === 10 ? '+' : ''}` : null]
              .filter(Boolean)
              .join(' ')}
          </bdi>
        </li>
      ))}
    </ul>
  );
}

/** A hero picture with its name (shared view, read-only). */
export function HeroTile({ hero, size = 'md', testid }: { hero: ViewHero | null; size?: 'sm' | 'md' | 'lg'; testid?: string }) {
  const { t } = useTranslation();
  const box = size === 'lg' ? 'w-[5.5rem]' : size === 'md' ? 'w-16' : 'w-12';
  if (!hero) {
    return (
      <div className={`${box} shrink-0`} data-testid={testid}>
        <div className="aspect-square rounded-lg border-2 border-dashed border-theme-border/60 bg-dark-input" aria-hidden="true" />
        <div className="text-[11px] text-theme-dim text-center mt-0.5">{t('svs:view.anyHero')}</div>
      </div>
    );
  }
  return (
    <figure className={`${box} shrink-0`} data-testid={testid} data-hero={hero.slug}>
      {hero.image ? (
        <img src={hero.image} alt="" className="block w-full aspect-square object-cover rounded-lg border border-theme-border bg-dark-input" loading="lazy" />
      ) : (
        <div className="w-full aspect-square rounded-lg border border-theme-border bg-dark-input" aria-hidden="true" />
      )}
      <figcaption className={`mt-0.5 text-center leading-tight ${size === 'sm' ? 'text-[10px]' : 'text-xs'} text-theme-text`}>
        <bdi className="block truncate font-medium">{hero.name}</bdi>
        {size !== 'sm' && hero.generation != null && <span className="block text-[10px] text-theme-dim">{t('common:heroes.gen', { n: hero.generation })}</span>}
      </figcaption>
    </figure>
  );
}
