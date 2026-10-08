import { forwardRef, type SVGProps } from 'react';

// Troop icons drawn in lucide-react's style (24px grid, currentColor stroke, round caps), because lucide has no spear
// or crossbow. Infantry keeps lucide's Shield. Owner request: Lancer = spear (not crossed swords), Marksman = crossbow
// (not crosshairs).

type IconProps = SVGProps<SVGSVGElement> & { size?: number | string; strokeWidth?: number | string };

function base({ size = 24, strokeWidth = 2, ...rest }: IconProps) {
  return {
    xmlns: 'http://www.w3.org/2000/svg',
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    ...(rest['aria-label'] ? {} : { 'aria-hidden': true }),
    ...rest,
  };
}

/** A spear: a diagonal shaft with a leaf-shaped head and a binding below it. */
export const SpearIcon = forwardRef<SVGSVGElement, IconProps>(function SpearIcon(props, ref) {
  return (
    <svg ref={ref} {...base(props)}>
      <path d="M21 3 18.5 8.5 15 9l.5-3.5Z" />
      <path d="M15 9 3 21" />
      <path d="m12.6 8.9 2.5 2.5" />
    </svg>
  );
});

/** A crossbow: the bow (prod) across the top, the string, the stock, a bolt and the trigger. */
export const CrossbowIcon = forwardRef<SVGSVGElement, IconProps>(function CrossbowIcon(props, ref) {
  return (
    <svg ref={ref} {...base(props)}>
      <path d="M3 12C5.5 6 18.5 6 21 12" />
      <path d="M3 12 12 15l9-3" />
      <path d="M12 4v17" />
      <path d="m10 6 2-3 2 3" />
      <path d="M12 17.5h2.5" />
    </svg>
  );
});
