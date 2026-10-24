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

type EngineHealth = {
  online: boolean | null;
  status: string | null;
  checkedAt: number | null;
};

type AuthState = {
  loading: boolean;
  authEnabled: boolean;
  user: SessionUser | null;
  engineHealth: EngineHealth;
  refreshHealth: () => Promise<EngineHealth>;
  login: (email: string, password: string) => Promise<SessionUser>;
  logout: () => void;
  refresh: () => Promise<void>;
  applyLoginResponse: (result: LoginResponse) => SessionUser;
};

const AuthContext = createContext<AuthState | null>(null);

const INITIAL_HEALTH: EngineHealth = { online: null, status: null, checkedAt: null };

function healthFromPayload(data: { status?: string } | null | undefined): EngineHealth {
  const status = data?.status ?? null;
  const online = status === "ok" || status === "degraded";
  return { online, status, checkedAt: Date.now() };
}

function toSessionUser(result: LoginResponse, extras?: Partial<SessionUser>): SessionUser {
  return {
    email: result.email,
    full_name: result.full_name,
    role: result.role,
    institution_id: result.institution_id,
    institution_name: result.institution_name,
    agent_dealer_id: result.agent_dealer_id,
    must_change_password: result.must_change_password,
    permissions: result.permissions || [],
    mfa_enroll_required: Boolean(result.mfa_enroll_required),
    mfa_enabled: Boolean(result.mfa_enabled),
    mfa_method: result.mfa_method ?? null,
    ...extras,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [authEnabled, setAuthEnabled] = useState(false);
  const [user, setUser] = useState<SessionUser | null>(null);
  const [engineHealth, setEngineHealth] = useState<EngineHealth>(INITIAL_HEALTH);

  const refreshHealth = useCallback(async () => {
    try {
      const data = await fetchHealth();
      const next = healthFromPayload(data);
      setEngineHealth(next);
      if (typeof data?.auth_enabled === "boolean") {
        setAuthEnabled(Boolean(data.auth_enabled));
      }
      return next;
    } catch {
      const next: EngineHealth = { online: false, status: "unreachable", checkedAt: Date.now() };
      setEngineHealth(next);
      return next;
    }
  }, []);

  const applyLoginResponse = useCallback(
    (result: LoginResponse) => {
      setAccessToken(result.access_token);
      const session = toSessionUser(result);
      setStoredSessionUser(session);
      setUser(session);
      setAuthEnabled(true);
      if (result.access_token) {
        void refreshHealth();
      }
      return session;
    },
    [refreshHealth],
  );

  const refresh = useCallback(async () => {
    try {
      const [ctx] = await Promise.all([api.getAuthContext(), refreshHealth()]);
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
        user_id: ctx.user_id ?? stored?.user_id,
        must_change_password: Boolean(ctx.must_change_password ?? stored?.must_change_password),
        permissions: ctx.permissions?.length ? ctx.permissions : stored?.permissions || [],
        mfa_enroll_required: Boolean(ctx.mfa_enroll_required ?? stored?.mfa_enroll_required),
        mfa_enabled: Boolean(ctx.mfa_enabled ?? stored?.mfa_enabled),
        mfa_method: (ctx.mfa_method ?? stored?.mfa_method ?? null) as SessionUser["mfa_method"],
        job_title: ctx.job_title ?? stored?.job_title ?? null,
        department: ctx.department ?? stored?.department ?? null,
        employee_number: ctx.employee_number ?? stored?.employee_number ?? null,
        phone: ctx.phone ?? stored?.phone ?? null,
        office: ctx.office ?? stored?.office ?? null,
      };
      setStoredSessionUser(session);
      setUser(session);
    } catch {
      // /ops/auth/me returns 401 when auth is on and there is no valid session.
      const health = await refreshHealth();
      if (health.status === "unreachable") {
        setAuthEnabled(true);
      }
      if (getAccessToken()) {
        clearPortalSession();
      }
      setUser(null);
    }
  }, [refreshHealth]);

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
      engineHealth,
      refreshHealth,
      login,
      logout,
      refresh,
      applyLoginResponse,
    }),
    [loading, authEnabled, user, engineHealth, refreshHealth, login, logout, refresh, applyLoginResponse],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
