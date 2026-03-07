import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Search, ArrowLeft, Save, AlertCircle, CheckCircle } from 'lucide-react';
import axios from 'axios';

interface PlayerData {
  id?: number;
  fid: string;
  game_name: string;
  construction_speedups_days: number;
  research_speedups_days: number;
  troop_training_speedups_days: number;
  general_speedups_days: number;
  fire_crystals: number;
  refined_fire_crystals: number;
  fire_crystal_shards: number;
  time_slots: string[];
  avatar_image?: string;
  stove_lv?: number;
  stove_lv_content?: string;
  alliance?: string;
}

export default function UpdateSubmission() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [searchFid, setSearchFid] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [playerData, setPlayerData] = useState<PlayerData | null>(null);

  const timeSlots = Array.from({ length: 24 }, (_, i) => `${i.toString().padStart(2, '0')}:00`);

  const handleSearch = async () => {
    if (!searchFid.trim()) {
      setError(t('form.enterPlayerID'));
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axios.get(`/api/player/${searchFid}`);
      setPlayerData(response.data);
    } catch (err: any) {
      if (err.response?.status === 404) {
        setError(t('update.notFound'));
      } else {
        setError(err.response?.data?.error || t('form.errorOccurred'));
      }
      setPlayerData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!playerData) return;

    const { name, value } = e.target;
    setPlayerData(prev => ({
      ...prev!,
      [name]: name === 'game_name' || name === 'fid' || name === 'alliance' ? value : parseFloat(value) || 0,
    }));
  };

  const toggleTimeSlot = (time: string) => {
    if (!playerData) return;

    setPlayerData(prev => ({
      ...prev!,
      time_slots: prev!.time_slots.includes(time)
        ? prev!.time_slots.filter(t => t !== time)
        : [...prev!.time_slots, time],
    }));
  };

  const handleUpdate = async () => {
    if (!playerData) return;

    setLoading(true);
    setError('');

    try {
      await axios.post('/api/player/submit', playerData);
      setSuccess(true);
      setTimeout(() => {
        navigate('/');
      }, 2000);
    } catch (err: any) {
      setError(err.response?.data?.error || t('form.updateError'));
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="bg-dark-card rounded-2xl p-12 border border-theme-border max-w-md w-full text-center">
          <CheckCircle className="w-20 h-20 text-success mx-auto mb-6" />
          <h2 className="text-3xl font-bold text-accent mb-4">{t('form.success')}</h2>
          <p className="text-theme-dim">{t('form.updateSuccess')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="bg-dark-card rounded-2xl p-8 border border-theme-border max-w-4xl w-full">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 text-theme-dim hover:text-theme-text mb-6"
        >
          <ArrowLeft className="w-5 h-5" />
          {t('update.backHome')}
        </button>

        <h2 className="text-3xl font-bold text-accent mb-6 text-center">
          {t('update.title')}
        </h2>

        {!playerData ? (
          <div>
            <p className="text-theme-dim text-center mb-6">{t('update.enterFID')}</p>
            <div className="flex gap-4">
              <input
                type="text"
                value={searchFid}
                onChange={(e) => setSearchFid(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                placeholder={t('update.fidLabel')}
                className="flex-1 px-4 py-3 bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim focus:ring-2 focus:ring-accent focus:border-accent"
              />
              <button
                onClick={handleSearch}
                disabled={loading}
                className="flex items-center gap-2 px-6 py-3 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors disabled:opacity-50"
              >
                <Search className="w-5 h-5" />
                {t('update.load')}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Player Information */}
            <div>
              <h3 className="text-xl font-semibold mb-4 text-accent">{t('form.playerInfo')}</h3>
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-4">
                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-theme-text mb-2">
                      {t('form.gameName')}
                    </label>
                    <input
                      type="text"
                      name="game_name"
                      value={playerData.game_name}
                      onChange={handleInputChange}
                      className="w-full px-4 py-3 bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim focus:ring-2 focus:ring-accent focus:border-accent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-theme-text mb-2">
                      {t('form.alliance')}
                    </label>
                    <input
                      type="text"
                      name="alliance"
                      value={playerData.alliance || ''}
                      onChange={(e) => setPlayerData(prev => prev ? { ...prev, alliance: e.target.value.toUpperCase().slice(0, 3) } : prev)}
                      maxLength={3}
                      className="w-full px-4 py-3 bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim focus:ring-2 focus:ring-accent focus:border-accent uppercase"
                      placeholder={t('form.alliancePlaceholder')}
                    />
                  </div>
                </div>
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-theme-text mb-2">
                      {t('form.constructionSpeedups')}
                    </label>
                    <input
                      type="number"
                      name="construction_speedups_days"
                      value={playerData.construction_speedups_days}
                      onChange={handleInputChange}
                      min="0"
                      step="0.1"
                      className="w-full px-4 py-3 bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim focus:ring-2 focus:ring-accent focus:border-accent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-theme-text mb-2">
                      {t('form.researchSpeedups')}
                    </label>
                    <input
                      type="number"
                      name="research_speedups_days"
                      value={playerData.research_speedups_days}
                      onChange={handleInputChange}
                      min="0"
                      step="0.1"
                      className="w-full px-4 py-3 bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim focus:ring-2 focus:ring-accent focus:border-accent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-theme-text mb-2">
                      {t('form.troopSpeedups')}
                    </label>
                    <input
                      type="number"
                      name="troop_training_speedups_days"
                      value={playerData.troop_training_speedups_days}
                      onChange={handleInputChange}
                      min="0"
                      step="0.1"
                      className="w-full px-4 py-3 bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim focus:ring-2 focus:ring-accent focus:border-accent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-theme-text mb-2">
                      {t('form.generalSpeedups')}
                    </label>
                    <input
                      type="number"
                      name="general_speedups_days"
                      value={playerData.general_speedups_days}
                      onChange={handleInputChange}
                      min="0"
                      step="0.1"
                      className="w-full px-4 py-3 bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim focus:ring-2 focus:ring-accent focus:border-accent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-theme-text mb-2">
                      {t('form.fireCrystals')}
                    </label>
                    <input
                      type="number"
                      name="fire_crystals"
                      value={playerData.fire_crystals}
                      onChange={handleInputChange}
                      min="0"
                      className="w-full px-4 py-3 bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim focus:ring-2 focus:ring-accent focus:border-accent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-theme-text mb-2">
                      {t('form.refinedFireCrystals')}
                    </label>
                    <input
                      type="number"
                      name="refined_fire_crystals"
                      value={playerData.refined_fire_crystals}
                      onChange={handleInputChange}
                      min="0"
                      className="w-full px-4 py-3 bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim focus:ring-2 focus:ring-accent focus:border-accent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-theme-text mb-2">
                      {t('form.fireCrystalShards')}
                    </label>
                    <input
                      type="number"
                      name="fire_crystal_shards"
                      value={playerData.fire_crystal_shards}
                      onChange={handleInputChange}
                      min="0"
                      className="w-full px-4 py-3 bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim focus:ring-2 focus:ring-accent focus:border-accent"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Time Preferences */}
            <div>
              <h3 className="text-xl font-semibold mb-4 text-accent">{t('form.selectTimes')}</h3>
              <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-3">
                {timeSlots.map((time) => (
                  <button
                    key={time}
                    onClick={() => toggleTimeSlot(time)}
                    className={`p-3 rounded-lg border-2 transition-all font-medium ${
                      playerData.time_slots?.includes(time)
                        ? 'bg-accent border-accent text-dark-bg'
                        : 'bg-dark-input border-theme-border text-theme-text hover:border-accent'
                    }`}
                  >
                    {time}
                  </button>
                ))}
              </div>
            </div>

            {/* Update Button */}
            <button
              onClick={handleUpdate}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors disabled:opacity-50"
            >
              <Save className="w-5 h-5" />
              {loading ? t('form.loading') : t('form.update')}
            </button>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="mt-6 p-4 bg-danger/10 border border-danger/30 rounded-lg flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-danger" />
            <p className="text-danger">{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}
