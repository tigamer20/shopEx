/**
 * Web token storage: localStorage (ARCHITECTURE §2). Accessors can throw in private mode or
 * when storage is blocked; the session then simply lasts until the tab is closed.
 */
import { TOKEN_STORAGE_KEY, type TokenStorage } from './tokenStorage.types';

function storage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

export const tokenStorage: TokenStorage = {
  async getToken() {
    try {
      return storage()?.getItem(TOKEN_STORAGE_KEY) ?? null;
    } catch {
      return null;
    }
  },
  async setToken(token) {
    try {
      storage()?.setItem(TOKEN_STORAGE_KEY, token);
    } catch {
      // Not persisted: the in-memory session still works.
    }
  },
  async clearToken() {
    try {
      storage()?.removeItem(TOKEN_STORAGE_KEY);
    } catch {
      // Nothing to clear.
    }
  },
};
