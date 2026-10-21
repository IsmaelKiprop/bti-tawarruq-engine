import { FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { BrandLogo } from "../components/BrandLogo";
import { getHomePath } from "../config/roles";
import "../components/ui.css";

export function LoginPage() {
  const { authEnabled, loading, user, applyLoginResponse } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("admin@bti.local");
  const [password, setPassword] = useState("");
  const [mfaToken, setMfaToken] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (!loading && !authEnabled) {
    return <Navigate to="/" replace />;
  }

  if (!loading && user && !user.must_change_password && !user.mfa_enroll_required) {
    return <Navigate to={(location.state as { from?: string })?.from || getHomePath(user.role)} replace />;
  }

  if (!loading && user?.must_change_password) {
    return <Navigate to="/change-password" replace />;
  }

  if (!loading && user?.mfa_enroll_required) {
    return <Navigate to="/mfa-enroll" replace />;
  }

  async function finishLogin(result: Awaited<ReturnType<typeof api.login>>) {
    const session = applyLoginResponse(result);
    if (session.must_change_password) {
      navigate("/change-password", { replace: true });
      return;
    }
    if (session.mfa_enroll_required) {
      navigate("/mfa-enroll", { replace: true });
      return;
    }
    navigate(getHomePath(session.role), { replace: true });
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mfaToken) {
        const result = await api.verifyMfa(mfaToken, mfaCode.trim());
        await finishLogin(result);
        return;
      }
      const result = await api.login(email.trim(), password);
      if (result.mfa_required && result.mfa_token) {
        setMfaToken(result.mfa_token);
        return;
      }
      await finishLogin(result);
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
          <p>{mfaToken ? "Authenticator code" : "Ops portal sign in"}</p>
        </div>
        {mfaToken ? (
          <label>
            6-digit code
            <input
              value={mfaCode}
              onChange={(event) => setMfaCode(event.target.value)}
              inputMode="numeric"
              autoComplete="one-time-code"
              required
            />
          </label>
        ) : (
          <>
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
          </>
        )}
        {error ? <p className="login-error">{error}</p> : null}
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? "Signing in…" : mfaToken ? "Verify" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
