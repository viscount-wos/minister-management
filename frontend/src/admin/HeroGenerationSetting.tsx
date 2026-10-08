import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Save, Check, AlertCircle } from 'lucide-react';
import api from '../shared/api';
import { errorText } from '../shared/apiErrors';

// State-wide "State hero generation" (global setting, like the state number; not per round). Shown in the Minister
// Settings tab next to the state number and on the SVS Heroes tab. Planners never offer heroes above it.
export const MAX_GENERATION = 17;

export default function HeroGenerationSetting({ onSaved, className = '' }: { onSaved?: (gen: number) => void; className?: string }) {
  const { t } = useTranslation();
  const [gen, setGen] = useState<number | null>(null);
  const [saved, setSaved] = useState<number | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    api.admin
      .settings()
      .then((s) => {
        setGen(s.state_generation);
        setSaved(s.state_generation);
      })
      .catch(() => {});
  }, []);

  const save = async () => {
    if (gen == null) return;
    try {
      const res = await api.admin.updateSettings({ state_generation: gen });
      setGen(res.state_generation);
      setSaved(res.state_generation);
      setMsg({ ok: true, text: t('admin:settingsSaved') });
      onSaved?.(res.state_generation);
    } catch (e) {
      setMsg({ ok: false, text: errorText(t, e, 'admin:settingsError') });
    }
  };

  return (
    <div className={`bg-dark-card rounded-xl border border-theme-border p-4 sm:p-6 ${className}`} data-testid="hero-generation-card">
      <h3 className="text-xl font-bold text-accent mb-2">
        <label htmlFor="state-generation">{t('admin:heroes.generation')}</label>
      </h3>
      <p className="text-theme-dim text-sm mb-4">{t('admin:heroes.generationDesc')}</p>
      <div className="flex flex-wrap gap-3 items-center">
        <select
          id="state-generation"
          data-testid="state-generation"
          value={gen ?? ''}
          disabled={gen == null}
          onChange={(e) => {
            setGen(Number(e.target.value));
            setMsg(null);
          }}
          className="min-h-[44px] px-3 py-2 text-base bg-dark-input border border-theme-border rounded-lg text-theme-text"
        >
          {Array.from({ length: MAX_GENERATION }, (_, i) => i + 1).map((n) => (
            <option key={n} value={n}>
              {t('common:heroes.gen', { n })}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={save}
          disabled={gen == null || gen === saved}
          data-testid="save-state-generation"
          className="flex items-center gap-2 min-h-[44px] px-4 py-2 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium disabled:opacity-50"
        >
          <Save className="w-4 h-4" aria-hidden="true" />
          {t('common:save')}
        </button>
        {msg && (
          <span
            role={msg.ok ? 'status' : 'alert'}
            data-testid={msg.ok ? 'state-generation-saved' : 'state-generation-error'}
            className={`flex items-center gap-1 text-sm ${msg.ok ? 'text-success' : 'text-danger'}`}
          >
            {msg.ok ? <Check className="w-4 h-4" aria-hidden="true" /> : <AlertCircle className="w-4 h-4" aria-hidden="true" />}
            {msg.text}
          </span>
        )}
      </div>
    </div>
  );
}
