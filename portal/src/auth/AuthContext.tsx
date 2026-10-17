import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  api,
  clearPortalSession,
  fetchHealth,
  getAccessToken,
  getStoredSessionUser,
  setAccessToken,
  setStoredSessionUser,
  type LoginResponse,
  type SessionUser,
} from "../api/client";

type AuthState = {
  loading: boolean;
  authEnabled: boolean;
  user: SessionUser | null;
  login: (email: string, password: string) => Promise<SessionUser>;
  logout: () => void;
  refresh: () => Promise<void>;
  applyLoginResponse: (result: LoginResponse) => SessionUser;
};

const AuthContext = createContext<AuthState | null>(null);

function toSessionUser(result: LoginResponse): SessionUser {
  return {
    email: result.email,
    full_name: result.full_name,
    role: result.role,
    institution_id: result.institution_id,
    institution_name: result.institution_name,
    agent_dealer_id: result.agent_dealer_id,
    must_change_password: result.must_change_password,
    permissions: result.permissions || [],
  };
}

async function readAuthEnabledFallback(): Promise<boolean> {
  try {
    const health = await fetchHealth();
    return Boolean(health?.auth_enabled);
  } catch {
    return true;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [authEnabled, setAuthEnabled] = useState(false);
  const [user, setUser] = useState<SessionUser | null>(null);

  const applyLoginResponse = useCallback((result: LoginResponse) => {
    setAccessToken(result.access_token);
    const session = toSessionUser(result);
    setStoredSessionUser(session);
    setUser(session);
    setAuthEnabled(true);
    return session;
  }, []);

  const refresh = useCallback(async () => {
    try {
      const ctx = await api.getAuthContext();
      setAuthEnabled(Boolean(ctx.auth_enabled));
      if (!ctx.auth_enabled) {
        setUser(null);
        return;
      }
      if (!ctx.authenticated) {
        setUser(null);
        return;
      }
      const stored = getStoredSessionUser();
      const session: SessionUser = {
        email: ctx.email || stored?.email || "",
        full_name: ctx.full_name || stored?.full_name || ctx.email || "User",
        role: ctx.role || stored?.role || "read_only",
        institution_id: ctx.institution_id,
        institution_name: ctx.institution_name ?? stored?.institution_name,
        agent_dealer_id: ctx.agent_dealer_id ?? stored?.agent_dealer_id,
        must_change_password: Boolean(ctx.must_change_password ?? stored?.must_change_password),
        permissions: ctx.permissions?.length ? ctx.permissions : stored?.permissions || [],
      };
      setStoredSessionUser(session);
      setUser(session);
    } catch {
      // /ops/auth/me returns 401 when auth is on and there is no valid session.
      const enabled = await readAuthEnabledFallback();
      setAuthEnabled(enabled);
      if (enabled && getAccessToken()) {
        // Stale/invalid token — clear it so the login page can be used again.
        clearPortalSession();
      }
      setUser(null);
    }
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      try {
        if (active) await refresh();
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [refresh]);

  const login = useCallback(
    async (email: string, password: string) => {
      const result = await api.login(email, password);
      return applyLoginResponse(result);
    },
    [applyLoginResponse],
  );

  const logout = useCallback(() => {
    clearPortalSession();
    setUser(null);
    setAuthEnabled(true);
  }, []);

  const value = useMemo(
    () => ({
      loading,
      authEnabled,
      user,
      login,
      logout,
      refresh,
      applyLoginResponse,
    }),
    [loading, authEnabled, user, login, logout, refresh, applyLoginResponse],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
