import { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, Edit2, Trash2, X, Save, AlertCircle } from 'lucide-react';
import axios from 'axios';

interface Player {
  id: number;
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
  monday_points: number;
  tuesday_points: number;
  thursday_points: number;
  avatar_image?: string;
  stove_lv?: number;
  stove_lv_content?: string;
}

type SortField = 'game_name' | 'fid' | 'monday_points' | 'tuesday_points' | 'thursday_points';
type SortDirection = 'asc' | 'desc';

export default function PlayerManagement() {
  const { t } = useTranslation();
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState<SortField>('game_name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [editingPlayer, setEditingPlayer] = useState<Player | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<number | null>(null);
  const [showDeleteAllConfirm, setShowDeleteAllConfirm] = useState(false);

  useEffect(() => {
    fetchPlayers();
  }, []);

  const fetchPlayers = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('adminToken');
      const response = await axios.get('/api/admin/players', {
        headers: { Authorization: `Bearer ${token}` },
      });
      setPlayers(response.data);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to fetch players');
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const filteredAndSortedPlayers = useMemo(() => {
    let filtered = players.filter(
      (player) =>
        player.game_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        player.fid.toLowerCase().includes(searchQuery.toLowerCase())
    );

    filtered.sort((a, b) => {
      let aVal = a[sortField];
      let bVal = b[sortField];

      if (typeof aVal === 'string') {
        aVal = aVal.toLowerCase();
        bVal = (bVal as string).toLowerCase();
      }

      if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });

    return filtered;
  }, [players, searchQuery, sortField, sortDirection]);

  const handleDelete = async (playerId: number) => {
    try {
      const token = localStorage.getItem('adminToken');
      await axios.delete(`/api/admin/player/${playerId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setPlayers(players.filter((p) => p.id !== playerId));
      setShowDeleteConfirm(null);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to delete player');
    }
  };

  const handleSaveEdit = async () => {
    if (!editingPlayer) return;

    try {
      const token = localStorage.getItem('adminToken');
      await axios.put(`/api/admin/player/${editingPlayer.id}`, editingPlayer, {
        headers: { Authorization: `Bearer ${token}` },
      });
      await fetchPlayers();
      setEditingPlayer(null);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to update player');
    }
  };

  const handleDeleteAll = async () => {
    try {
      const token = localStorage.getItem('adminToken');
      await axios.delete('/api/admin/players/delete-all', {
        headers: { Authorization: `Bearer ${token}` },
      });
      setPlayers([]);
      setShowDeleteAllConfirm(false);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to delete all players');
    }
  };

  const SortButton = ({ field, label }: { field: SortField; label: string }) => (
    <button
      onClick={() => handleSort(field)}
      className="flex items-center gap-1 hover:text-accent transition-colors"
    >
      {label}
      {sortField === field && (
        <span className="text-xs">{sortDirection === 'asc' ? '↑' : '↓'}</span>
      )}
    </button>
  );

  if (loading) {
    return (
      <div className="bg-dark-card rounded-xl border border-theme-border p-12 text-center">
        <p className="text-theme-dim">{t('form.loading')}</p>
      </div>
    );
  }

  return (
    <div className="bg-dark-card rounded-xl border border-theme-border p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-accent">{t('admin.playerManagement')}</h2>
          <p className="text-theme-dim mt-1">
            {t('admin.totalPlayers')}: {players.length}
          </p>
        </div>
        {players.length > 0 && (
          <button
            onClick={() => setShowDeleteAllConfirm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-danger text-white rounded-lg hover:bg-danger-dark font-medium transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            Remove All Players
          </button>
        )}
      </div>

      {/* Search */}
      <div className="mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-theme-dim w-5 h-5" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('admin.search')}
            className="w-full pl-10 pr-4 py-3 bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder-theme-dim focus:ring-2 focus:ring-accent focus:border-accent"
          />
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="mb-6 p-4 bg-danger/10 border border-danger/30 rounded-lg flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-danger" />
          <p className="text-danger">{error}</p>
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b-2 border-theme-border">
              <th className="text-left p-3 font-semibold text-theme-dim">
                <SortButton field="game_name" label="Game Name" />
              </th>
              <th className="text-left p-3 font-semibold text-theme-dim">
                <SortButton field="fid" label="FID" />
              </th>
              <th className="text-center p-3 font-semibold text-theme-dim">
                <SortButton field="monday_points" label="Monday" />
              </th>
              <th className="text-center p-3 font-semibold text-theme-dim">
                <SortButton field="tuesday_points" label="Tuesday" />
              </th>
              <th className="text-center p-3 font-semibold text-theme-dim">
                <SortButton field="thursday_points" label="Thursday" />
              </th>
              <th className="text-center p-3 font-semibold text-theme-dim">Time Slots</th>
              <th className="text-center p-3 font-semibold text-theme-dim">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredAndSortedPlayers.map((player) => (
              <tr key={player.id} className="border-b border-theme-border/50 hover:bg-dark-card-hover">
                <td className="p-3 text-theme-text">
                  <div className="flex items-center gap-2">
                    {player.avatar_image ? (
                      <img src={player.avatar_image} alt="" className="w-6 h-6 rounded-full flex-shrink-0" />
                    ) : null}
                    {player.game_name}
                  </div>
                </td>
                <td className="p-3 text-sm text-theme-dim">{player.fid}</td>
                <td className="p-3 text-center font-medium text-accent">
                  {player.monday_points.toLocaleString()}
                </td>
                <td className="p-3 text-center font-medium text-success">
                  {player.tuesday_points.toLocaleString()}
                </td>
                <td className="p-3 text-center font-medium text-accent-light">
                  {player.thursday_points.toLocaleString()}
                </td>
                <td className="p-3 text-center text-sm text-theme-dim">
                  {player.time_slots ? player.time_slots.length : 0} selected
                </td>
                <td className="p-3">
                  <div className="flex items-center justify-center gap-2">
                    <button
                      onClick={() => setEditingPlayer(player)}
                      className="p-2 text-accent hover:bg-accent/10 rounded-lg transition-colors"
                      title={t('admin.edit')}
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setShowDeleteConfirm(player.id)}
                      className="p-2 text-danger hover:bg-danger/10 rounded-lg transition-colors"
                      title={t('admin.delete')}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filteredAndSortedPlayers.length === 0 && (
          <div className="text-center py-12 text-theme-dim">
            No players found
          </div>
        )}
      </div>

      {/* Edit Modal */}
      {editingPlayer && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-dark-card rounded-xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto border border-theme-border">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-2xl font-bold text-accent">{t('admin.edit')} Player</h3>
              <button
                onClick={() => setEditingPlayer(null)}
                className="text-theme-dim hover:text-theme-text"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-theme-text mb-2">Game Name</label>
                <input
                  type="text"
                  value={editingPlayer.game_name}
                  onChange={(e) =>
                    setEditingPlayer({ ...editingPlayer, game_name: e.target.value })
                  }
                  className="w-full px-4 py-2 bg-dark-input border border-theme-border rounded-lg text-theme-text focus:ring-2 focus:ring-accent focus:border-accent"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                {[
                  { key: 'construction_speedups_days', label: 'Construction (days)' },
                  { key: 'research_speedups_days', label: 'Research (days)' },
                  { key: 'troop_training_speedups_days', label: 'Troop (days)' },
                  { key: 'general_speedups_days', label: 'General (days)' },
                  { key: 'fire_crystals', label: 'Fire Crystals' },
                  { key: 'refined_fire_crystals', label: 'Refined Crystals' },
                  { key: 'fire_crystal_shards', label: 'Crystal Shards' },
                ].map(({ key, label }) => (
                  <div key={key}>
                    <label className="block text-sm font-medium text-theme-text mb-2">{label}</label>
                    <input
                      type="number"
                      value={(editingPlayer as any)[key]}
                      onChange={(e) =>
                        setEditingPlayer({
                          ...editingPlayer,
                          [key]: parseFloat(e.target.value) || 0,
                        })
                      }
                      min="0"
                      step={key.includes('speedups') ? '0.1' : '1'}
                      className="w-full px-4 py-2 bg-dark-input border border-theme-border rounded-lg text-theme-text focus:ring-2 focus:ring-accent focus:border-accent"
                    />
                  </div>
                ))}
              </div>

              {/* Time Preferences */}
              <div className="mt-6">
                <label className="block text-sm font-medium text-theme-text mb-2">
                  Time Preferences (UTC)
                </label>
                <div className="grid grid-cols-6 gap-2">
                  {Array.from({ length: 24 }, (_, i) => `${i.toString().padStart(2, '0')}:00`).map((time) => (
                    <button
                      key={time}
                      type="button"
                      onClick={() => {
                        const slots = editingPlayer.time_slots || [];
                        setEditingPlayer({
                          ...editingPlayer,
                          time_slots: slots.includes(time)
                            ? slots.filter((t: string) => t !== time)
                            : [...slots, time],
                        });
                      }}
                      className={`p-2 rounded border text-sm font-medium transition-all ${
                        (editingPlayer.time_slots || []).includes(time)
                          ? 'bg-accent border-accent text-dark-bg'
                          : 'bg-dark-input border-theme-border text-theme-text hover:border-accent'
                      }`}
                    >
                      {time}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-theme-dim mt-2">
                  Selected: {(editingPlayer.time_slots || []).length} time slots
                </p>
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  onClick={handleSaveEdit}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium"
                >
                  <Save className="w-5 h-5" />
                  {t('common.save')}
                </button>
                <button
                  onClick={() => setEditingPlayer(null)}
                  className="flex-1 px-4 py-3 bg-dark-bg text-theme-text rounded-lg hover:bg-dark-card-hover font-medium border border-theme-border"
                >
                  {t('common.cancel')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-dark-card rounded-xl p-6 max-w-md w-full border border-theme-border">
            <h3 className="text-xl font-bold text-theme-text mb-4">{t('admin.confirmDelete')}</h3>
            <div className="flex gap-3">
              <button
                onClick={() => handleDelete(showDeleteConfirm)}
                className="flex-1 px-4 py-3 bg-danger text-white rounded-lg hover:bg-danger-dark font-medium"
              >
                {t('common.yes')}
              </button>
              <button
                onClick={() => setShowDeleteConfirm(null)}
                className="flex-1 px-4 py-3 bg-dark-bg text-theme-text rounded-lg hover:bg-dark-card-hover font-medium border border-theme-border"
              >
                {t('common.no')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete All Confirmation Modal */}
      {showDeleteAllConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-dark-card rounded-xl p-6 max-w-md w-full border border-theme-border">
            <div className="flex items-center gap-3 mb-4">
              <AlertCircle className="w-8 h-8 text-danger" />
              <h3 className="text-xl font-bold text-theme-text">Remove All Players?</h3>
            </div>
            <p className="text-theme-dim mb-6">
              This will permanently delete all {players.length} players and their assignments. This action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={handleDeleteAll}
                className="flex-1 px-4 py-3 bg-danger text-white rounded-lg hover:bg-danger-dark font-medium"
              >
                Yes, Delete All
              </button>
              <button
                onClick={() => setShowDeleteAllConfirm(false)}
                className="flex-1 px-4 py-3 bg-dark-bg text-theme-text rounded-lg hover:bg-dark-card-hover font-medium border border-theme-border"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
