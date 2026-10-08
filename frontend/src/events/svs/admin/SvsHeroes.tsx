import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertCircle } from 'lucide-react';
import { errorText } from '../../../shared/apiErrors';
import HeroCard, { HeroCredit, TroopIcon } from '../../../shared/heroes/HeroCard';
import { HERO_TROOPS, HeroLibrary, HeroTroop, fetchHeroes } from '../../../shared/heroes/api';
import HeroGenerationSetting from '../../../admin/HeroGenerationSetting';

// Event Management -> SVS -> Heroes: a reference view of the hero library as planners will see it (up to the state's
// hero generation), filterable by troop, so the owner can check names, pictures and generations. The drag-and-drop
// picker of the SVS planner will reuse HeroCard.

export default function SvsHeroes() {
  const { t } = useTranslation();
  const [lib, setLib] = useState<HeroLibrary | null>(null);
  const [troop, setTroop] = useState<HeroTroop | ''>('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setLib(await fetchHeroes({ troop: troop || undefined }));
      setError('');
    } catch (e) {
      setError(errorText(t, e, 'admin:fetchError'));
    }
  }, [troop, t]);

  useEffect(() => {
    load();
  }, [load]);

  const chip = (value: HeroTroop | '', label: string) => (
    <button
      key={value || 'all'}
      type="button"
      onClick={() => setTroop(value)}
      aria-pressed={troop === value}
      data-testid={`hero-troop-${value || 'all'}`}
      className={`inline-flex items-center gap-2 min-h-[44px] px-4 rounded-full border text-sm font-medium ${
        troop === value ? 'border-accent bg-accent/20 text-accent' : 'border-theme-border text-theme-text hover:bg-dark-card-hover'
      }`}
    >
      {value && <TroopIcon troop={value} />}
      {label}
    </button>
  );

  return (
    <div className="space-y-6" data-testid="heroes-panel">
      <HeroGenerationSetting onSaved={() => load()} />

      <div className="bg-dark-card rounded-xl border border-theme-border p-4 sm:p-6">
        <div className="flex flex-wrap items-center gap-3 mb-2">
          <h3 className="text-xl font-bold text-accent flex-1">{t('admin:heroes.title')}</h3>
          {lib && (
            <p className="text-sm text-theme-dim" data-testid="heroes-count">
              {t('admin:heroes.count', { n: lib.total, gen: lib.max_gen })}
            </p>
          )}
        </div>
        <p className="text-theme-dim text-sm mb-4">{t('admin:heroes.desc')}</p>
        <div className="flex flex-wrap gap-2 mb-5" role="group" aria-label={t('tyrant:admin.filter.troop')}>
          {chip('', t('tyrant:admin.troopName.all'))}
          {HERO_TROOPS.map((k) => chip(k, t(`tyrant:admin.troopName.${k}`)))}
        </div>
        {error && (
          <div className="mb-4 p-3 bg-danger/10 border border-danger/30 rounded-lg flex items-center gap-2 text-danger" role="alert">
            <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
            {error}
          </div>
        )}
        <div className="flex flex-wrap gap-3" data-testid="hero-grid">
          {lib?.heroes.map((h) => <HeroCard key={h.slug} hero={h} />)}
        </div>
        <HeroCredit className="mt-5" />
      </div>
    </div>
  );
}
