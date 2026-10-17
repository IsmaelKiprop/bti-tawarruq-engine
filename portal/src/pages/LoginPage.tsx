import { FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { BrandLogo } from "../components/BrandLogo";
import { getHomePath } from "../config/roles";
import "../components/ui.css";

export function LoginPage() {
  const { authEnabled, loading, user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("admin@bti.local");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (!loading && !authEnabled) {
    return <Navigate to="/" replace />;
  }

  if (!loading && user && !user.must_change_password) {
    return <Navigate to={(location.state as { from?: string })?.from || getHomePath(user.role)} replace />;
  }

  if (!loading && user?.must_change_password) {
    return <Navigate to="/change-password" replace />;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await login(email.trim(), password);
      navigate(result.must_change_password ? "/change-password" : getHomePath(result.role), { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-shell">
      <form className="login-card" onSubmit={onSubmit}>
        <div className="login-brand login-brand--logo">
          <BrandLogo variant="lockup" />
          <p>Ops portal sign in</p>
        </div>
        <p className="muted">
          This portal runs Kenya float Tawarruq and Malaysia palm oil Tawarruq. It is not a cash-loan
          book. Use the email and password issued by your admin. Temporary passwords must be changed
          after first sign-in. Then pick a customer, lock the Murabaha offer, and run the commodity desk.
        </p>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error ? <p className="login-error">{error}</p> : null}
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
