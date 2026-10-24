import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, PageShell } from "../components/PageShell";
import { useTheme } from "../hooks/useTheme";
import { getRoleProfile, roleLabel } from "../config/roles";

type MfaMode = "idle" | "totp";

export function SettingsPage() {
  const { user, applyLoginResponse, refresh } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const profile = getRoleProfile(user?.role);

  const [fullName, setFullName] = useState(user?.full_name || "");
  const [jobTitle, setJobTitle] = useState(user?.job_title || "");
  const [department, setDepartment] = useState(user?.department || "");
  const [employeeNumber, setEmployeeNumber] = useState(user?.employee_number || "");
  const [phone, setPhone] = useState(user?.phone || "");
  const [office, setOffice] = useState(user?.office || "");
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileMsg, setProfileMsg] = useState<{ tone: "error" | "success"; text: string } | null>(null);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [passwordMsg, setPasswordMsg] = useState<{ tone: "error" | "success"; text: string } | null>(null);

  const [mfaMode, setMfaMode] = useState<MfaMode>("idle");
  const [totpSecret, setTotpSecret] = useState("");
  const [totpUrl, setTotpUrl] = useState("");
  const [disablePassword, setDisablePassword] = useState("");
  const [mfaBusy, setMfaBusy] = useState(false);
  const [mfaMsg, setMfaMsg] = useState<{ tone: "error" | "success" | "info"; text: string } | null>(null);

  useEffect(() => {
    setFullName(user?.full_name || "");
    setJobTitle(user?.job_title || "");
    setDepartment(user?.department || "");
    setEmployeeNumber(user?.employee_number || "");
    setPhone(user?.phone || "");
    setOffice(user?.office || "");
  }, [user]);

  const privilegedMfa = useMemo(
    () => ["platform_admin", "bti_ops", "bti_finance"].includes(user?.role || ""),
    [user?.role],
  );

  async function onSaveProfile(event: FormEvent) {
    event.preventDefault();
    setProfileBusy(true);
    setProfileMsg(null);
    try {
      await api.updateOwnProfile({
        full_name: fullName.trim(),
        job_title: jobTitle.trim() || null,
        department: department.trim() || null,
        employee_number: employeeNumber.trim() || null,
        phone: phone.trim() || null,
        office: office.trim() || null,
      });
      await refresh();
      setProfileMsg({ tone: "success", text: "Profile and HR details saved." });
    } catch (err) {
      setProfileMsg({ tone: "error", text: err instanceof Error ? err.message : "Could not save profile" });
    } finally {
      setProfileBusy(false);
    }
  }

  const roleLinks = useMemo(() => {
    const links: { to: string; label: string; hint: string }[] = [];
    if (user?.permissions.includes("manage_institutions")) {
      links.push({ to: "/institutions", label: "Institutions", hint: "Tenant banks and SACCO onboarding" });
    }
    if (user?.permissions.includes("manage_credentials")) {
      links.push({ to: "/users", label: "Users & roles", hint: "Invite portal logins for your scope" });
      links.push({ to: "/webhooks", label: "API keys & webhooks", hint: "Machine credentials and callbacks" });
    }
    if (user?.permissions.includes("manage_integrations")) {
      links.push({ to: "/integrations", label: "Integrations", hint: "M-Pesa, MNO, and partner profiles" });
    }
    if (user?.permissions.includes("manage_billing")) {
      links.push({ to: "/billing", label: "Billing", hint: "Invoices and usage fees" });
    }
    if (user?.permissions.includes("view_metrics")) {
      links.push({ to: "/ops", label: "Ops monitor", hint: "Engine telemetry for your role" });
    }
    return links;
  }, [user?.permissions]);

  async function onChangePassword(event: FormEvent) {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      setPasswordMsg({ tone: "error", text: "New passwords do not match." });
      return;
    }
    setPasswordBusy(true);
    setPasswordMsg(null);
    try {
      const result = await api.changePassword(currentPassword, newPassword);
      applyLoginResponse(result);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordMsg({ tone: "success", text: "Password updated." });
      await refresh();
    } catch (err) {
      setPasswordMsg({ tone: "error", text: err instanceof Error ? err.message : "Password change failed" });
    } finally {
      setPasswordBusy(false);
    }
  }

  async function startTotp() {
    setMfaBusy(true);
    setMfaMsg(null);
    try {
      const enrolled = await api.enrollMfa();
      setTotpSecret(enrolled.secret);
      setTotpUrl(enrolled.otpauth_url);
      setMfaMode("totp");
    } catch (err) {
      setMfaMsg({ tone: "error", text: err instanceof Error ? err.message : "Could not start authenticator setup" });
    } finally {
      setMfaBusy(false);
    }
  }

  async function enableTotp() {
    setMfaBusy(true);
    setMfaMsg(null);
    try {
      const result = await api.enableTotpMfa();
      applyLoginResponse(result);
      await refresh();
      setMfaMode("idle");
      setTotpSecret("");
      setTotpUrl("");
      setMfaMsg({
        tone: "success",
        text: "Authenticator MFA enabled. Codes are required at sign-in.",
      });
    } catch (err) {
      setMfaMsg({ tone: "error", text: err instanceof Error ? err.message : "Could not enable authenticator MFA" });
    } finally {
      setMfaBusy(false);
    }
  }

  async function enableEmailMfa() {
    setMfaBusy(true);
    setMfaMsg(null);
    try {
      const result = await api.enableEmailMfa();
      applyLoginResponse(result);
      await refresh();
      setMfaMode("idle");
      setMfaMsg({
        tone: "success",
        text: "Email MFA enabled. A code will be required at sign-in.",
      });
    } catch (err) {
      setMfaMsg({ tone: "error", text: err instanceof Error ? err.message : "Could not enable email MFA" });
    } finally {
      setMfaBusy(false);
    }
  }

  async function onDisableMfa(event: FormEvent) {
    event.preventDefault();
    setMfaBusy(true);
    setMfaMsg(null);
    try {
      const result = await api.disableMfa(disablePassword);
      applyLoginResponse(result);
      await refresh();
      setDisablePassword("");
      setMfaMode("idle");
      setMfaMsg({
        tone: privilegedMfa ? "info" : "success",
        text: privilegedMfa
          ? "MFA turned off. Super Admin / BTI Ops / BTI Finance should re-enable it soon."
          : "MFA turned off.",
      });
    } catch (err) {
      setMfaMsg({ tone: "error", text: err instanceof Error ? err.message : "Could not disable MFA" });
    } finally {
      setMfaBusy(false);
    }
  }

  const qrSrc = totpUrl
    ? `https://api.qrserver.com/v1/create-qr-code/?size=140x140&margin=6&data=${encodeURIComponent(totpUrl)}`
    : "";

  const methodLabel =
    user?.mfa_method === "email" ? "Email code" : user?.mfa_method === "totp" ? "Authenticator app" : null;

  if (!user) {
    return (
      <PageShell>
        <Alert tone="info">Sign in to manage settings.</Alert>
      </PageShell>
    );
  }

  return (
    <PageShell>
      <div className="settings-grid">
        <section className="panel settings-panel">
          <div className="panel-header">
            <div>
              <h2>Account</h2>
              <p className="muted">Portal session identity</p>
            </div>
            <span className="badge info">{roleLabel(user.role)}</span>
          </div>
          <dl className="settings-dl">
            <div>
              <dt>Email</dt>
              <dd>{user.email}</dd>
            </div>
            <div>
              <dt>Role</dt>
              <dd>
                {profile.label}
                <span className="meta"> · {profile.navDescription}</span>
              </dd>
            </div>
            <div>
              <dt>Workspace</dt>
              <dd>{user.institution_name || profile.workspaceFallback}</dd>
            </div>
          </dl>
          <p className="meta" style={{ marginBottom: 0 }}>
            Desk process notes live in{" "}
            <Link to="/documentation">Documentation</Link>
            {user.permissions.includes("manage_credentials") ? (
              <>
                . Admins manage other logins on <Link to="/users">Users</Link>.
              </>
            ) : (
              "."
            )}
          </p>
        </section>

        <section className="panel settings-panel">
          <div className="panel-header">
            <div>
              <h2>Profile & HR</h2>
              <p className="muted">Name and staff record for this login</p>
            </div>
          </div>
          {profileMsg ? <Alert tone={profileMsg.tone}>{profileMsg.text}</Alert> : null}
          <form className="settings-form" onSubmit={onSaveProfile}>
            <label>
              Display name
              <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
            </label>
            <label>
              Job title
              <input value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} placeholder="e.g. Credit officer" />
            </label>
            <label>
              Department
              <input value={department} onChange={(e) => setDepartment(e.target.value)} placeholder="e.g. Retail banking" />
            </label>
            <label>
              Employee number
              <input value={employeeNumber} onChange={(e) => setEmployeeNumber(e.target.value)} />
            </label>
            <label>
              Phone
              <input value={phone} onChange={(e) => setPhone(e.target.value)} />
            </label>
            <label>
              Office / branch
              <input value={office} onChange={(e) => setOffice(e.target.value)} />
            </label>
            <button type="submit" className="btn btn-primary" disabled={profileBusy}>
              {profileBusy ? "Saving…" : "Save profile"}
            </button>
          </form>
        </section>

        <section className="panel settings-panel">
          <div className="panel-header">
            <div>
              <h2>Appearance</h2>
              <p className="muted">This browser only</p>
            </div>
          </div>
          <div className="settings-row">
            <div>
              <strong>Theme</strong>
              <p className="meta">{theme === "light" ? "Light" : "Dark"} mode</p>
            </div>
            <button type="button" className="btn btn-secondary btn-sm" onClick={toggleTheme}>
              Switch to {theme === "light" ? "dark" : "light"}
            </button>
          </div>
        </section>

        <section className="panel settings-panel">
          <div className="panel-header">
            <div>
              <h2>Password</h2>
              <p className="muted">Update portal login password</p>
            </div>
          </div>
          {passwordMsg ? <Alert tone={passwordMsg.tone}>{passwordMsg.text}</Alert> : null}
          <form className="settings-form" onSubmit={onChangePassword}>
            <label>
              Current password
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            <label>
              New password
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
                minLength={8}
                required
              />
            </label>
            <label>
              Confirm new password
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                minLength={8}
                required
              />
            </label>
            <button type="submit" className="btn btn-primary" disabled={passwordBusy}>
              {passwordBusy ? "Saving…" : "Update password"}
            </button>
          </form>
        </section>

        <section className="panel settings-panel">
          <div className="panel-header">
            <div>
              <h2>Two-factor authentication</h2>
              <p className="muted">
                Enable here — verification happens at login
                {privilegedMfa ? " (required for Super Admin, BTI Ops, BTI Finance)" : ""}.
              </p>
            </div>
            <span className={`badge ${user.mfa_enabled ? "success" : "warning"}`}>
              {user.mfa_enabled ? `On · ${methodLabel}` : "Off"}
            </span>
          </div>

          {mfaMsg ? <Alert tone={mfaMsg.tone}>{mfaMsg.text}</Alert> : null}

          {!user.mfa_enabled && mfaMode === "idle" ? (
            <div className="settings-mfa-choices">
              <button type="button" className="settings-choice" onClick={() => void startTotp()} disabled={mfaBusy}>
                <strong>Authenticator app</strong>
                <span>Microsoft Authenticator, Google Authenticator, or Authy</span>
              </button>
              <button type="button" className="settings-choice" onClick={() => void enableEmailMfa()} disabled={mfaBusy}>
                <strong>Email code</strong>
                <span>Require a code to {user.email} at sign-in</span>
              </button>
            </div>
          ) : null}

          {mfaMode === "totp" ? (
            <div className="settings-totp">
              <p className="meta">Add this account in your authenticator app, then enable. Codes are checked at login.</p>
              <div className="settings-totp-body">
                {qrSrc ? <img className="mfa-qr" src={qrSrc} alt="Authenticator QR code" /> : null}
                <label>
                  Manual secret
                  <input value={totpSecret} readOnly />
                </label>
              </div>
              <div className="settings-actions">
                <button type="button" className="btn btn-primary" onClick={() => void enableTotp()} disabled={mfaBusy || !totpSecret}>
                  {mfaBusy ? "Enabling…" : "Enable authenticator"}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setMfaMode("idle")} disabled={mfaBusy}>
                  Cancel
                </button>
              </div>
            </div>
          ) : null}

          {user.mfa_enabled && mfaMode === "idle" ? (
            <form className="settings-form" onSubmit={onDisableMfa}>
              <label>
                Current password to disable MFA
                <input
                  type="password"
                  value={disablePassword}
                  onChange={(e) => setDisablePassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
              </label>
              <div className="settings-actions">
                <button type="submit" className="btn btn-secondary" disabled={mfaBusy}>
                  {mfaBusy ? "Updating…" : "Disable MFA"}
                </button>
                {user.mfa_method !== "totp" ? (
                  <button type="button" className="btn btn-secondary" onClick={() => void startTotp()} disabled={mfaBusy}>
                    Switch to authenticator
                  </button>
                ) : null}
                {user.mfa_method !== "email" ? (
                  <button type="button" className="btn btn-secondary" onClick={() => void enableEmailMfa()} disabled={mfaBusy}>
                    Switch to email
                  </button>
                ) : null}
              </div>
            </form>
          ) : null}
        </section>

        {roleLinks.length > 0 ? (
          <section className="panel settings-panel">
            <div className="panel-header">
              <div>
                <h2>Role workspace</h2>
                <p className="muted">Shortcuts for {profile.label}</p>
              </div>
            </div>
            <div className="settings-links">
              {roleLinks.map((link) => (
                <Link key={link.to} to={link.to} className="settings-choice">
                  <strong>{link.label}</strong>
                  <span>{link.hint}</span>
                </Link>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </PageShell>
  );
}
