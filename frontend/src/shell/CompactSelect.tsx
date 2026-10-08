import type { ReactNode } from 'react';
import { ChevronDown, LucideIcon } from 'lucide-react';

// A compact header control: icon + short value + chevron, with a NATIVE <select>
// stretched invisibly over it. Phones get their own picker (iOS wheel, Android
// sheet), keyboards and screen readers get a real labelled select, and the
// visible chip stays one small 44px-tall box.

interface CompactSelectProps {
  icon: LucideIcon;
  /** Accessible name of the select (also the tooltip). */
  label: string;
  /** What the chip shows for the current value. */
  display: ReactNode;
  value: string;
  onChange: (value: string) => void;
  testId: string;
  /** Hide the value text below the sm breakpoint (icon + chevron only on phones). */
  textFromSm?: boolean;
  /** Language of the visible text (e.g. a language's own name). */
  displayLang?: string;
  children: ReactNode;
}

export default function CompactSelect({
  icon: Icon,
  label,
  display,
  value,
  onChange,
  testId,
  textFromSm,
  displayLang,
  children,
}: CompactSelectProps) {
  return (
    <div
      className="relative inline-flex items-center gap-1 sm:gap-1.5 h-11 min-w-[44px] px-2 sm:px-3 rounded-lg border border-theme-border bg-dark-input text-theme-text hover:border-accent focus-within:ring-2 focus-within:ring-accent focus-within:border-accent transition-colors"
      title={label}
      data-testid={`${testId}-chip`}
    >
      <Icon className="w-5 h-5 text-theme-dim shrink-0" aria-hidden="true" />
      <span
        className={`text-sm font-medium whitespace-nowrap truncate max-w-[5.5rem] sm:max-w-[10rem] ${textFromSm ? 'hidden sm:inline' : ''}`}
        aria-hidden="true"
        lang={displayLang}
      >
        {display}
      </span>
      <ChevronDown className="w-3.5 h-3.5 text-theme-dim shrink-0" aria-hidden="true" />
      <select
        aria-label={label}
        data-testid={testId}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        // 16px text: iOS zooms the page when a smaller control gets focus.
        className="absolute -inset-px opacity-0 cursor-pointer text-base bg-dark-input text-theme-text"
      >
        {children}
      </select>
    </div>
  );
}
