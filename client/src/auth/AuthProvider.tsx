import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import {
  deleteMe,
  fetchMe,
  isApiError,
  loginUser,
  registerUser,
  setApiToken,
  setUnauthorizedHandler,
  updateMe,
} from '@/api/client';
import type { LoginRequest, RegisterRequest, TokenResponse, User, UserUpdate } from '@/api/types';

import { tokenStorage } from './tokenStorage';

export type AuthStatus = 'loading' | 'signedIn' | 'signedOut';

interface AuthState {
  status: AuthStatus;
  token: string | null;
  /** Null while signed out, and briefly when the profile could not be loaded (offline start). */
  user: User | null;
}

export interface AuthContextValue extends AuthState {
  login: (credentials: LoginRequest) => Promise<User>;
  register: (input: RegisterRequest) => Promise<User>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<User | null>;
  updateUser: (patch: UserUpdate) => Promise<User>;
  /** Deletes the account (and its lists) server-side, then signs out. */
  deleteAccount: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const SIGNED_OUT: AuthState = { status: 'signedOut', token: null, user: null };
/** Startup should not hang on a slow network: the profile can be refreshed later. */
const RESTORE_TIMEOUT_MS = 8_000;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: 'loading', token: null, user: null });
  // Mirrors state.token for callbacks that must not go stale.
  const tokenRef = useRef<string | null>(null);

  const applyToken = useCallback((token: string | null) => {
    tokenRef.current = token;
    setApiToken(token);
  }, []);

  const logout = useCallback(async () => {
    applyToken(null);
    setState(SIGNED_OUT);
    try {
      await tokenStorage.clearToken();
    } catch {
      // Nothing persisted, nothing to clear.
    }
  }, [applyToken]);

  // An authenticated request answered 401 (expired or revoked token): end the session.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      void logout();
    });
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  // Restore the session saved on this device.
  useEffect(() => {
    let cancelled = false;

    async function restore(): Promise<void> {
      let token: string | null = null;
      try {
        token = await tokenStorage.getToken();
      } catch {
        token = null;
      }
      if (cancelled) {
        return;
      }
      if (!token) {
        setState(SIGNED_OUT);
        return;
      }

      applyToken(token);
      let user: User | null = null;
      try {
        user = await fetchMe({ timeoutMs: RESTORE_TIMEOUT_MS });
      } catch (error) {
        // A 401 already signed the user out through the unauthorized handler.
        if (isApiError(error) && error.status === 401) {
          return;
        }
        // Offline or server down: keep the session; screens can call refreshUser().
      }
      if (!cancelled) {
        setState({ status: 'signedIn', token, user });
      }
    }

    void restore();
    return () => {
      cancelled = true;
    };
  }, [applyToken]);

  const startSession = useCallback(
    async ({ access_token, user }: TokenResponse): Promise<User> => {
      applyToken(access_token);
      setState({ status: 'signedIn', token: access_token, user });
      try {
        await tokenStorage.setToken(access_token);
      } catch {
        // Not persisted: the session lasts until the app is closed.
      }
      return user;
    },
    [applyToken],
  );

  const login = useCallback(
    async (credentials: LoginRequest) => startSession(await loginUser(credentials)),
    [startSession],
  );

  const register = useCallback(
    async (input: RegisterRequest) => startSession(await registerUser(input)),
    [startSession],
  );

  /** Stores a fresh profile, unless the session changed while the request was in flight. */
  const applyUser = useCallback((token: string, user: User) => {
    setState((previous) => (previous.token === token ? { ...previous, user } : previous));
  }, []);

  const refreshUser = useCallback(async (): Promise<User | null> => {
    const token = tokenRef.current;
    if (!token) {
      return null;
    }
    const user = await fetchMe();
    applyUser(token, user);
    return user;
  }, [applyUser]);

  const updateUser = useCallback(
    async (patch: UserUpdate): Promise<User> => {
      const token = tokenRef.current;
      const user = await updateMe(patch);
      if (token) {
        applyUser(token, user);
      }
      return user;
    },
    [applyUser],
  );

  const deleteAccount = useCallback(async () => {
    await deleteMe();
    await logout();
  }, [logout]);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, register, logout, refreshUser, updateUser, deleteAccount }),
    [state, login, register, logout, refreshUser, updateUser, deleteAccount],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside <AuthProvider>');
  }
  return context;
}
