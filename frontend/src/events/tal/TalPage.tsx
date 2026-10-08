import { Swords } from 'lucide-react';
import EventPlaceholder from '../../shared/EventPlaceholder';

// Tundra Arms League: "coming soon" only; the event still needs planning.
export default function TalPage() {
  return <EventPlaceholder ns="tal" icon={Swords} status="comingSoon" />;
}
