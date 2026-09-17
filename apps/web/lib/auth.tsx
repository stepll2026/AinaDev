"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { clearAuth, getStoredUser, http, setAuth } from "./api";

interface AuthCtx {
  user: any | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string, inviteCode: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const Ctx = createContext<AuthCtx>(null as any);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<any | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const stored = getStoredUser();
    if (stored) setUser(stored);
    setReady(true);
  }, []);

  const login = async (email: string, password: string) => {
    const data = await http.post("/auth/login", { email, password });
    setAuth(data.access_token, data.user);
    setUser(data.user);
  };

  const register = async (email: string, name: string, password: string, inviteCode: string) => {
    const data = await http.post("/auth/register", { email, name, password, invite_code: inviteCode });
    setAuth(data.access_token, data.user);
    setUser(data.user);
  };

  const logout = () => {
    clearAuth();
    setUser(null);
    window.location.href = "/login";
  };

  const refreshUser = async () => {
    try {
      const me = await http.get("/auth/me");
      setUser(me);
      localStorage.setItem("community_user", JSON.stringify(me));
    } catch {
      /* ignore */
    }
  };

  return <Ctx.Provider value={{ user, login, register, logout, refreshUser }}>{ready ? children : null}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
