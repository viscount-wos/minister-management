import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

// The big navigation tiles (Home events, an event's Apply / Event Management).
// Phones: a compact row (icon beside the text) so several fit on one screen;
// from sm up: the original tall card with the icon on top.

interface TileProps {
  icon: LucideIcon;
  title: ReactNode;
  description?: ReactNode;
  badge?: ReactNode;
  onClick: () => void;
  testId: string;
  /** Live/accent look vs greyed (not open / coming soon). */
  live?: boolean;
  disabled?: boolean;
}

export default function Tile({ icon: Icon, title, description, badge, onClick, testId, live = true, disabled }: TileProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      data-testid={testId}
      className={`w-full bg-dark-card rounded-2xl p-4 sm:p-8 border border-theme-border transition-all duration-300 group ${
        disabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-dark-card-hover sm:transform sm:hover:-translate-y-2'
      }`}
    >
      <div className="flex flex-row sm:flex-col items-center gap-4 sm:gap-0 text-start sm:text-center">
        <div
          className={`w-14 h-14 sm:w-20 sm:h-20 shrink-0 rounded-full flex items-center justify-center sm:mb-6 transition-colors ${
            live && !disabled ? 'bg-accent/20 group-hover:bg-accent/30' : 'bg-theme-dim/20 group-hover:bg-theme-dim/30'
          }`}
        >
          <Icon className={`w-7 h-7 sm:w-10 sm:h-10 ${live && !disabled ? 'text-accent' : 'text-theme-dim'}`} aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1 sm:flex-none">
          <h2 className="text-xl sm:text-2xl font-bold text-theme-text mb-1 sm:mb-3 break-words">{title}</h2>
          {description && <p className="text-theme-dim text-sm sm:text-base break-words">{description}</p>}
          {badge && <div className="mt-2 sm:mt-4">{badge}</div>}
        </div>
      </div>
    </button>
  );
}

/** Title + subtitle at the top of a landing page. */
export function PageHero({ title, subtitle }: { title: ReactNode; subtitle?: ReactNode }) {
  return (
    <div className="text-center mb-6 sm:mb-12">
      <h1 className="text-3xl sm:text-5xl font-bold text-accent mb-2 sm:mb-4 break-words">{title}</h1>
      {subtitle && <p className="text-base sm:text-xl text-theme-dim">{subtitle}</p>}
    </div>
  );
}

/** Small text link-button under the tiles (guide, what's new, admin): 44px tap target. */
export function LinkButton({
  icon: Icon,
  children,
  onClick,
  testId,
  accent,
  flipInRtl,
}: {
  icon: LucideIcon;
  children: ReactNode;
  onClick: () => void;
  testId?: string;
  accent?: boolean;
  flipInRtl?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      className={`inline-flex items-center gap-2 min-h-[44px] px-2 transition-colors text-sm font-medium ${
        accent ? 'text-accent hover:text-accent-dim' : 'text-theme-dim hover:text-accent'
      }`}
    >
      <Icon className={`w-4 h-4 shrink-0 ${flipInRtl ? 'rtl:rotate-180' : ''}`} aria-hidden="true" />
      {children}
    </button>
  );
}
