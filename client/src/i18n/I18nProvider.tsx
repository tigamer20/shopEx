import { getLocales } from 'expo-localization';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import type { Language } from '@/api/types';
import { readPreference, STORAGE_KEYS, writePreference } from '@/utils/storage';

import { DEFAULT_LANGUAGE, toLanguage, translate } from './translate';
import type { Translate } from './types';

interface I18nContextValue {
  language: Language;
  setLanguage: (language: Language) => Promise<void>;
  t: Translate;
  /** False until the saved preference has been read. */
  ready: boolean;
  /** True once the user picked a language explicitly (saved preference exists). */
  hasSavedPreference: boolean;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function deviceLanguage(): Language | null {
  try {
    return toLanguage(getLocales()[0]?.languageCode);
  } catch {
    return null;
  }
}

/** Initial language = saved preference → device locale → French. */
export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => deviceLanguage() ?? DEFAULT_LANGUAGE);
  const [hasSavedPreference, setHasSavedPreference] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void readPreference(STORAGE_KEYS.language).then((saved) => {
      if (cancelled) {
        return;
      }
      const savedLanguage = toLanguage(saved);
      if (savedLanguage) {
        setLanguageState(savedLanguage);
        setHasSavedPreference(true);
      }
      setReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const setLanguage = useCallback(async (next: Language) => {
    setLanguageState(next);
    setHasSavedPreference(true);
    await writePreference(STORAGE_KEYS.language, next);
  }, []);

  const t = useCallback<Translate>((key, params) => translate(language, key, params), [language]);

  const value = useMemo<I18nContextValue>(
    () => ({ language, setLanguage, t, ready, hasSavedPreference }),
    [language, setLanguage, t, ready, hasSavedPreference],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

function useI18nContext(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('i18n hooks must be used inside <I18nProvider>');
  }
  return context;
}

/** Returns `t(key, params?)` for the current language. */
export function useT(): Translate {
  return useI18nContext().t;
}

/** Current language and its setter (persisted). */
export function useLanguage(): Pick<I18nContextValue, 'language' | 'setLanguage' | 'hasSavedPreference'> {
  const { language, setLanguage, hasSavedPreference } = useI18nContext();
  return { language, setLanguage, hasSavedPreference };
}

/** Readiness flag for the root layout (waits for the saved language before first paint). */
export function useI18nReady(): boolean {
  return useI18nContext().ready;
}
