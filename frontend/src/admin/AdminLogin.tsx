import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Shield, ArrowLeft, AlertCircle, Clock } from 'lucide-react';
import api, { adminSession } from '../shared/api';
import { errorText } from '../shared/apiErrors';
import { usePageTitle } from '../shared/usePageTitle';
import { findAdminEvent, resolveAdminEvent } from './registry';
import { ADMIN_PATHS } from './paths';

// One login for every event ("Event Management"). /admin?event=tyrant comes
// from the Tyrant page and lands on the Tyrant dashboard; plain /admin lands
// on the last event administered here (or ministry).
export default function AdminLogin() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const expired = params.get('expired') === '1';
  const fromEvent = findAdminEvent(params.get('event'));
  const target = ADMIN_PATHS.dashboard(resolveAdminEvent(params.get('event')).key);

  usePageTitle(t('admin:title'));

  // Already holding a valid token? Go straight to the dashboard.
  useEffect(() => {
    if (!adminSession.token() || expired) return;
    api.admin.me()
      .then(() => navigate(target, { replace: true }))
      .catch(() => adminSession.clear());
    // The 401 handler is not registered here, so a stale token is simply dropped.
  }, [navigate, expired, target]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await api.admin.login(password);
      adminSession.save(res.token, res.role);
      navigate(target);
    } catch (err) {
      setError(errorText(t, err, 'admin:invalidPassword'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[70vh] flex items-start sm:items-center justify-center p-3 sm:p-4">
      <div className="bg-dark-card rounded-2xl p-5 sm:p-8 border border-theme-border max-w-md w-full">
        <button
          onClick={() => navigate(fromEvent ? fromEvent.publicPath : '/')}
          data-testid="admin-login-back"
          className="flex items-center gap-2 min-h-[44px] text-theme-dim hover:text-theme-text mb-4 sm:mb-6"
        >
          <ArrowLeft className="w-5 h-5 rtl:rotate-180" aria-hidden="true" />
          {fromEvent ? t('admin:shell.backTo', { event: t(fromEvent.label) }) : t('common:nav.home')}
        </button>

        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-accent/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <Shield className="w-10 h-10 text-accent" aria-hidden="true" />
          </div>
          <h2 className="text-3xl font-bold text-accent mb-2" data-testid="admin-title">
            {t('admin:title')}
          </h2>
          {fromEvent && (
            <p
              className="inline-flex items-center gap-2 px-3 py-1 mb-3 rounded-full bg-accent/10 border border-accent/40 text-accent text-sm font-semibold"
              data-testid="admin-login-event"
              data-event={fromEvent.key}
            >
              <fromEvent.icon className="w-4 h-4" aria-hidden="true" />
              {t(fromEvent.label)}
            </p>
          )}
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
