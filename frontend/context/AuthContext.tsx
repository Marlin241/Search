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
import { clearCompatibilityCache } from "@/lib/compatibilityCache";
import type { CandidateProfileOut, User } from "@/lib/types";

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  /** Profil candidat de l'utilisateur courant, ou `null` s'il n'en a pas
   * encore (compte tout juste créé) - utilisé pour savoir si l'onboarding
   * a déjà été complété (voir lib/onboarding.ts). */
  profile: CandidateProfileOut | null;
  isProfileLoading: boolean;
  refreshProfile: () => Promise<void>;
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
  const [profile, setProfile] = useState<CandidateProfileOut | null>(null);
  const [isProfileLoading, setIsProfileLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    clearCompatibilityCache();
    void clearTokenCookie();
    setToken(null);
    setUser(null);
    setProfile(null);
  }, []);

  /** Charge (ou recharge) le profil candidat pour un token donné. Un compte
   * flambant neuf n'a pas encore de ligne `candidate_profiles` -> 404, ce
   * qui équivaut simplement à "onboarding pas fait", pas à une erreur. */
  const loadProfile = useCallback(async (authToken: string) => {
    setIsProfileLoading(true);
    try {
      const fetched = await api.getCandidateProfile(authToken);
      setProfile(fetched);
    } catch {
      setProfile(null);
    } finally {
      setIsProfileLoading(false);
    }
  }, []);

  const refreshProfile = useCallback(async () => {
    if (!token) return;
    await loadProfile(token);
  }, [token, loadProfile]);

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
      setIsProfileLoading(false);
      return;
    }
    setToken(stored);
    void setTokenCookie(stored);
    api
      .fetchMe(stored)
      .then((me) => {
        setUser(me);
        void loadProfile(stored);
      })
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        void clearTokenCookie();
        setToken(null);
        setIsProfileLoading(false);
      })
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loginFn = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await api.login(email, password);
      localStorage.setItem(TOKEN_KEY, access_token);
      await setTokenCookie(access_token);
      setToken(access_token);
      const me = await api.fetchMe(access_token);
      setUser(me);
      await loadProfile(access_token);
    },
    [loadProfile]
  );

  const registerFn = useCallback(
    async (email: string, password: string, inviteCode: string) => {
      await api.register(email, password, inviteCode);
      await loginFn(email, password);
    },
    [loginFn]
  );

  const value = useMemo(
    () => ({
      user,
      token,
      isLoading,
      profile,
      isProfileLoading,
      refreshProfile,
      login: loginFn,
      register: registerFn,
      logout,
    }),
    [
      user,
      token,
      isLoading,
      profile,
      isProfileLoading,
      refreshProfile,
      loginFn,
      registerFn,
      logout,
    ]
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
