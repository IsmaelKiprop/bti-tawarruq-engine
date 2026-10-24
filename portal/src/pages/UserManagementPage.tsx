import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type AuditEvent, type Institution, type OpsUserRecord } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, LoadingPanel, PageShell } from "../components/PageShell";
import { inviteNeedsInstitution, inviteRoleOptions, roleLabel } from "../config/roles";

export function UserManagementPage() {
  const { userId = "" } = useParams();
  const navigate = useNavigate();
  const { user: self } = useAuth();
  const isPlatform = self?.role === "platform_admin";
  const roleOptions = useMemo(() => inviteRoleOptions(self?.role), [self?.role]);

  const [item, setItem] = useState<OpsUserRecord | null>(null);
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [tempPassword, setTempPassword] = useState("");

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [institutionId, setInstitutionId] = useState("");
  const [approvalLimit, setApprovalLimit] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [department, setDepartment] = useState("");
  const [employeeNumber, setEmployeeNumber] = useState("");
  const [phone, setPhone] = useState("");
  const [office, setOffice] = useState("");

  const isSelf = Boolean(item && self?.email && item.email.toLowerCase() === self.email.toLowerCase());

  function hydrate(record: OpsUserRecord) {
    setItem(record);
    setFullName(record.full_name || "");
    setEmail(record.email || "");
    setRole(record.role || "");
    setInstitutionId(record.institution_id || "");
    setApprovalLimit(record.approval_limit_amount || "");
    setJobTitle(record.job_title || "");
    setDepartment(record.department || "");
    setEmployeeNumber(record.employee_number || "");
    setPhone(record.phone || "");
    setOffice(record.office || "");
  }

  async function load() {
    if (!userId) return;
    setLoading(true);
    try {
      const [record, books, events] = await Promise.all([
        api.getOpsUser(userId),
        isPlatform ? api.listInstitutions().catch(() => [] as Institution[]) : Promise.resolve([] as Institution[]),
        api.getAudit(userId).catch(() => [] as AuditEvent[]),
      ]);
      hydrate(record);
      setInstitutions(books);
      setAudit(events);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load user");
      setItem(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, isPlatform]);

  async function onSaveProfile(event: FormEvent) {
    event.preventDefault();
    if (!item) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const updated = await api.updateOpsUser(item.id, {
        full_name: fullName,
        email,
        role,
        institution_id: isPlatform && inviteNeedsInstitution(role) ? institutionId || null : undefined,
        approval_limit_amount: approvalLimit.trim() || null,
        job_title: jobTitle.trim() || null,
        department: department.trim() || null,
        employee_number: employeeNumber.trim() || null,
        phone: phone.trim() || null,
        office: office.trim() || null,
      });
      hydrate(updated);
      setMessage("Profile saved.");
      const events = await api.getAudit(item.id).catch(() => [] as AuditEvent[]);
      setAudit(events);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save user");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive() {
    if (!item) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const updated = await api.updateOpsUser(item.id, { active: !item.active });
      hydrate(updated);
      setMessage(updated.active ? "User activated." : "User deactivated.");
      const events = await api.getAudit(item.id).catch(() => [] as AuditEvent[]);
      setAudit(events);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update status");
    } finally {
      setBusy(false);
    }
  }

  async function resendInvite() {
    if (!item) return;
    setBusy(true);
    setError("");
    setMessage("");
    setTempPassword("");
    try {
      const reset = await api.resetOpsUserPassword(item.id);
      setMessage(reset.invite_message || "Temporary password issued.");
      if (reset.temporary_password) setTempPassword(reset.temporary_password);
      const events = await api.getAudit(item.id).catch(() => [] as AuditEvent[]);
      setAudit(events);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reset password");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <PageShell wide>
        <LoadingPanel rows={6} />
      </PageShell>
    );
  }

  if (!item) {
    return (
      <PageShell>
        <Alert tone="error">{error || "User not found"}</Alert>
        <Link className="btn btn-secondary" to="/users">
          Back to users
        </Link>
      </PageShell>
    );
  }

  return (
    <PageShell wide>
      <header className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="meta m-0">
            <Link className="text-primary hover:underline" to="/users">
              Users
            </Link>{" "}
            / manage
          </p>
          <h2 className="m-0 mt-1 text-lg font-semibold">{item.full_name}</h2>
          <p className="muted m-0 mt-1 text-sm">
            {roleLabel(item.role)} · {item.email}
            {item.mfa_enabled ? " · MFA on" : " · MFA off"}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <button type="button" className="btn btn-secondary btn-sm" disabled={busy || isSelf} onClick={() => void toggleActive()}>
            {item.active ? "Deactivate" : "Activate"}
          </button>
          <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => void resendInvite()}>
            Resend invite
          </button>
        </div>
      </header>

      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}
      {tempPassword ? (
        <Alert tone="info">
          Temporary password (SMTP did not send — share once): <strong>{tempPassword}</strong>
        </Alert>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-2">
        <section className="panel">
          <h2>Access profile</h2>
          <form className="grid gap-3" onSubmit={onSaveProfile}>
            <div className="grid gap-3 sm:grid-cols-2">
              <label>
                Full name
                <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
              </label>
              <label>
                Email
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
              </label>
              <label>
                Role
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                  {roleOptions.some((opt) => opt.value === role) ? null : (
                    <option value={role}>{roleLabel(role)}</option>
                  )}
                  {roleOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </label>
              {isPlatform && inviteNeedsInstitution(role) ? (
                <label>
                  Institution
                  <select value={institutionId} onChange={(e) => setInstitutionId(e.target.value)}>
                    <option value="">—</option>
                    {institutions.map((inst) => (
                      <option key={inst.id} value={inst.id}>
                        {inst.name}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              <label>
                Approval limit
                <input value={approvalLimit} onChange={(e) => setApprovalLimit(e.target.value)} placeholder="Optional" />
              </label>
              <label>
                Status
                <input value={item.active ? "Active" : "Inactive"} readOnly />
              </label>
            </div>

            <h3 className="m-0 text-sm font-semibold">HR record</h3>
            <div className="grid gap-3 sm:grid-cols-2">
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
              <label className="sm:col-span-2">
                Office / branch
                <input value={office} onChange={(e) => setOffice(e.target.value)} />
              </label>
            </div>

            <div className="flex flex-wrap gap-2">
              <button type="submit" className="btn btn-primary" disabled={busy}>
                {busy ? "Saving…" : "Save changes"}
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => navigate("/users")}>
                Back
              </button>
            </div>
          </form>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Audit trail</h2>
              <p className="muted m-0 text-sm">Admin view of lifecycle events for this login</p>
            </div>
          </div>
          {audit.length === 0 ? (
            <p className="muted text-sm">No audit events yet. Saves, invites, and status changes appear here.</p>
          ) : (
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {audit.map((event) => (
                <li key={event.id} className="rounded-sm border border-border/80 bg-surface-elevated px-3 py-2">
                  <div className="text-sm font-semibold text-foreground">{event.action}</div>
                  <div className="meta">
                    {event.actor} · {new Date(event.timestamp).toLocaleString()}
                  </div>
                  {event.details ? <div className="mt-1 text-xs text-muted">{event.details}</div> : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </PageShell>
  );
}
