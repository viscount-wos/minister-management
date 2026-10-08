import { createContext, useContext, useState, ReactNode } from 'react';
import { getSavedTimezone } from './timezone';

// One display timezone for the whole app, so the header selector and the
// selectors on the ministry forms/schedules always agree. Starts from the saved
// preference (localStorage 'preferred_timezone', as before); TimezoneSelector
// persists the user's choice. Pages may still set it programmatically (e.g. the
// update page adopting the player's saved timezone) without persisting it.

interface TimezoneContextValue {
  timezone: string;
  setTimezone: (tz: string) => void;
}

const TimezoneContext = createContext<TimezoneContextValue | null>(null);

export function TimezoneProvider({ children }: { children: ReactNode }) {
  const [timezone, setTimezone] = useState(getSavedTimezone);
  return (
    <TimezoneContext.Provider value={{ timezone, setTimezone }}>
      {children}
    </TimezoneContext.Provider>
  );
}

export function useTimezone(): TimezoneContextValue {
  const ctx = useContext(TimezoneContext);
  if (!ctx) throw new Error('useTimezone must be used inside <TimezoneProvider>');
  return ctx;
}
