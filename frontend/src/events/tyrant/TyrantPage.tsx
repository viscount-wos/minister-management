import { Flame } from 'lucide-react';
import EventPlaceholder from '../../shared/EventPlaceholder';

// Frost Dragon Tyrant: the sign-up module lands in the next release (phase 2).
export default function TyrantPage() {
  return <EventPlaceholder ns="tyrant" icon={Flame} status="nextRelease" />;
}
