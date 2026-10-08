import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Shield, ArrowLeft, AlertCircle, Clock } from 'lucide-react';
import api, { adminSession } from '../../../shared/api';
import { errorText } from '../../../shared/apiErrors';
import { MINISTRY_PATHS } from '../paths';

export default function AdminLogin() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const expired = params.get('expired') === '1';

  // Already holding a valid token? Go straight to the dashboard.
  useEffect(() => {
    if (!adminSession.token() || expired) return;
    api.admin.me()
      .then(() => navigate('/admin/dashboard', { replace: true }))
      .catch(() => adminSession.clear());
    // The 401 handler is not registered here, so a stale token is simply dropped.
  }, [navigate, expired]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await api.admin.login(password);
      adminSession.save(res.token, res.role);
      navigate('/admin/dashboard');
    } catch (err) {
      setError(errorText(t, err, 'admin:invalidPassword'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="bg-dark-card rounded-2xl p-8 border border-theme-border max-w-md w-full">
        <button
          onClick={() => navigate(MINISTRY_PATHS.home)}
          className="flex items-center gap-2 text-theme-dim hover:text-theme-text mb-6"
        >
          <ArrowLeft className="w-5 h-5 rtl:rotate-180" aria-hidden="true" />
          {t('ministry:update.backHome')}
        </button>

        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-accent/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <Shield className="w-10 h-10 text-accent" aria-hidden="true" />
          </div>
          <h2 className="text-3xl font-bold text-accent mb-2">{t('admin:title')}</h2>
          <p className="text-theme-dim">{t('admin:enterPassword')}</p>
        </div>

        {expired && !error && (
          <div
            className="mb-4 p-4 bg-warning/10 border border-warning/30 rounded-lg flex items-center gap-3"
            role="status"
            data-testid="session-expired"
          >
            <Clock className="w-5 h-5 text-warning shrink-0" aria-hidden="true" />
            <p className="text-warning">{t('admin:sessionExpired')}</p>
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label htmlFor="admin-password" className="block text-sm font-medium text-theme-text mb-2">
              {t('admin:password')}
            </label>
            <input
              id="admin-password"
              data-testid="admin-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 bg-dark-input border border-theme-border rounded-lg text-theme-text focus:ring-2 focus:ring-accent focus:border-accent"
              required
            />
          </div>

          {error && (
            <div
              className="p-4 bg-danger/10 border border-danger/30 rounded-lg flex items-center gap-3"
              role="alert"
              data-testid="login-error"
            >
              <AlertCircle className="w-5 h-5 text-danger shrink-0" aria-hidden="true" />
              <p className="text-danger">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            data-testid="admin-login"
            className="w-full px-6 py-3 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors disabled:opacity-50"
          >
            {loading ? t('ministry:form.loading') : t('admin:login')}
          </button>
        </form>
      </div>
    </div>
  );
}
