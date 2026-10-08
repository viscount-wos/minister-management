import { Navigate, useLocation, useParams } from 'react-router-dom';

// Redirects a pre-v2 URL to its new home, keeping any :params, query string
// and hash, so links people bookmarked or shared keep working.
export default function LegacyRedirect({ to }: { to: string }) {
  const params = useParams();
  const location = useLocation();
  const path = to.replace(/:([A-Za-z]+)/g, (_, name: string) => encodeURIComponent(params[name] ?? ''));
  return <Navigate to={`${path}${location.search}${location.hash}`} replace />;
}
