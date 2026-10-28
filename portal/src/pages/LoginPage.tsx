import { FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { BrandLogo } from "../components/BrandLogo";
import { getDeploymentProfile } from "../config/deployment";
import { safePostLoginPath } from "../config/navigation";

export function LoginPage() {
  const { authEnabled, loading, user, applyLoginResponse } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const brand = getDeploymentProfile().brandName;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaToken, setMfaToken] = useState("");
  const [mfaMethod, setMfaMethod] = useState<"totp" | "email" | null>(null);
  const [mfaDevCode, setMfaDevCode] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (!loading && !authEnabled) {
    return <Navigate to="/" replace />;
  }

  if (!loading && user && !user.must_change_password && !user.mfa_enroll_required) {
    return <Navigate to={safePostLoginPath(user, (location.state as { from?: string })?.from, authEnabled)} replace />;
  }

  if (!loading && user?.must_change_password) {
    return <Navigate to="/change-password" replace />;
  }

  if (!loading && user?.mfa_enroll_required) {
    return <Navigate to="/settings" replace />;
  }

  async function finishLogin(result: Awaited<ReturnType<typeof api.login>>) {
    const session = applyLoginResponse(result);
    if (session.must_change_password) {
      navigate("/change-password", { replace: true });
      return;
    }
    if (session.mfa_enroll_required) {
      navigate("/settings", { replace: true });
      return;
    }
    navigate(safePostLoginPath(session, (location.state as { from?: string })?.from, authEnabled), { replace: true });
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
        setMfaMethod(result.mfa_method === "email" ? "email" : "totp");
        setMfaDevCode(result.mfa_dev_code || null);
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
          <p>
            {mfaToken
              ? mfaMethod === "email"
                ? "Email verification code"
                : "Authenticator code"
              : `${brand} ops portal sign in`}
          </p>
        </div>
        {mfaToken ? (
          <>
            <p className="muted">
              {mfaMethod === "email"
                ? "Enter the 6-digit code sent to your email."
                : "Enter the 6-digit code from Microsoft Authenticator (or Google / Authy)."}
            </p>
            {mfaDevCode ? (
              <p className="meta">
                Demo code: <code>{mfaDevCode}</code>
              </p>
            ) : null}
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
          </>
        ) : (
          <>
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="email"
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
