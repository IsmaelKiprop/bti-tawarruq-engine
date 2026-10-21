import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { BrandLogo } from "../components/BrandLogo";
import { getHomePath } from "../config/roles";
import "../components/ui.css";

export function MfaEnrollPage() {
  const { applyLoginResponse, user, refresh } = useAuth();
  const navigate = useNavigate();
  const [secret, setSecret] = useState("");
  const [url, setUrl] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const enrolled = await api.enrollMfa();
        if (!active) return;
        setSecret(enrolled.secret);
        setUrl(enrolled.otpauth_url);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "Could not start MFA enrollment");
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api.confirmMfa(code.trim());
      applyLoginResponse(result);
      await refresh();
      navigate(getHomePath(result.role), { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid authenticator code");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-shell">
      <form className="login-card" onSubmit={onSubmit}>
        <div className="login-brand login-brand--logo">
          <BrandLogo variant="lockup" />
          <p>Privileged authenticator setup</p>
        </div>
        <p className="muted">
          Super Admin, BTI Ops, and BTI Finance must enroll a TOTP authenticator (Google Authenticator,
          Authy, or similar) before using the portal.
        </p>
        {secret ? (
          <label>
            Secret
            <input value={secret} readOnly />
            <span className="meta">Add this key in your authenticator app. URI: {url}</span>
          </label>
        ) : null}
        <label>
          6-digit code
          <input
            value={code}
            onChange={(event) => setCode(event.target.value)}
            inputMode="numeric"
            autoComplete="one-time-code"
            required
          />
        </label>
        {error ? <p className="login-error">{error}</p> : null}
        <button type="submit" className="btn btn-primary" disabled={busy || !secret}>
          {busy ? "Confirming…" : "Enable MFA"}
        </button>
        {user ? <p className="meta">Signed in as {user.email}</p> : null}
      </form>
    </div>
  );
}
