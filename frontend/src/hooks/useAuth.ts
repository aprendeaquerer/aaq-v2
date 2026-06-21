'use client';

import { useState, useCallback, useEffect } from 'react';
import * as api from '@/lib/api';

interface AuthUser {
  user_id: string;
  email: string;
  is_premium: boolean;
  preferred_language: string;
}

function getStoredUser(): AuthUser | null {
  if (typeof window === 'undefined') return null;

  const stored = localStorage.getItem('user');
  if (!stored) return null;

  try {
    return JSON.parse(stored) as AuthUser;
  } catch {
    api.clearTokens();
    return null;
  }
}

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(() => getStoredUser());
  const loading = false;

  useEffect(() => {
    const syncStoredUser = () => setUser(getStoredUser());
    window.addEventListener('storage', syncStoredUser);
    window.addEventListener('aaq-auth-cleared', syncStoredUser);
    return () => {
      window.removeEventListener('storage', syncStoredUser);
      window.removeEventListener('aaq-auth-cleared', syncStoredUser);
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await api.login(email, password);
    const authUser: AuthUser = {
      user_id: data.user_id,
      email: data.email,
      is_premium: data.is_premium,
      preferred_language: data.preferred_language,
    };
    setUser(authUser);
    return data;
  }, []);

  const register = useCallback(async (email: string, password: string, language: string = 'es') => {
    await api.register(email, password, language);
  }, []);

  const logout = useCallback(() => {
    api.clearTokens();
    setUser(null);
  }, []);

  return { user, loading, login, register, logout, isAuthenticated: !!user };
}
