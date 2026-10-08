import { Castle } from 'lucide-react';
import EventPlaceholder from '../../shared/EventPlaceholder';

// SVS Castle: the sign-up module lands in a following release (phase 3).
export default function SvsPage() {
  return <EventPlaceholder ns="svs" icon={Castle} status="nextRelease" />;
}
