import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, Sparkles } from 'lucide-react';
import { usePageTitle } from '../shared/usePageTitle';

// Newest first. Each entry maps to a block of keys in locales/<lang>/changelog.json (all 9 languages).
const RELEASES = [
  { version: '2.2.1', key: 'v221', items: ['a'] },
  { version: '2.2.0', key: 'v220', items: ['a', 'b', 'c', 'd'] },
  { version: '2.1.0', key: 'v210', items: ['a', 'b', 'c', 'd', 'e'] },
  { version: '2.0.0', key: 'v200', items: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'] },
  { version: '1.4.0', key: 'v140', items: ['a', 'b', 'c', 'd', 'e'] },
  { version: '1.3.0', key: 'v130', items: ['a', 'b'] },
  { version: '1.2.0', key: 'v120', items: ['a', 'b', 'c'] },
  { version: '1.1.0', key: 'v110', items: ['a', 'b', 'c'] },
  { version: '1.0.0', key: 'v100', items: ['a', 'b', 'c', 'd'] },
];

export default function Changelog() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  usePageTitle(t('changelog:title'));

  return (
    <div className="min-h-screen px-3 sm:px-4 py-4 sm:py-8">
      <div className="max-w-2xl mx-auto">
        <button
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-2 min-h-[44px] text-accent hover:text-accent-dim transition-colors text-sm font-medium mb-4 sm:mb-6"
        >
          <ArrowLeft className="w-4 h-4 rtl:rotate-180" aria-hidden="true" />
          {t('changelog:backHome')}
        </button>

        <h1 className="text-3xl sm:text-4xl font-bold text-accent mb-2">
          {t('changelog:title')}
        </h1>
        <p className="text-theme-dim mb-6 sm:mb-10 leading-relaxed">
          {t('changelog:subtitle')}
        </p>

        <div className="space-y-5">
          {RELEASES.map((release, index) => (
            <section
              key={release.version}
              className="bg-dark-card border border-theme-border rounded-xl p-4 sm:p-6"
            >
              {/* Wraps to two rows on a narrow screen rather than squashing */}
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2 mb-3">
                <h2 className="text-lg font-semibold text-theme-text">
                  {t(`changelog:${release.key}Title`)}
                </h2>
                {index === 0 && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent/20 text-accent text-xs font-semibold">
                    <Sparkles className="w-3 h-3" />
                    {t('changelog:latest')}
                  </span>
                )}
                <span className="text-theme-dim text-sm ms-auto whitespace-nowrap">
                  {t(`changelog:${release.key}Date`)}
                </span>
              </div>

              <ul className="space-y-2">
                {release.items.map((item) => (
                  <li key={item} className="flex gap-3 text-theme-text leading-relaxed">
                    <span className="text-accent shrink-0" aria-hidden="true">&bull;</span>
                    <span>{t(`changelog:${release.key}${item}`)}</span>
                  </li>
                ))}
              </ul>

              <p className="text-theme-dim text-xs mt-4">v{release.version}</p>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
