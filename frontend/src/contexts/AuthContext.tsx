import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import api from '../api/client';
import type { EmployeeProfile } from '../api/types';

interface AuthUser {
  id: number;
  username: string;
  role: 'operator' | 'chief' | 'admin';
  isEmployee?: boolean;
  employeeProfile?: EmployeeProfile | null;
}

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

function parseJwt(token: string): Record<string, unknown> {
  const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
  const json = decodeURIComponent(
    atob(base64)
      .split('')
      .map((c) => '%' + c.charCodeAt(0).toString(16).padStart(2, '0'))
      .join('')
  );
  return JSON.parse(json);
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Подтягивает полный профиль (включая данные сотрудника) с /me/
  const hydrateProfile = useCallback(async (fallback: AuthUser) => {
    try {
      const { data } = await api.get('/api/auth/me/');
      setUser({
        id: data.id,
        username: data.username,
        role: data.role,
        isEmployee: data.is_employee,
        employeeProfile: data.employee_profile ?? null,
      });
    } catch {
      // если /me/ недоступен — оставляем базовые данные из токена
      setUser(fallback);
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      try {
        const payload = parseJwt(token);
        const base: AuthUser = {
          id: payload.user_id as number,
          username: payload.username as string,
          role: payload.role as AuthUser['role'],
          isEmployee: payload.is_employee as boolean | undefined,
        };
        setUser(base);
        hydrateProfile(base).finally(() => setIsLoading(false));
        return;
      } catch {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
      }
    }
    setIsLoading(false);
  }, [hydrateProfile]);

  const login = useCallback(async (username: string, password: string) => {
    const { data } = await api.post('/api/auth/login/', { username, password });
    localStorage.setItem('access_token', data.access);
    localStorage.setItem('refresh_token', data.refresh);
    const payload = parseJwt(data.access);
    const base: AuthUser = {
      id: payload.user_id as number,
      username: payload.username as string,
      role: payload.role as AuthUser['role'],
      isEmployee: payload.is_employee as boolean | undefined,
    };
    setUser(base);
    await hydrateProfile(base);
  }, [hydrateProfile]);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: user !== null, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
