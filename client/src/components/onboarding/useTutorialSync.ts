/**
 * The first-launch tutorial runs before sign-in, so the account cannot be updated at that time.
 * Once a session exists, this records `tutorial_completed` on the account when the tutorial was
 * already seen on this device (once per session; failures are retried on the next profile load).
 */
import { useEffect, useRef } from 'react';

import { useAuth } from '@/auth';
import { useSettings } from '@/settings/SettingsProvider';

export function useTutorialSync(): void {
  const { user, updateUser } = useAuth();
  const { hasSeenOnboarding, isReplayingOnboarding } = useSettings();
  const pending = useRef(false);
  const needsSync = Boolean(user && !user.tutorial_completed && hasSeenOnboarding && !isReplayingOnboarding);

  useEffect(() => {
    if (!needsSync || pending.current) {
      return;
    }
    pending.current = true;
    updateUser({ tutorial_completed: true })
      .catch(() => undefined)
      .finally(() => {
        pending.current = false;
      });
  }, [needsSync, updateUser]);
}
