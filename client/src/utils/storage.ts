/**
 * Non-sensitive preferences persisted with AsyncStorage (localStorage on web).
 * The auth token never goes here: see `src/auth/tokenStorage.ts`.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';

export const STORAGE_KEYS = {
  language: 'shopex.language',
  hasSeenOnboarding: 'shopex.hasSeenOnboarding',
} as const;

export type StorageKey = (typeof STORAGE_KEYS)[keyof typeof STORAGE_KEYS];

/** Reads a value; storage failures (private mode, quota...) behave like a missing value. */
export async function readPreference(key: StorageKey): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(key);
  } catch {
    return null;
  }
}

/** Writes a value; a failure only loses persistence, never the in-memory state. */
export async function writePreference(key: StorageKey, value: string): Promise<void> {
  try {
    await AsyncStorage.setItem(key, value);
  } catch {
    // Preference stays in memory for this session.
  }
}
