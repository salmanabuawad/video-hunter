/**
 * AppContext — session + brightness + theme + font-size in one place.
 * Real login hits POST /api/auth/login; the backend sets an HttpOnly cookie
 * and returns the user record. We keep a light session copy in localStorage
 * for instant re-render on reload, then verify via /me.
 */
import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { setFontSizeStore, type FontSize } from '../lib/fontSizeStore';
import { api } from '../api';

export type ThemeId = 'ocean' | 'mist';
export type Brightness = 'light' | 'normal' | 'dark' | 'contrast';

export interface Session {
  user_id: number;
  user_name: string;
  user_role: 'admin' | 'user' | 'readonly' | string;
  token: string;
}

interface AppContextValue {
  session: Session | null;
  login: (username: string, password: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  themeId: ThemeId;
  brightness: Brightness;
  fontSize: FontSize;
  setThemeId: (t: ThemeId) => void;
  setBrightness: (b: Brightness) => void;
  setFontSize: (f: FontSize) => void;
}

const AppContext = createContext<AppContextValue | null>(null);

const SESSION_KEY = 'app-session';
const THEME_KEY = 'app-theme';
const BRIGHT_KEY = 'app-brightness';
const FONTSIZE_KEY = 'app-font-size';

function loadSession(): Session | null {
  try {
    return JSON.parse(localStorage.getItem(SESSION_KEY) || 'null');
  } catch {
    return null;
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(loadSession);
  const [themeId, setThemeIdSt] = useState<ThemeId>(
    () => (localStorage.getItem(THEME_KEY) as ThemeId) || 'ocean',
  );
  const [brightness, setBrightnessSt] = useState<Brightness>(
    () => (localStorage.getItem(BRIGHT_KEY) as Brightness) || 'normal',
  );
  const [fontSize, setFontSizeSt] = useState<FontSize>(
    () => (localStorage.getItem(FONTSIZE_KEY) as FontSize) || 'normal',
  );

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', themeId);
    localStorage.setItem(THEME_KEY, themeId);
  }, [themeId]);

  useEffect(() => {
    if (brightness === 'normal') {
      document.documentElement.removeAttribute('data-brightness');
      localStorage.removeItem(BRIGHT_KEY);
    } else {
      document.documentElement.setAttribute('data-brightness', brightness);
      localStorage.setItem(BRIGHT_KEY, brightness);
    }
  }, [brightness]);

  useEffect(() => {
    if (fontSize === 'normal') {
      document.documentElement.removeAttribute('data-font-size');
      localStorage.removeItem(FONTSIZE_KEY);
    } else {
      document.documentElement.setAttribute('data-font-size', fontSize);
      localStorage.setItem(FONTSIZE_KEY, fontSize);
    }
    setFontSizeStore(fontSize);
  }, [fontSize]);

  /* Verify session on mount: if the cookie no longer authenticates, clear
     our local copy so the Login screen shows instead of a dead session. */
  useEffect(() => {
    if (!session) return;
    api
      .me()
      .then((me) => {
        const updated: Session = { ...me, token: session.token };
        localStorage.setItem(SESSION_KEY, JSON.stringify(updated));
        setSession(updated);
      })
      .catch(() => {
        localStorage.removeItem(SESSION_KEY);
        setSession(null);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(
    async (username: string, password: string): Promise<{ success: boolean; error?: string }> => {
      if (!username.trim() || !password)
        return { success: false, error: 'Username and password are required.' };
      try {
        const res = await api.login(username.trim(), password);
        const sess: Session = {
          user_id: res.user.id,
          user_name: res.user.username,
          user_role: res.user.role,
          token: res.token,
        };
        localStorage.setItem(SESSION_KEY, JSON.stringify(sess));
        setSession(sess);
        return { success: true };
      } catch (e: unknown) {
        return { success: false, error: e instanceof Error ? e.message : 'Login failed' };
      }
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      /* ignore — we still clear local state */
    }
    localStorage.removeItem(SESSION_KEY);
    setSession(null);
  }, []);

  return (
    <AppContext.Provider
      value={{
        session,
        login,
        logout,
        themeId,
        setThemeId: setThemeIdSt,
        brightness,
        setBrightness: setBrightnessSt,
        fontSize,
        setFontSize: setFontSizeSt,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be inside AppProvider');
  return ctx;
}
