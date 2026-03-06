import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, ArrowRight, CheckCircle, AlertCircle, Download, Loader2 } from 'lucide-react';
import axios from 'axios';

interface PlayerData {
  fid: string;
  game_name: string;
  construction_speedups_days: number;
  research_speedups_days: number;
  troop_training_speedups_days: number;
  general_speedups_days: number;
  fire_crystals: number;
  refined_fire_crystals: number;
  fire_crystal_shards: number;
  avatar_image?: string;
  stove_lv?: number;
  stove_lv_content?: string;
}

export default function PlayerForm() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [wosLoading, setWosLoading] = useState(false);

  const [playerData, setPlayerData] = useState<PlayerData>({
    fid: '',
    game_name: '',
    construction_speedups_days: 0,
    research_speedups_days: 0,
    troop_training_speedups_days: 0,
    general_speedups_days: 0,
    fire_crystals: 0,
    refined_fire_crystals: 0,
    fire_crystal_shards: 0,
  });

  const [selectedTimes, setSelectedTimes] = useState<string[]>([]);

  // Generate time slots from 00:00 to 23:00 in 1-hour increments
  const timeSlots = Array.from({ length: 24 }, (_, i) => `${i.toString().padStart(2, '0')}:00`);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setPlayerData(prev => ({
      ...prev,
      [name]: name === 'game_name' || name === 'fid' ? value : parseFloat(value) || 0,
    }));
  };

  const handleWosLookup = async () => {
    if (!playerData.fid.trim()) {
      setError(t('form.enterFidFirst'));
      return;
    }

    setWosLoading(true);
    setError('');

    try {
      const response = await axios.post('/api/player/wos-lookup', {
        fid: playerData.fid.trim(),
      });

      const wosData = response.data;
      setPlayerData(prev => ({
        ...prev,
        game_name: wosData.nickname || prev.game_name,
        avatar_image: wosData.avatar_image || undefined,
        stove_lv: wosData.stove_lv || undefined,
        stove_lv_content: wosData.stove_lv_content || undefined,
      }));
    } catch (err: any) {
      const msg = err.response?.data?.error || 'Failed to look up player from WOS';
      setError(msg);
    } finally {
      setWosLoading(false);
    }
  };

  const toggleTimeSlot = (time: string) => {
    setSelectedTimes(prev =>
      prev.includes(time)
        ? prev.filter(t => t !== time)
        : [...prev, time]
    );
  };

  const validateStep1 = () => {
    if (!playerData.game_name.trim()) {
      setError(t('form.required'));
      return false;
    }
    // FID is now required
    if (!playerData.fid || !playerData.fid.trim()) {
      setError('Player ID (FID) is required');
      return false;
    }
    setError('');
    return true;
  };

  const handleNext = () => {
    if (step === 1 && !validateStep1()) {
      return;
    }
    setStep(step + 1);
  };

  const handleBack = () => {
    setStep(step - 1);
    setError('');
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError('');

    try {
      const submitData = {
        ...playerData,
        time_slots: selectedTimes,
      };

      await axios.post('/api/player/submit', submitData);
      setSuccess(true);
      setTimeout(() => {
        navigate('/');
      }, 2000);
    } catch (err: any) {
      setError(err.response?.data?.error || 'An error occurred while submitting');
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
          <p className="text-theme-dim">{t('form.submissionSuccess')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 py-20">
      <div className="bg-dark-card rounded-2xl p-8 border border-theme-border max-w-4xl w-full">
        {/* Progress Indicator */}
        <div className="flex items-center justify-center mb-8">
          {[1, 2, 3].map((num) => (
            <div key={num} className="flex items-center">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${
                  step >= num
                    ? 'bg-accent text-dark-bg'
                    : 'bg-dark-bg text-theme-dim border-2 border-theme-border'
                }`}
              >
                {num}
              </div>
              {num < 3 && (
                <div
                  className={`w-16 h-1 mx-2 ${
                    step > num ? 'bg-accent' : 'bg-theme-border'
                  }`}
                />
              )}
            </div>
          ))}
        </div>

        {/* Step 1: Player Information */}
        {step === 1 && (
          <div>
            <h2 className="text-3xl font-bold text-accent mb-6 text-center">
              {t('form.step1Title')}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-theme-text mb-2">
                  {t('form.playerID')} *
                </label>
                <div className="flex gap-3">
                  <input
                    type="text"
                    name="fid"
                    value={playerData.fid}
                    onChange={handleInputChange}
                    className="flex-1 px-4 py-3 bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim focus:ring-2 focus:ring-accent focus:border-accent"
                    placeholder="Enter your unique Player ID"
                    required
                  />
                  <button
                    type="button"
                    onClick={handleWosLookup}
                    disabled={wosLoading || !playerData.fid.trim()}
                    className="flex items-center gap-2 px-4 py-3 bg-success text-dark-bg rounded-lg hover:bg-success/80 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
                  >
                    {wosLoading ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Download className="w-5 h-5" />
                    )}
                    {t('form.loadFromWOS')}
                  </button>
                </div>
              </div>

              {/* Avatar preview after WOS lookup */}
              {playerData.avatar_image && (
                <div className="flex items-center gap-4 p-4 bg-dark-bg rounded-lg border border-accent/30">
                  <img
                    src={playerData.avatar_image}
                    alt="Player avatar"
                    className="w-16 h-16 rounded-full border-2 border-accent"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                  />
                  {playerData.stove_lv_content && (
                    <img
                      src={playerData.stove_lv_content}
                      alt={`Furnace level ${playerData.stove_lv}`}
                      className="w-8 h-8"
                    />
                  )}
                  <div className="text-theme-text font-medium">{playerData.game_name}</div>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-theme-text mb-2">
                  {t('form.gameName')} *
                </label>
                <input
                  type="text"
                  name="game_name"
                  value={playerData.game_name}
                  onChange={handleInputChange}
                  className="w-full px-4 py-3 bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim focus:ring-2 focus:ring-accent focus:border-accent"
                  required
                />
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
        )}

        {/* Step 2: Time Preferences */}
        {step === 2 && (
          <div>
            <h2 className="text-3xl font-bold text-accent mb-4 text-center">
              {t('form.step2Title')}
            </h2>
            <p className="text-theme-dim text-center mb-6">{t('form.selectMultiple')}</p>
            <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-3">
              {timeSlots.map((time) => (
                <button
                  key={time}
                  onClick={() => toggleTimeSlot(time)}
                  className={`p-3 rounded-lg border-2 transition-all font-medium ${
                    selectedTimes.includes(time)
                      ? 'bg-accent border-accent text-dark-bg'
                      : 'bg-dark-input border-theme-border text-theme-text hover:border-accent'
                  }`}
                >
                  {time}
                </button>
              ))}
            </div>
            <p className="text-sm text-theme-dim mt-4 text-center">
              Selected: {selectedTimes.length} time slots
            </p>
          </div>
        )}

        {/* Step 3: Review */}
        {step === 3 && (
          <div>
            <h2 className="text-3xl font-bold text-accent mb-6 text-center">
              {t('form.step3Title')}
            </h2>
            <div className="space-y-4">
              <div className="bg-dark-bg p-6 rounded-lg border border-theme-border">
                {playerData.avatar_image && (
                  <div className="flex items-center gap-3 mb-4 pb-4 border-b border-theme-border">
                    <img src={playerData.avatar_image} alt="Avatar" className="w-12 h-12 rounded-full border-2 border-accent" />
                    {playerData.stove_lv_content && (
                      <img src={playerData.stove_lv_content} alt="Stove level" className="w-6 h-6" />
                    )}
                  </div>
                )}
                <h3 className="font-semibold text-lg mb-4 text-accent">Player Information</h3>
                <div className="grid md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-theme-dim">Game Name:</span>
                    <span className="ml-2 font-medium text-theme-text">{playerData.game_name}</span>
                  </div>
                  <div>
                    <span className="text-theme-dim">Player ID:</span>
                    <span className="ml-2 font-medium text-theme-text">{playerData.fid}</span>
                  </div>
                  <div>
                    <span className="text-theme-dim">Construction Speedups:</span>
                    <span className="ml-2 font-medium text-theme-text">{playerData.construction_speedups_days} days</span>
                  </div>
                  <div>
                    <span className="text-theme-dim">Research Speedups:</span>
                    <span className="ml-2 font-medium text-theme-text">{playerData.research_speedups_days} days</span>
                  </div>
                  <div>
                    <span className="text-theme-dim">Troop Speedups:</span>
                    <span className="ml-2 font-medium text-theme-text">{playerData.troop_training_speedups_days} days</span>
                  </div>
                  <div>
                    <span className="text-theme-dim">General Speedups:</span>
                    <span className="ml-2 font-medium text-theme-text">{playerData.general_speedups_days} days</span>
                  </div>
                  <div>
                    <span className="text-theme-dim">Fire Crystals:</span>
                    <span className="ml-2 font-medium text-theme-text">{playerData.fire_crystals}</span>
                  </div>
                  <div>
                    <span className="text-theme-dim">Refined Fire Crystals:</span>
                    <span className="ml-2 font-medium text-theme-text">{playerData.refined_fire_crystals}</span>
                  </div>
                  <div>
                    <span className="text-theme-dim">Fire Crystal Shards:</span>
                    <span className="ml-2 font-medium text-theme-text">{playerData.fire_crystal_shards}</span>
                  </div>
                </div>
              </div>
              <div className="bg-dark-bg p-6 rounded-lg border border-theme-border">
                <h3 className="font-semibold text-lg mb-4 text-accent">Time Preferences (UTC)</h3>
                <div className="flex flex-wrap gap-2">
                  {selectedTimes.sort().map((time) => (
                    <span
                      key={time}
                      className="px-3 py-1 bg-accent/20 text-accent rounded-full text-sm font-medium"
                    >
                      {time}
                    </span>
                  ))}
                  {selectedTimes.length === 0 && (
                    <span className="text-theme-dim">No time preferences selected</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="mt-6 p-4 bg-danger/10 border border-danger/30 rounded-lg flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-danger" />
            <p className="text-danger">{error}</p>
          </div>
        )}

        {/* Navigation Buttons */}
        <div className="flex justify-between mt-8">
          <button
            onClick={step === 1 ? () => navigate('/') : handleBack}
            className="flex items-center gap-2 px-6 py-3 border-2 border-theme-border rounded-lg hover:bg-dark-card-hover font-medium transition-colors text-theme-text"
          >
            <ArrowLeft className="w-5 h-5" />
            {t('form.back')}
          </button>
          {step < 3 ? (
            <button
              onClick={handleNext}
              className="flex items-center gap-2 px-6 py-3 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors"
            >
              {t('form.next')}
              <ArrowRight className="w-5 h-5" />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="flex items-center gap-2 px-6 py-3 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? t('form.loading') : t('form.submit')}
              <CheckCircle className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
