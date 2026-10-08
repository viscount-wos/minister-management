import { Suspense } from 'react';
import { Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { isRtl } from '../i18n/index';
import Header from './Header';

export default function Layout() {
  const { t, i18n } = useTranslation();

  // Set document direction for RTL languages (also kept in sync by the
  // languageChanged listener in i18n/index.ts).
  document.documentElement.dir = isRtl(i18n.language) ? 'rtl' : 'ltr';

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <div className="flex-1">
        {/* Pages are lazy chunks (src/pages.ts): keep the header while one loads */}
        <Suspense
          fallback={
            <p className="py-16 text-center text-theme-dim" role="status" data-testid="page-loading">
              {t('common:loading')}
            </p>
          }
        >
          <Outlet />
        </Suspense>
      </div>
      <footer className="mt-auto pb-4 text-center">
        <p className="text-xs italic text-theme-dim">{t('common:footer')}</p>
      </footer>
    </div>
  );
}
