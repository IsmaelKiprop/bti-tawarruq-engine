import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type AuditGroup, type Institution } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, LoadingPanel, PageShell } from "../components/PageShell";
import { BSAS_MODE_ORDER, getBsasMode } from "../config/institutions";

export function InstitutionManagementPage() {
  const { institutionId = "" } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const canManage = user?.role === "platform_admin" || Boolean(user?.permissions.includes("manage_institutions"));

  const [item, setItem] = useState<Institution | null>(null);
  const [auditGroups, setAuditGroups] = useState<AuditGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const [editName, setEditName] = useState("");
  const [editMode, setEditMode] = useState("manual_bridge");
  const [editActive, setEditActive] = useState(true);
  const [editSteps, setEditSteps] = useState("murabaha,liquidation,disbursement");
  const [editLimit, setEditLimit] = useState("");
  const [editFeeBps, setEditFeeBps] = useState("25");

  const protectedRow = Boolean(item && item.code.toUpperCase() === "DEFAULT");

  function hydrate(record: Institution) {
    setItem(record);
    setEditName(record.name);
    setEditMode(record.bsas_mode || "manual_bridge");
    setEditActive(record.active !== false);
    setEditSteps(record.approval_steps || "murabaha,liquidation,disbursement");
    setEditLimit(record.approval_limit_amount || "");
    setEditFeeBps(String(record.billing_fee_bps ?? 25));
  }

  async function load() {
    if (!institutionId) return;
    setLoading(true);
    try {
      const [record, feed] = await Promise.all([
        api.getInstitution(institutionId),
        api
          .getOpsAuditFeed({ institution_id: institutionId, limit: 120, grouped: true })
          .catch(() => null),
      ]);
      hydrate(record);
      setAuditGroups(feed?.groups || []);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load institution");
      setItem(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [institutionId]);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    if (!item || !canManage) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const updated = await api.updateInstitution(item.id, {
        name: editName.trim(),
        bsas_mode: editMode,
        active: editActive,
        approval_steps: editSteps,
        approval_limit_amount: editLimit.trim() || null,
        billing_fee_bps: Number(editFeeBps),
      });
      hydrate(updated);
      setMessage("Institution saved.");
      const feed = await api
        .getOpsAuditFeed({ institution_id: item.id, limit: 120, grouped: true })
        .catch(() => null);
      setAuditGroups(feed?.groups || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update institution");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    if (!item || !canManage || protectedRow) return;
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api.deleteInstitution(item.id);
      navigate("/institutions", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete institution");
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
        <Alert tone="error">{error || "Institution not found"}</Alert>
        <Link className="btn btn-secondary" to="/institutions">
          Back to institutions
        </Link>
      </PageShell>
    );
  }

  return (
    <PageShell wide>
      <header className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="meta m-0">
            <Link className="text-primary hover:underline" to="/institutions">
              Institutions
            </Link>{" "}
            / manage
          </p>
          <h2 className="m-0 mt-1 text-lg font-semibold">{item.name}</h2>
          <p className="muted m-0 mt-1 text-sm">
            <code>{item.code}</code> · {getBsasMode(item.bsas_mode).label} ·{" "}
            {item.active === false ? "Suspended" : "Active"}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Link className="btn btn-secondary btn-sm" to={`/integrations?institution=${item.id}`}>
            Integrations
          </Link>
          {canManage ? (
            <Link className="btn btn-secondary btn-sm" to={`/users?institution=${item.id}`}>
              Users
            </Link>
          ) : null}
          {canManage ? (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={busy || protectedRow}
              title={protectedRow ? "The default institution cannot be deleted" : undefined}
              onClick={() => void onDelete()}
            >
              {confirmDelete ? "Confirm delete" : "Delete"}
            </button>
          ) : null}
        </div>
      </header>

      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}

      <div className="grid gap-3 lg:grid-cols-2">
        <section className="panel">
          <h2>Tenant profile</h2>
          {!canManage ? (
            <Alert tone="info">You can view this institution. Only platform admins can edit it.</Alert>
          ) : null}
          <form className="grid gap-3" onSubmit={onSave}>
            <div className="grid gap-3 sm:grid-cols-2">
              <label>
                Display name
                <input value={editName} onChange={(e) => setEditName(e.target.value)} required disabled={!canManage} />
              </label>
              <label>
                Code
                <input value={item.code} readOnly />
              </label>
              <label>
                Malaysia desk mode
                <select
                  className="select-input"
                  value={editMode}
                  onChange={(e) => setEditMode(e.target.value)}
                  disabled={!canManage}
                >
                  {BSAS_MODE_ORDER.map((id) => (
                    <option key={id} value={id}>
                      {getBsasMode(id).label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Tenant status
                <select
                  value={editActive ? "active" : "suspended"}
                  onChange={(e) => setEditActive(e.target.value === "active")}
                  disabled={!canManage}
                >
                  <option value="active">Active</option>
                  <option value="suspended">Suspended</option>
                </select>
              </label>
              <label>
                Maker-checker steps
                <input
                  value={editSteps}
                  onChange={(e) => setEditSteps(e.target.value)}
                  disabled={!canManage}
                />
              </label>
              <label>
                Approval limit
                <input
                  value={editLimit}
                  onChange={(e) => setEditLimit(e.target.value)}
                  placeholder="Unlimited if blank"
                  disabled={!canManage}
                />
              </label>
              <label>
                Billing fee (bps)
                <input value={editFeeBps} onChange={(e) => setEditFeeBps(e.target.value)} disabled={!canManage} />
              </label>
            </div>
            {canManage ? (
              <div className="flex flex-wrap gap-2">
                <button type="submit" className="btn btn-primary" disabled={busy}>
                  {busy ? "Saving…" : "Save changes"}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => navigate("/institutions")}>
                  Back
                </button>
              </div>
            ) : (
              <Link className="btn btn-secondary btn-sm" to="/institutions">
                Back
              </Link>
            )}
          </form>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Audit trail</h2>
              <p className="muted m-0 text-sm">
                Grouped ops for this tenant ·{" "}
                <Link className="text-primary hover:underline" to={`/audit?institution=${item.id}`}>
                  Full feed
                </Link>
              </p>
            </div>
          </div>
          {auditGroups.length === 0 ? (
            <p className="muted text-sm">No audit events yet.</p>
          ) : (
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {auditGroups.slice(0, 12).map((group) => {
                const last = group.events[group.events.length - 1];
                return (
                  <li key={group.group_id} className="rounded-sm border border-border/80 bg-surface-elevated px-3 py-2">
                    <div className="text-sm font-semibold text-foreground">
                      {last?.action || group.action_group}
                    </div>
                    <div className="meta">
                      {group.action_group}
                      {group.ended_at ? ` · ${new Date(group.ended_at).toLocaleString()}` : null}
                      {group.events.length > 1 ? ` · ${group.events.length} events` : null}
                    </div>
                    {last?.details ? <div className="mt-1 text-xs text-muted">{last.details}</div> : null}
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
    </PageShell>
  );
}
