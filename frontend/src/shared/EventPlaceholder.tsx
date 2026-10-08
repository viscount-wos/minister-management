import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, Hourglass, LucideIcon } from 'lucide-react';
import { usePageTitle } from './usePageTitle';

interface EventPlaceholderProps {
  /** Namespace holding the event's `name` and `tagline` keys. */
  ns: 'tyrant' | 'svs' | 'tal';
  icon: LucideIcon;
  /** 'nextRelease': module is being built; 'comingSoon': not planned yet. */
  status: 'nextRelease' | 'comingSoon';
}

// Stand-in page for an event whose module has not shipped yet.
export default function EventPlaceholder({ ns, icon: Icon, status }: EventPlaceholderProps) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  usePageTitle(t(`${ns}:name`));

  return (
    <div className="min-h-[70vh] flex items-center justify-center p-4">
      <div className="max-w-xl w-full bg-dark-card border border-theme-border rounded-2xl p-5 sm:p-10 text-center">
        <div className="w-20 h-20 mx-auto rounded-full bg-accent/20 flex items-center justify-center mb-6">
          <Icon className="w-10 h-10 text-accent" aria-hidden="true" />
        </div>
        <h1 className="text-3xl sm:text-4xl font-bold text-accent mb-3">{t(`${ns}:name`)}</h1>
        <p className="text-theme-dim mb-8">{t(`${ns}:tagline`)}</p>

        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent/10 border border-accent/40 text-accent text-sm font-semibold mb-4">
          <Hourglass className="w-4 h-4" aria-hidden="true" />
          {t(`common:placeholder.${status}Title`)}
        </div>
        <p className="text-theme-text leading-relaxed mb-8">{t(`common:placeholder.${status}Body`)}</p>

        <button
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-2 min-h-[44px] text-accent hover:text-accent-dim transition-colors text-sm font-medium"
        >
          <ArrowLeft className="w-4 h-4 rtl:rotate-180" aria-hidden="true" />
          {t('common:nav.home')}
        </button>
      </div>
    </div>
  );
}
