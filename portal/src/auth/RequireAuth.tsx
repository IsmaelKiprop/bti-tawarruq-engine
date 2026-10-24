import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { AppLayout } from "../components/AppLayout";
import { LoadingPanel } from "../components/PageShell";

export function OptionalAppLayout() {
  const { loading, authEnabled, user } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="page-shell">
        <LoadingPanel rows={3} />
      </div>
    );
  }

  if (user?.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }

  if (!authEnabled || user) {
    return <AppLayout />;
  }

  return <Outlet />;
}

export function RequireRole({ roles }: { roles: string[] }) {
  const { loading, authEnabled, user } = useAuth();

  if (loading) {
    return (
      <div className="page-shell">
        <LoadingPanel rows={3} />
      </div>
    );
  }

  if (!authEnabled) {
    return <Outlet />;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (roles.includes(user.role)) {
    return <Outlet />;
  }

  return (
    <div className="page-shell">
      <div className="panel">
        <h2>Access denied</h2>
        <p className="muted">Your role cannot open this page.</p>
      </div>
    </div>
  );
}

export function RequireAnyPermission({ permissions }: { permissions: string[] }) {
  const { loading, authEnabled, user } = useAuth();

  if (loading) {
    return (
      <div className="page-shell">
        <LoadingPanel rows={3} />
      </div>
    );
  }

  if (!authEnabled) {
    return <Outlet />;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (permissions.some((permission) => user.permissions.includes(permission))) {
    return <Outlet />;
  }

  return (
    <div className="page-shell">
      <div className="panel">
        <h2>Access denied</h2>
        <p className="muted">Your role cannot open this page.</p>
      </div>
    </div>
  );
}

export function RequirePermission({ permission }: { permission: string }) {
  const { loading, authEnabled, user } = useAuth();

  if (loading) {
    return (
      <div className="page-shell">
        <LoadingPanel rows={3} />
      </div>
    );
  }

  if (!authEnabled) {
    return <Outlet />;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (user.permissions.includes(permission)) {
    return <Outlet />;
  }

  return (
    <div className="page-shell">
      <div className="panel">
        <h2>Access denied</h2>
        <p className="muted">Your role cannot open this page.</p>
      </div>
    </div>
  );
}

export function RequireAuth() {
  const { loading, authEnabled, user } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="login-shell">
        <div className="login-card">
          <LoadingPanel rows={3} />
        </div>
      </div>
    );
  }

  if (!authEnabled) {
    return <Outlet />;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (user.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }

  return <Outlet />;
}
