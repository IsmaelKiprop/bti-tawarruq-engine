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
  const [copied, setCopied] = useState(false);

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

  async function copySecret() {
    if (!secret) return;
    try {
      await navigator.clipboard.writeText(secret);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

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

  const qrSrc = url
    ? `https://api.qrserver.com/v1/create-qr-code/?size=180x180&margin=8&data=${encodeURIComponent(url)}`
    : "";

  return (
    <div className="login-shell">
      <form className="login-card login-card--mfa" onSubmit={onSubmit}>
        <div className="login-brand login-brand--logo">
          <BrandLogo variant="lockup" />
          <p>Authenticator setup</p>
        </div>
        <p className="muted">
          Super Admin, BTI Ops, and BTI Finance must add this account to Google Authenticator, Authy, or
          Microsoft Authenticator before the desks open.
        </p>
        <ol className="flow-list numbered">
          <li>Open the authenticator app and tap add account.</li>
          <li>Scan the QR code. If you cannot scan, copy the secret and add it manually.</li>
          <li>Type the current 6-digit code below and enable MFA.</li>
        </ol>
        {secret ? (
          <div className="mfa-setup">
            {qrSrc ? (
              <img className="mfa-qr" src={qrSrc} alt="Scan this QR code in your authenticator app" />
            ) : null}
            <label>
              Manual secret
              <input value={secret} readOnly />
              <span className="meta">Use this only if the camera cannot scan the code.</span>
            </label>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => void copySecret()}>
              {copied ? "Copied" : "Copy secret"}
            </button>
          </div>
        ) : (
          <p className="meta">Preparing your authenticator key…</p>
        )}
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
