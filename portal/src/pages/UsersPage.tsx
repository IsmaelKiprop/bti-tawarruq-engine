import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type Institution, type OpsUserRecord } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { IconManage } from "../components/icons";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import {
  defaultInviteRole,
  inviteNeedsInstitution,
  inviteRoleOptions,
  roleLabel,
} from "../config/roles";

export function UsersPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const [items, setItems] = useState<OpsUserRecord[]>([]);
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState(() => defaultInviteRole(user?.role));
  const [institutionId, setInstitutionId] = useState(searchParams.get("institution") || "");
  const [tempPassword, setTempPassword] = useState("");
  const [approvalLimit, setApprovalLimit] = useState("");
  const [query, setQuery] = useState("");
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
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPlatform]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((item) =>
      [item.full_name, item.email, item.role, item.job_title, item.department, item.employee_number]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(q),
    );
  }, [items, query]);

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

  return (
    <PageShell wide>
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="m-0 text-lg font-semibold">Users</h2>
          <p className="muted m-0 mt-1 text-sm">
            {filtered.length} of {items.length} portal logins
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex min-w-[12rem] flex-col gap-1 text-xs uppercase tracking-wide text-muted">
            Search
            <input
              className="rounded-sm border border-border bg-surface-elevated px-2.5 py-1.5 text-sm normal-case tracking-normal text-foreground"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Name, email, role…"
            />
          </label>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => setInviteOpen((open) => !open)}
            aria-expanded={inviteOpen}
          >
            {inviteOpen ? "Hide invite" : "Invite user"}
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

      {inviteOpen ? (
        <section className="panel">
          <h2>Invite user</h2>
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
              {busy ? "Inviting…" : "Send invite"}
            </button>
          </form>
        </section>
      ) : null}

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Directory</h2>
          </div>
        </div>
        {loading ? (
          <LoadingPanel rows={4} />
        ) : filtered.length === 0 ? (
          <EmptyState title="No users" description="Invite a portal login or clear the search." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>HR</th>
                  <th>Active</th>
                  <th className="w-[1%]">Manage</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <div className="font-medium">{item.full_name}</div>
                      {item.approval_limit_amount ? (
                        <div className="meta">Limit {item.approval_limit_amount}</div>
                      ) : null}
                    </td>
                    <td>{item.email}</td>
                    <td>{roleLabel(item.role)}</td>
                    <td className="text-sm text-muted">
                      {[item.job_title, item.department, item.employee_number].filter(Boolean).join(" · ") || "—"}
                    </td>
                    <td>{item.active ? "Yes" : "No"}</td>
                    <td>
                      <Link
                        to={`/users/${item.id}`}
                        className="icon-btn"
                        aria-label={`Manage ${item.full_name}`}
                        title="Manage user"
                      >
                        <IconManage size={16} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </PageShell>
  );
}
