/**
 * Device-level app settings. For now: whether the first-launch tutorial was seen, and the
 * "replay tutorial" mode started from the Profile screen.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { readPreference, STORAGE_KEYS, writePreference } from '@/utils/storage';

export interface SettingsContextValue {
  /** False until persisted settings have been read. */
  ready: boolean;
  hasSeenOnboarding: boolean;
  /** True while the user replays the tutorial from Profile. */
  isReplayingOnboarding: boolean;
  /** Marks the tutorial as seen (persisted) and ends a replay. */
  completeOnboarding: () => Promise<void>;
  /** Shows the tutorial again; the router gate switches to it. */
  replayOnboarding: () => void;
}

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [hasSeenOnboarding, setHasSeenOnboarding] = useState(false);
  const [isReplayingOnboarding, setIsReplayingOnboarding] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void readPreference(STORAGE_KEYS.hasSeenOnboarding).then((value) => {
      if (!cancelled) {
        setHasSeenOnboarding(value === 'true');
        setReady(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const completeOnboarding = useCallback(async () => {
    setHasSeenOnboarding(true);
    setIsReplayingOnboarding(false);
    await writePreference(STORAGE_KEYS.hasSeenOnboarding, 'true');
  }, []);

  const replayOnboarding = useCallback(() => {
    setIsReplayingOnboarding(true);
  }, []);

  const value = useMemo<SettingsContextValue>(
    () => ({ ready, hasSeenOnboarding, isReplayingOnboarding, completeOnboarding, replayOnboarding }),
    [ready, hasSeenOnboarding, isReplayingOnboarding, completeOnboarding, replayOnboarding],
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings(): SettingsContextValue {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error('useSettings must be used inside <SettingsProvider>');
  }
  return context;
}
