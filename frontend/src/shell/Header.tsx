import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Clock, LayoutGrid } from 'lucide-react';
import ThemeSelector from './ThemeSelector';
import LanguageSelector from './LanguageSelector';
import CompactSelect from './CompactSelect';
import { TimezoneOptions } from '../shared/TimezoneSelector';
import { useTimezone } from '../shared/TimezoneContext';
import { saveTimezone, timezoneShortLabel } from '../shared/timezone';

// ONE row on every width (SPEC "Phone-first header"): the "All events" link
// (icon only on phones) and three compact dropdowns: timezone (clock + short
// zone), language (globe + its own name), theme (palette; name from sm up).
// Each is a native <select> under a 44px chip, so phones get their own picker.
export default function Header() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const { timezone, setTimezone } = useTimezone();

  const changeTimezone = (tz: string) => {
    saveTimezone(tz);
    setTimezone(tz);
  };

  return (
    <header className="w-full py-2 px-3 sm:py-3 sm:px-4 flex items-center gap-2 sm:gap-4" data-testid="site-header">
      {pathname !== '/' && (
        <Link
          to="/"
          data-testid="nav-home"
          aria-label={t('common:nav.home')}
          className="inline-flex items-center justify-center gap-2 h-11 min-w-[44px] px-2 sm:px-0 rounded-lg text-accent hover:text-accent-dim transition-colors text-sm font-medium shrink-0"
        >
          <LayoutGrid className="w-5 h-5 sm:w-4 sm:h-4" aria-hidden="true" />
          <span className="hidden sm:inline" aria-hidden="true">
            {t('common:nav.home')}
          </span>
        </Link>
      )}
      <div className="flex items-center justify-end gap-1.5 sm:gap-2 ms-auto min-w-0" data-testid="header-controls">
        <CompactSelect
          icon={Clock}
          label={t('common:header.timezone')}
          display={timezoneShortLabel(timezone)}
          value={timezone}
          onChange={changeTimezone}
          testId="header-timezone"
        >
          <TimezoneOptions value={timezone} />
        </CompactSelect>
        <LanguageSelector />
        <ThemeSelector />
      </div>
    </header>
  );
}
