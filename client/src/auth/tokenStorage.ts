/**
 * Native (iOS/Android) token storage: Keychain / Android Keystore through expo-secure-store.
 * Metro picks `tokenStorage.web.ts` instead when bundling for the web.
 */
import * as SecureStore from 'expo-secure-store';

import { TOKEN_STORAGE_KEY, type TokenStorage } from './tokenStorage.types';

const options: SecureStore.SecureStoreOptions = {
  keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY,
};

export const tokenStorage: TokenStorage = {
  getToken: () => SecureStore.getItemAsync(TOKEN_STORAGE_KEY, options),
  setToken: (token) => SecureStore.setItemAsync(TOKEN_STORAGE_KEY, token, options),
  clearToken: () => SecureStore.deleteItemAsync(TOKEN_STORAGE_KEY, options),
};
