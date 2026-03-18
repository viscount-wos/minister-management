import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LogOut, Users, Calendar, HelpCircle, Settings } from 'lucide-react';
import PlayerManagement from '../components/admin/PlayerManagement';
import AssignmentManagement from '../components/admin/AssignmentManagement';
import AdminSettings from '../components/admin/AdminSettings';

export default function AdminDashboard() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<'players' | 'assignments' | 'settings'>('players');
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    // Check if user is authenticated
    const token = localStorage.getItem('adminToken');
    if (!token) {
      navigate('/admin');
      return;
    }
    setIsAuthenticated(true);
  }, [navigate]);

  const handleLogout = () => {
    localStorage.removeItem('adminToken');
    localStorage.removeItem('adminRole');
    navigate('/');
  };

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="min-h-screen bg-dark-bg py-8 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-dark-card rounded-xl border border-theme-border p-6 mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-accent">{t('admin.title')}</h1>
              <p className="text-theme-dim mt-1">{t('admin.managePlayers')}</p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate('/admin/guide')}
                className="flex items-center gap-2 px-4 py-2 bg-accent/20 text-accent rounded-lg hover:bg-accent/30 transition-colors"
              >
                <HelpCircle className="w-5 h-5" />
                {t('adminGuide.linkText')}
              </button>
              <button
                onClick={handleLogout}
                className="flex items-center gap-2 px-4 py-2 bg-danger text-white rounded-lg hover:bg-danger-dark transition-colors"
              >
                <LogOut className="w-5 h-5" />
                {t('admin.logout')}
              </button>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="flex gap-4 mt-6 border-b border-theme-border">
            <button
              onClick={() => setActiveTab('players')}
              className={`flex items-center gap-2 px-4 py-3 font-medium transition-colors border-b-2 ${
                activeTab === 'players'
                  ? 'border-accent text-accent'
                  : 'border-transparent text-theme-dim hover:text-theme-text'
              }`}
            >
              <Users className="w-5 h-5" />
              {t('admin.players')}
            </button>
            <button
              onClick={() => setActiveTab('assignments')}
              className={`flex items-center gap-2 px-4 py-3 font-medium transition-colors border-b-2 ${
                activeTab === 'assignments'
                  ? 'border-accent text-accent'
                  : 'border-transparent text-theme-dim hover:text-theme-text'
              }`}
            >
              <Calendar className="w-5 h-5" />
              {t('admin.assignments')}
            </button>
            <button
              onClick={() => setActiveTab('settings')}
              className={`flex items-center gap-2 px-4 py-3 font-medium transition-colors border-b-2 ${
                activeTab === 'settings'
                  ? 'border-accent text-accent'
                  : 'border-transparent text-theme-dim hover:text-theme-text'
              }`}
            >
              <Settings className="w-5 h-5" />
              {t('admin.settings')}
            </button>
          </div>
        </div>

        {/* Content */}
        {activeTab === 'players' && <PlayerManagement />}
        {activeTab === 'assignments' && <AssignmentManagement />}
        {activeTab === 'settings' && <AdminSettings />}
      </div>
    </div>
  );
}
