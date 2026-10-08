import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Crown, Flame, Castle, Swords, Shield, Sparkles, LucideIcon } from 'lucide-react';
import axios from 'axios';
import { MINISTRY_PATHS } from '../events/ministry/paths';

type TileStatus = 'open' | 'nextRelease' | 'comingSoon';

interface EventTile {
  key: 'ministry' | 'tyrant' | 'svs' | 'tal';
  path: string;
  icon: LucideIcon;
  status: TileStatus;
}

// One tile per event, in the order players meet them.
const EVENTS: EventTile[] = [
  { key: 'ministry', path: MINISTRY_PATHS.home, icon: Crown, status: 'open' },
  { key: 'tyrant', path: '/tyrant', icon: Flame, status: 'nextRelease' },
  { key: 'svs', path: '/svs', icon: Castle, status: 'nextRelease' },
  { key: 'tal', path: '/tal', icon: Swords, status: 'comingSoon' },
];

// Tile name/tagline keys. Ministry keeps its strings in the ministry namespace
// under `event.*`; the other events own a namespace each.
const nameKey = (key: EventTile['key']) => (key === 'ministry' ? 'ministry:event.name' : `${key}:name`);
const taglineKey = (key: EventTile['key']) => (key === 'ministry' ? 'ministry:event.tagline' : `${key}:tagline`);

export default function Home() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [stateNumber, setStateNumber] = useState('2694');

  useEffect(() => {
    // Same endpoint (and default) the ministry home has always used.
    axios.get('/api/settings/state-number')
      .then(res => setStateNumber(res.data.state_number || '2694'))
      .catch(() => {});
  }, []);

  return (
    <div className="min-h-[80vh] flex items-center justify-center p-4">
      <div className="max-w-4xl w-full">
        <div className="text-center mb-4">
          <p className="text-2xl text-theme-text font-semibold">
            {t('common:home.welcome', { state: stateNumber })}
          </p>
        </div>

        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-accent mb-4">{t('common:home.title')}</h1>
          <p className="text-xl text-theme-dim">{t('common:home.subtitle')}</p>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          {EVENTS.map(({ key, path, icon: Icon, status }) => {
            const live = status === 'open';
            return (
              <button
                key={key}
                onClick={() => navigate(path)}
                className="bg-dark-card rounded-2xl p-8 border border-theme-border hover:bg-dark-card-hover transform hover:-translate-y-2 transition-all duration-300 group"
              >
                <div className="flex flex-col items-center text-center">
                  <div
                    className={`w-20 h-20 rounded-full flex items-center justify-center mb-6 transition-colors ${
                      live ? 'bg-accent/20 group-hover:bg-accent/30' : 'bg-theme-dim/20 group-hover:bg-theme-dim/30'
                    }`}
                  >
                    <Icon className={`w-10 h-10 ${live ? 'text-accent' : 'text-theme-dim'}`} aria-hidden="true" />
                  </div>
                  <h2 className="text-2xl font-bold text-theme-text mb-3">{t(nameKey(key))}</h2>
                  <p className="text-theme-dim mb-4">{t(taglineKey(key))}</p>
                  <span
                    className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold ${
                      live
                        ? 'bg-success/20 text-success'
                        : 'bg-dark-input border border-theme-border text-theme-dim'
                    }`}
                  >
                    {t(`common:home.status.${status}`)}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Wraps to two rows on a phone rather than overflowing the width */}
        <div className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-3">
          <button
            onClick={() => navigate('/changelog')}
            className="inline-flex items-center gap-2 text-theme-dim hover:text-accent transition-colors text-sm font-medium"
          >
            <Sparkles className="w-4 h-4" aria-hidden="true" />
            {t('changelog:linkText')}
          </button>
          <button
            onClick={() => navigate('/admin')}
            className="inline-flex items-center gap-2 text-theme-dim hover:text-accent transition-colors text-sm font-medium"
          >
            <Shield className="w-4 h-4" aria-hidden="true" />
            {t('admin:title')}
          </button>
        </div>
      </div>
    </div>
  );
}
