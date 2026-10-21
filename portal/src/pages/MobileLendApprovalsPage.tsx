import { FormEvent, useEffect, useState } from "react";
import { api, Institution } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { HowItWorks, PageExplain } from "../components/PageExplain";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import { HOW_IT_WORKS, PAGE_EXPLAINS } from "../config/pageExplainers";
import "../components/ui.css";

type MobileAccountRow = {
  id: string;
  email: string;
  full_name: string;
  email_verified: boolean;
  approval_status: string;
  phone: string | null;
  credit_limit: string | null;
  can_borrow: boolean;
  approval_message: string | null;
  institution_id: string | null;
  institution_name: string | null;
  created_at: string | null;
};

type MobileInviteRow = {
  id: string;
  email: string;
  phone: string | null;
  full_name: string | null;
  code: string;
  credit_limit: string;
  activate_on_claim: boolean;
  status: string;
  institution_name: string | null;
  delivery?: { dev_code?: string | null };
};

export function MobileLendApprovalsPage() {
  const { user } = useAuth();
  const canInvite = !user || user.permissions.includes("write_ops");
  const canApprove = !user || user.permissions.includes("approve_txn");
  const [accounts, setAccounts] = useState<MobileAccountRow[]>([]);
  const [invites, setInvites] = useState<MobileInviteRow[]>([]);
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [filter, setFilter] = useState("pending");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const [inviteEmail, setInviteEmail] = useState("");
  const [invitePhone, setInvitePhone] = useState("2547");
  const [inviteName, setInviteName] = useState("");
  const [inviteLimit, setInviteLimit] = useState("100000");
  const [inviteInstitutionId, setInviteInstitutionId] = useState("");
  const [activateOnClaim, setActivateOnClaim] = useState(false);

  const [approvePhone, setApprovePhone] = useState<Record<string, string>>({});
  const [approveLimit, setApproveLimit] = useState<Record<string, string>>({});

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [acc, inv, inst] = await Promise.all([
        api.listMobileAccounts(filter || undefined),
        api.listMobileInvites(),
        api.listInstitutions().catch(() => [] as Institution[]),
      ]);
      setAccounts(acc);
      setInvites(inv);
      setInstitutions(inst);
      if (!inviteInstitutionId && (user?.institution_id || inst[0]?.id)) {
        setInviteInstitutionId(user?.institution_id || inst[0]?.id || "");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load mobile lend queue.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [filter]);

  async function sendInvite(event: FormEvent) {
    event.preventDefault();
    if (!canInvite) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await api.createMobileInvite({
        institution_id: inviteInstitutionId,
        email: inviteEmail.trim().toLowerCase(),
        phone: invitePhone.trim() || undefined,
        full_name: inviteName.trim() || undefined,
        credit_limit: inviteLimit,
        activate_on_claim: activateOnClaim,
      });
      setMessage(
        `Invite ${result.code} created for ${result.email}` +
          (result.delivery?.dev_code ? ` · dev code ${result.delivery.dev_code}` : ""),
      );
      setInviteEmail("");
      setInviteName("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invite failed.");
    } finally {
      setBusy(false);
    }
  }

  async function approve(account: MobileAccountRow) {
    if (!canApprove) return;
    const phone = (approvePhone[account.id] || account.phone || "").trim();
    const limit = (approveLimit[account.id] || account.credit_limit || "100000").trim();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api.approveMobileAccount(account.id, {
        phone,
        credit_limit: limit,
        institution_id: account.institution_id || inviteInstitutionId || undefined,
      });
      setMessage(`Approved ${account.email}. They can borrow up to KES ${limit}.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed.");
    } finally {
      setBusy(false);
    }
  }

  async function reject(account: MobileAccountRow) {
    if (!canApprove) return;
    const reason = window.prompt("Rejection reason", "Incomplete KYC documentation") || "";
    if (!reason.trim()) return;
    setBusy(true);
    try {
      await api.rejectMobileAccount(account.id, reason.trim());
      setMessage(`Rejected ${account.email}.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reject failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell>
      <header className="page-header">
        <h1>Mobile Lend approvals</h1>
        <p className="muted">
          Invite members and activate Buruuj Lend accounts before they can borrow.
        </p>
      </header>
      <PageExplain content={PAGE_EXPLAINS["/mobile-lend"] || PAGE_EXPLAINS["/customers"]} />
      <HowItWorks content={HOW_IT_WORKS["/mobile-lend"] || HOW_IT_WORKS["/customers"]} />

      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}

      {canInvite ? (
        <form className="card stack gap-md" onSubmit={sendInvite}>
          <h2>Invite by email</h2>
          <p className="muted">
            Customer registers with that email, claims the invite code, then you activate (unless auto-activate is on).
          </p>
          <div className="grid-2">
            <label>
              Institution
              <select
                value={inviteInstitutionId}
                onChange={(e) => setInviteInstitutionId(e.target.value)}
                required
              >
                <option value="">Select</option>
                {institutions.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Credit limit (KES)
              <input value={inviteLimit} onChange={(e) => setInviteLimit(e.target.value)} required />
            </label>
            <label>
              Email
              <input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                required
              />
            </label>
            <label>
              Phone (254…)
              <input value={invitePhone} onChange={(e) => setInvitePhone(e.target.value)} />
            </label>
            <label>
              Full name
              <input value={inviteName} onChange={(e) => setInviteName(e.target.value)} />
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={activateOnClaim}
                onChange={(e) => setActivateOnClaim(e.target.checked)}
              />
              Auto-activate on claim (KYC already done offline)
            </label>
          </div>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            Send invite
          </button>
        </form>
      ) : null}

      <div className="card stack gap-md">
        <div className="row between">
          <h2>Mobile accounts</h2>
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="">All</option>
          </select>
        </div>
        {loading ? (
          <LoadingPanel />
        ) : accounts.length === 0 ? (
          <EmptyState title="No accounts" description="Self-registered app users appear here after email verify." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Status</th>
                  <th>Institution</th>
                  <th>Activate</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((account) => (
                  <tr key={account.id}>
                    <td>
                      <strong>{account.full_name}</strong>
                      <div className="muted">{account.email}</div>
                      <div className="muted">{account.phone || "No phone yet"}</div>
                    </td>
                    <td>
                      <span className="badge">{account.approval_status}</span>
                      <div className="muted">{account.approval_message}</div>
                    </td>
                    <td>{account.institution_name || "—"}</td>
                    <td>
                      {account.approval_status === "pending" && canApprove ? (
                        <div className="stack gap-sm">
                          <input
                            placeholder="2547…"
                            value={approvePhone[account.id] ?? account.phone ?? ""}
                            onChange={(e) =>
                              setApprovePhone((prev) => ({ ...prev, [account.id]: e.target.value }))
                            }
                          />
                          <input
                            placeholder="Limit KES"
                            value={approveLimit[account.id] ?? account.credit_limit ?? "100000"}
                            onChange={(e) =>
                              setApproveLimit((prev) => ({ ...prev, [account.id]: e.target.value }))
                            }
                          />
                          <div className="row gap-sm">
                            <button className="btn btn-primary btn-sm" type="button" disabled={busy} onClick={() => void approve(account)}>
                              Approve
                            </button>
                            <button className="btn btn-secondary btn-sm" type="button" disabled={busy} onClick={() => void reject(account)}>
                              Reject
                            </button>
                          </div>
                        </div>
                      ) : (
                        <span className="muted">
                          {account.can_borrow ? `Limit KES ${account.credit_limit}` : "—"}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card stack gap-md">
        <h2>Invites</h2>
        {invites.length === 0 ? (
          <EmptyState title="No invites yet" description="Send an invite above for a member email." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Code</th>
                  <th>Limit</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {invites.map((invite) => (
                  <tr key={invite.id}>
                    <td>
                      {invite.full_name || invite.email}
                      <div className="muted">{invite.email}</div>
                    </td>
                    <td>
                      <code>{invite.code}</code>
                    </td>
                    <td>KES {invite.credit_limit}</td>
                    <td>
                      {invite.status}
                      {invite.activate_on_claim ? " · auto" : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PageShell>
  );
}
