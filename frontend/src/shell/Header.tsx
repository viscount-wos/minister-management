import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LayoutGrid } from 'lucide-react';
import ThemeSelector from './ThemeSelector';
import LanguageSelector from './LanguageSelector';
import TimezoneSelector from '../shared/TimezoneSelector';
import { useTimezone } from '../shared/TimezoneContext';

export default function Header() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const { timezone, setTimezone } = useTimezone();

  return (
    // Everything shares one wrapping row so it stacks tidily on a phone
    // instead of forcing the header wider than the screen.
    <header className="w-full py-3 px-4 flex flex-wrap items-center justify-between gap-x-5 gap-y-2">
      {pathname !== '/' ? (
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-accent hover:text-accent-dim transition-colors text-sm font-medium"
        >
          <LayoutGrid className="w-4 h-4" aria-hidden="true" />
          {t('common:nav.home')}
        </Link>
      ) : (
        <span />
      )}
      <div className="flex flex-wrap items-center justify-end gap-x-5 gap-y-2 ms-auto">
        <TimezoneSelector value={timezone} onChange={setTimezone} label={t('common:header.timezone')} />
        <ThemeSelector />
        <LanguageSelector />
      </div>
    </header>
  );
}
