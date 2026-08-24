"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import * as api from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

const TOKEN_KEY = "search_app_token";
/* Non-httpOnly cookie mirror of the token, so middleware.ts can do a cheap
 * server-side "is anyone logged in" check before the page ever renders
 * (fixes v2's client-only guard, which always flashed a spinner). The
 * backend still only trusts the Bearer header, never this cookie — actual
 * validation happens client-side via fetchMe, same as before. */
const TOKEN_COOKIE = "search_app_token";
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24; // 24h, matches backend JWT default expiry

function setTokenCookie(token: string) {
  document.cookie = `${TOKEN_COOKIE}=${token}; path=/; max-age=${COOKIE_MAX_AGE_SECONDS}; samesite=lax`;
}

function clearTokenCookie() {
  document.cookie = `${TOKEN_COOKIE}=; path=/; max-age=0; samesite=lax`;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    clearTokenCookie();
    setToken(null);
    setUser(null);
  }, []);

  /* Global 401 handler: any API call that comes back unauthorized forces
   * a logout instead of leaving the page silently broken. */
  useEffect(() => {
    api.setUnauthorizedHandler(logout);
    return () => api.setUnauthorizedHandler(null);
  }, [logout]);

  /* Persist & restore token */
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (!stored) {
      setIsLoading(false);
      return;
    }
    setToken(stored);
    setTokenCookie(stored);
    api
      .fetchMe(stored)
      .then(setUser)
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        clearTokenCookie();
        setToken(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const loginFn = useCallback(async (email: string, password: string) => {
    const { access_token } = await api.login(email, password);
    localStorage.setItem(TOKEN_KEY, access_token);
    setTokenCookie(access_token);
    setToken(access_token);
    const me = await api.fetchMe(access_token);
    setUser(me);
  }, []);

  const registerFn = useCallback(async (email: string, password: string) => {
    await api.register(email, password);
    await loginFn(email, password);
  }, [loginFn]);

  const value = useMemo(
    () => ({ user, token, isLoading, login: loginFn, register: registerFn, logout }),
    [user, token, isLoading, loginFn, registerFn, logout]
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
