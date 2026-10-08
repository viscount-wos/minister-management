import { Navigate, useLocation, useParams } from 'react-router-dom';

// Redirects an older URL to its new home, keeping any :params, query string
// and hash, so links people bookmarked or shared keep working. A target with
// its own query (/admin?event=ministry) is merged with the incoming one.
export default function LegacyRedirect({ to }: { to: string }) {
  const params = useParams();
  const location = useLocation();
  const filled = to.replace(/:([A-Za-z]+)/g, (_, name: string) => encodeURIComponent(params[name] ?? ''));
  const [path, ownQuery = ''] = filled.split('?');
  const query = new URLSearchParams(ownQuery);
  new URLSearchParams(location.search).forEach((v, k) => query.set(k, v));
  const qs = query.toString();
  return <Navigate to={`${path}${qs ? `?${qs}` : ''}${location.hash}`} replace />;
}
