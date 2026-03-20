'use client';

import { useState, useEffect, useCallback } from 'react';
import * as api from '@/lib/api';
import type { LoginResponse } from '@/lib/types';

interface AuthUser {
  user_id: string;
  email: string;
  is_premium: boolean;
  preferred_language: string;
}

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('user');
    if (stored) {
      try {
        setUser(JSON.parse(stored));
      } catch {
        api.clearTokens();
      }
    }
    setLoading(false);
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
