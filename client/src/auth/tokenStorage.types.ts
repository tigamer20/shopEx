/** Persistence for the session JWT. Platform files implement it (`tokenStorage[.web].ts`). */
export interface TokenStorage {
  getToken(): Promise<string | null>;
  setToken(token: string): Promise<void>;
  clearToken(): Promise<void>;
}

export const TOKEN_STORAGE_KEY = 'shopex.session.token';
