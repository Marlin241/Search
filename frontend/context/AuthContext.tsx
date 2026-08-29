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
  register: (
    email: string,
    password: string,
    inviteCode: string
  ) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

const TOKEN_KEY = "search_app_token";

/* HttpOnly cookie mirror of the token, set server-side by the /api/session
 * route handler, so proxy.ts can do a cheap server-side "is anyone logged
 * in" check before the page ever renders. The backend still only trusts the
 * Bearer header (from localStorage), never this cookie — actual validation
 * happens client-side via fetchMe, same as before. */
async function setTokenCookie(token: string) {
  await fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
}

async function clearTokenCookie() {
  await fetch("/api/session", { method: "DELETE" });
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    void clearTokenCookie();
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
    void setTokenCookie(stored);
    api
      .fetchMe(stored)
      .then(setUser)
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        void clearTokenCookie();
        setToken(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const loginFn = useCallback(async (email: string, password: string) => {
    const { access_token } = await api.login(email, password);
    localStorage.setItem(TOKEN_KEY, access_token);
    await setTokenCookie(access_token);
    setToken(access_token);
    const me = await api.fetchMe(access_token);
    setUser(me);
  }, []);

  const registerFn = useCallback(
    async (email: string, password: string, inviteCode: string) => {
      await api.register(email, password, inviteCode);
      await loginFn(email, password);
    },
    [loginFn]
  );

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
