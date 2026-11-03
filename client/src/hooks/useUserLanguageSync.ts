/**
 * Keeps the UI language and the account's `language` field in agreement:
 * - an explicit choice made on this device (saved preference) wins and is pushed to the account;
 * - otherwise the account's language is applied (e.g. first sign-in on a new device).
 * Screens therefore only call `setLanguage()`; the server follows automatically.
 */
import { useEffect, useRef } from 'react';

import { useAuth } from '@/auth';
import { useLanguage } from '@/i18n';

export function useUserLanguageSync(): void {
  const { user, updateUser } = useAuth();
  const { language, setLanguage, hasSavedPreference } = useLanguage();
  const pushing = useRef(false);
  const accountLanguage = user?.language;

  useEffect(() => {
    if (!accountLanguage || accountLanguage === language) {
      return;
    }
    if (!hasSavedPreference) {
      void setLanguage(accountLanguage);
      return;
    }
    if (pushing.current) {
      return;
    }
    pushing.current = true;
    updateUser({ language })
      .catch(() => {
        // Offline: the next profile refresh retries.
      })
      .finally(() => {
        pushing.current = false;
      });
  }, [accountLanguage, language, hasSavedPreference, setLanguage, updateUser]);
}
