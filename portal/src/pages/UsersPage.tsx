import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type Institution, type OpsUserRecord } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { IconManage } from "../components/icons";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import { isActiveInstitution } from "../config/fiKyc";
import {
  canAssignInviteInstitution,
  defaultInviteRole,
  inviteNeedsInstitution,
  inviteRoleOptionsForBook,
  isBtiManagedUser,
  roleLabel,
} from "../config/roles";

type UserBook = "bti" | "fi";

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
  const [book, setBook] = useState<UserBook>(() =>
    searchParams.get("institution") || user?.role === "bti_ops" ? "fi" : "bti",
  );
  const canPickInstitution = canAssignInviteInstitution(user?.role);
  const splitBooks = canPickInstitution;

  const roleOptions = useMemo(
    () => (splitBooks ? inviteRoleOptionsForBook(user?.role, book) : inviteRoleOptionsForBook(user?.role, "fi")),
    [user?.role, book, splitBooks],
  );

  useEffect(() => {
    if (!roleOptions.some((opt) => opt.value === role)) {
      setRole(roleOptions[0]?.value || defaultInviteRole(user?.role));
    }
  }, [role, roleOptions, user?.role]);

  async function load() {
    setLoading(true);
    try {
      const [users, books] = await Promise.all([
        api.listOpsUsers(),
        canPickInstitution ? api.listInstitutions().catch(() => [] as Institution[]) : Promise.resolve([] as Institution[]),
      ]);
      setItems(users);
      const activeBooks = books.filter(isActiveInstitution);
      setInstitutions(activeBooks);
      if (!institutionId && activeBooks[0]) setInstitutionId(activeBooks[0].id);
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
  }, [canPickInstitution]);

  const institutionName = useMemo(() => {
    const names = new Map(institutions.map((item) => [item.id, item.name]));
    return (id?: string | null) => (id ? names.get(id) || id : "—");
  }, [institutions]);

  const bookItems = useMemo(() => {
    if (!splitBooks) return items;
    return items.filter((item) => (book === "bti" ? isBtiManagedUser(item.role, item.institution_id) : !isBtiManagedUser(item.role, item.institution_id)));
  }, [items, book, splitBooks]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return bookItems;
    return bookItems.filter((item) =>
      [item.full_name, item.email, item.role, item.job_title, item.department, item.employee_number, institutionName(item.institution_id)]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(q),
    );
  }, [bookItems, query, institutionName]);

  function switchBook(next: UserBook) {
    setBook(next);
    setQuery("");
    setInviteOpen(false);
  }

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
        institution_id: canPickInstitution && inviteNeedsInstitution(role, book) ? institutionId || null : undefined,
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

  const canInviteHere = roleOptions.length > 0;

  return (
    <PageShell wide>
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="m-0 text-lg font-semibold">Users</h2>
          <p className="muted m-0 mt-1 text-sm">
            {splitBooks
              ? book === "bti"
                ? `${filtered.length} BTI staff. Super Admin, BTI Ops, BTI Finance, and BTI-wide Shariah / Recon live here.`
                : `${filtered.length} FI logins. Invite FI Admin only for Active institutions. FI Shariah is tenant-scoped.`
              : `${filtered.length} of ${items.length} portal logins for your institution.`}
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          {splitBooks ? (
            <div className="queue-filters m-0" role="tablist" aria-label="User books">
              <button type="button" className={`chip${book === "bti" ? " active" : ""}`} role="tab" aria-selected={book === "bti"} onClick={() => switchBook("bti")}>
                BTI
              </button>
              <button type="button" className={`chip${book === "fi" ? " active" : ""}`} role="tab" aria-selected={book === "fi"} onClick={() => switchBook("fi")}>
                FI users
              </button>
            </div>
          ) : null}
          <label className="flex min-w-[12rem] flex-col gap-1 text-xs uppercase tracking-wide text-muted">
            Search
            <input
              className="rounded-sm border border-border bg-surface-elevated px-2.5 py-1.5 text-sm normal-case tracking-normal text-foreground"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={book === "fi" && splitBooks ? "Name, email, institution…" : "Name, email, role…"}
            />
          </label>
          {canInviteHere ? (
            <button type="button" className="btn btn-primary btn-sm" onClick={() => setInviteOpen((open) => !open)} aria-expanded={inviteOpen}>
              {inviteOpen ? "Hide invite" : book === "bti" && splitBooks ? "Invite BTI user" : "Invite FI user"}
            </button>
          ) : null}
        </div>
      </header>

      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}
      {tempPassword ? (
        <Alert tone="info">
          Temporary password (SMTP did not send — share once): <strong>{tempPassword}</strong>
        </Alert>
      ) : null}

      {inviteOpen && canInviteHere ? (
        <section className="panel">
          <h2>{splitBooks && book === "bti" ? "Invite BTI staff" : "Invite FI login"}</h2>
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
                      {splitBooks && book === "bti" && (opt.value === "shariah_officer" || opt.value === "reconciler")
                        ? `${opt.label} (BTI-wide)`
                        : opt.label}
                    </option>
                  ))}
              </select>
            </label>
            {canPickInstitution && inviteNeedsInstitution(role, book) ? (
              <label>
                Institution
                <select value={institutionId} onChange={(e) => setInstitutionId(e.target.value)} required>
                  {institutions.length === 0 ? <option value="">No active institution</option> : null}
                  {institutions.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {book === "fi" || !splitBooks ? (
              <label>
                Approval limit (optional)
                <input value={approvalLimit} onChange={(e) => setApprovalLimit(e.target.value)} placeholder="e.g. 500000" />
              </label>
            ) : null}
            <button className="btn btn-primary" type="submit" disabled={busy}>
              {busy ? "Inviting…" : "Send invite"}
            </button>
          </form>
        </section>
      ) : null}

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>{splitBooks ? (book === "bti" ? "BTI staff" : "FI logins") : "Directory"}</h2>
          </div>
        </div>
        {loading ? (
          <LoadingPanel rows={4} />
        ) : filtered.length === 0 ? (
          <EmptyState
            title={!splitBooks ? "No users" : book === "bti" ? "No BTI staff" : "No FI users"}
            description={
              splitBooks && book === "fi"
                ? "Invite an FI Admin on an Active institution, or clear the search."
                : "Invite a portal login or clear the search."
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  {splitBooks && book === "fi" ? <th>Institution</th> : null}
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
                      {item.approval_limit_amount ? <div className="meta">Limit {item.approval_limit_amount}</div> : null}
                    </td>
                    <td>{item.email}</td>
                    <td>{roleLabel(item.role)}</td>
                    {splitBooks && book === "fi" ? <td>{institutionName(item.institution_id)}</td> : null}
                    <td className="text-sm text-muted">
                      {[item.job_title, item.department, item.employee_number].filter(Boolean).join(" · ") || "—"}
                    </td>
                    <td>{item.active ? "Yes" : "No"}</td>
                    <td>
                      <Link to={`/users/${item.id}`} className="icon-btn" aria-label={`Manage ${item.full_name}`} title="Manage user">
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
