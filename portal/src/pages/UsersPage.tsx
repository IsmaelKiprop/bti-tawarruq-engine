import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, type Institution, type OpsUserRecord } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { HowItWorks, PageExplain } from "../components/PageExplain";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import { HOW_IT_WORKS, PAGE_EXPLAINS } from "../config/pageExplainers";
import {
  defaultInviteRole,
  getRoleProfile,
  inviteNeedsInstitution,
  inviteRoleOptions,
} from "../config/roles";
import "../components/ui.css";

export function UsersPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<OpsUserRecord[]>([]);
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [rowBusy, setRowBusy] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState(() => defaultInviteRole(user?.role));
  const [institutionId, setInstitutionId] = useState("");
  const [tempPassword, setTempPassword] = useState("");
  const [approvalLimit, setApprovalLimit] = useState("");
  const isPlatform = user?.role === "platform_admin";

  const roleOptions = useMemo(() => inviteRoleOptions(user?.role), [user?.role]);

  useEffect(() => {
    setRole(defaultInviteRole(user?.role));
  }, [user?.role]);

  async function load() {
    setLoading(true);
    try {
      const [users, books] = await Promise.all([
        api.listOpsUsers(),
        isPlatform ? api.listInstitutions().catch(() => [] as Institution[]) : Promise.resolve([] as Institution[]),
      ]);
      setItems(users);
      setInstitutions(books);
      if (!institutionId && books[0]) setInstitutionId(books[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [isPlatform]);

  async function onInvite(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    setTempPassword("");
    try {
      const created = await api.createOpsUser({
        email,
        full_name: fullName,
        role,
        institution_id: isPlatform && inviteNeedsInstitution(role) ? institutionId || null : undefined,
        approval_limit_amount: approvalLimit.trim() || null,
      });
      setMessage(created.invite_message || "User invited.");
      if (created.temporary_password) {
        setTempPassword(created.temporary_password);
      }
      setEmail("");
      setFullName("");
      setApprovalLimit("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to invite user");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(item: OpsUserRecord) {
    setRowBusy(item.id);
    setError("");
    setMessage("");
    try {
      const updated = await api.updateOpsUser(item.id, { active: !item.active });
      setMessage(
        updated.active
          ? `${updated.full_name} activated.`
          : `${updated.full_name} deactivated — they cannot sign in.`,
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update user");
    } finally {
      setRowBusy(null);
    }
  }

  async function resendInvite(item: OpsUserRecord) {
    setRowBusy(item.id);
    setError("");
    setMessage("");
    setTempPassword("");
    try {
      const reset = await api.resetOpsUserPassword(item.id);
      setMessage(reset.invite_message || "Temporary password issued.");
      if (reset.temporary_password) {
        setTempPassword(reset.temporary_password);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reset password");
    } finally {
      setRowBusy(null);
    }
  }

  return (
    <PageShell wide>
      <PageExplain content={PAGE_EXPLAINS["/users"]} />
      <HowItWorks content={HOW_IT_WORKS["/users"]} />
      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}
      {tempPassword ? (
        <Alert tone="info">
          Temporary password (SMTP did not send — share once): <strong>{tempPassword}</strong>
        </Alert>
      ) : null}

      <section className="panel">
        <h2>Invite user</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          {isPlatform
            ? "Super Admin may invite Super Admin, FI Admin, BTI Ops, Shariah, BTI Finance, and Recon. FI Operations and FI Approver are created by the FI Administrator."
            : "FI Admin may invite FI Admin, FI Operations, FI Approver, Shariah, and Recon for this institution. BTI Super Admin, BTI Ops, and BTI Finance are not available."}
        </p>
        <form className="grid-2" onSubmit={onInvite}>
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
            <select
              value={role}
              onChange={(e) => {
                const next = roleOptions.find((opt) => opt.value === e.target.value)?.value;
                if (next) setRole(next);
              }}
            >
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
              <select value={institutionId} onChange={(e) => setInstitutionId(e.target.value)} required>
                {institutions.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label>
            Approval limit (optional)
            <input
              value={approvalLimit}
              onChange={(e) => setApprovalLimit(e.target.value)}
              placeholder="e.g. 500000"
            />
          </label>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? "Inviting…" : "Invite user"}
          </button>
        </form>
      </section>

      <section className="panel">
        <h2>Portal users</h2>
        {loading ? (
          <LoadingPanel rows={4} />
        ) : items.length === 0 ? (
          <EmptyState title="No users" description="Invite an ops login for bank or SACCO staff." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Limit</th>
                  <th>Active</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const self = item.email.toLowerCase() === (user?.email || "").toLowerCase();
                  const busyRow = rowBusy === item.id;
                  return (
                    <tr key={item.id}>
                      <td>{item.full_name}</td>
                      <td>{item.email}</td>
                      <td>{getRoleProfile(item.role).label}</td>
                      <td>{item.approval_limit_amount || "—"}</td>
                      <td>{item.active ? "Yes" : "No"}</td>
                      <td>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            disabled={busyRow || self}
                            onClick={() => toggleActive(item)}
                            title={self ? "You cannot deactivate your own account" : undefined}
                          >
                            {item.active ? "Deactivate" : "Activate"}
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            disabled={busyRow}
                            onClick={() => resendInvite(item)}
                          >
                            Resend invite
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </PageShell>
  );
}
