"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { login as apiLogin, register as apiRegister, fetchMe, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const TOKEN_STORAGE_KEY = "ats_diagnostic_token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (!stored) {
      setIsLoading(false);
      return;
    }
    fetchMe(stored)
      .then((fetchedUser) => {
        setToken(stored);
        setUser(fetchedUser);
      })
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) {
          localStorage.removeItem(TOKEN_STORAGE_KEY);
        }
      })
      .finally(() => setIsLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const { access_token } = await apiLogin(email, password);
    const loggedInUser = await fetchMe(access_token);
    localStorage.setItem(TOKEN_STORAGE_KEY, access_token);
    setToken(access_token);
    setUser(loggedInUser);
  }

  async function register(email: string, password: string) {
    await apiRegister(email, password);
    await login(email, password);
  }

  function logout() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}
