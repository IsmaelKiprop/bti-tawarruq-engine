import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Institution } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { IconManage } from "../components/icons";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import { lifecycleLabel } from "../config/fiKyc";
import { getBsasMode } from "../config/institutions";

const LIFECYCLE_FILTERS = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "draft", label: "Draft" },
  { value: "pending_approval", label: "Pending approval" },
  { value: "dormant", label: "Dormant" },
  { value: "deactivated", label: "Deactivated" },
];

export function InstitutionsPage() {
  const { user } = useAuth();
  const canManage = user?.role === "platform_admin" || Boolean(user?.permissions.includes("manage_institutions"));
  const canOnboard =
    canManage || user?.role === "bti_ops" || Boolean(user?.permissions.includes("write_bti_ops"));

  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [query, setQuery] = useState("");
  const [lifecycle, setLifecycle] = useState("all");
  const [busyId, setBusyId] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setInstitutions(await api.listInstitutions());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load institutions");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return institutions.filter((item) => {
      const status = item.lifecycle_status || (item.active === false ? "deactivated" : "active");
      if (lifecycle !== "all" && status !== lifecycle) return false;
      if (!q) return true;
      return [item.name, item.code, status, item.bsas_mode].filter(Boolean).join(" ").toLowerCase().includes(q);
    });
  }, [institutions, query, lifecycle]);

  async function onDecide(id: string, decision: "approve" | "return") {
    setBusyId(id);
    setError("");
    setMessage("");
    try {
      const done = await api.decideInstitutionOnboarding(id, { decision });
      setMessage(
        decision === "approve"
          ? `${done.name} is active. Invite its FI Admin from Users.`
          : `${done.name} was returned to draft.`,
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Decision failed");
    } finally {
      setBusyId("");
    }
  }

  return (
    <PageShell wide>
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="m-0 text-lg font-semibold">Institutions</h2>
          <p className="muted m-0 mt-1 text-sm">
            Customer financial institutions. Onboarding is a separate wizard. Engine settings stay on Manage.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex min-w-[10rem] flex-col gap-1 text-xs uppercase tracking-wide text-muted">
            Search
            <input
              className="rounded-sm border border-border bg-surface-elevated px-2.5 py-1.5 text-sm normal-case tracking-normal text-foreground"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Name, code…"
            />
          </label>
          <label className="flex min-w-[10rem] flex-col gap-1 text-xs uppercase tracking-wide text-muted">
            Lifecycle
            <select
              className="rounded-sm border border-border bg-surface-elevated px-2.5 py-1.5 text-sm normal-case tracking-normal text-foreground"
              value={lifecycle}
              onChange={(e) => setLifecycle(e.target.value)}
            >
              {LIFECYCLE_FILTERS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          {canOnboard ? (
            <Link className="btn btn-primary btn-sm" to="/institutions/onboard">
              Onboard financial institution
            </Link>
          ) : null}
        </div>
      </header>

      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Directory</h2>
            <p className="muted m-0 text-sm">
              {filtered.length} of {institutions.length} customer institutions
            </p>
          </div>
        </div>
        {loading ? (
          <LoadingPanel rows={4} />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No customer institutions"
            description="Onboard a bank, SACCO, or other financial institution to start this book."
            action={
              canOnboard ? (
                <Link className="btn btn-primary btn-sm" to="/institutions/onboard">
                  Onboard financial institution
                </Link>
              ) : undefined
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Code</th>
                  <th>Engine settings</th>
                  <th>Lifecycle</th>
                  <th className="w-[1%]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => {
                  const status = item.lifecycle_status || (item.active === false ? "deactivated" : "active");
                  return (
                    <tr key={item.id}>
                      <td>
                        <div className="font-medium">{item.name}</div>
                        <div className="meta">{new Date(item.created_at).toLocaleDateString()}</div>
                      </td>
                      <td>
                        <code>{item.code}</code>
                      </td>
                      <td className="text-sm text-muted">{getBsasMode(item.bsas_mode).label}</td>
                      <td>{lifecycleLabel(status, item.active)}</td>
                      <td>
                        <div className="flex flex-wrap items-center gap-1.5">
                          {canOnboard && (status === "draft" || status === "pending_approval") ? (
                            <Link className="btn btn-secondary btn-sm" to={`/institutions/${item.id}/onboard`}>
                              Resume KYC
                            </Link>
                          ) : (
                            <Link className="btn btn-secondary btn-sm" to={`/institutions/${item.id}/onboard`}>
                              Profile
                            </Link>
                          )}
                          {canManage && status === "pending_approval" ? (
                            <>
                              <button
                                type="button"
                                className="btn btn-primary btn-sm"
                                disabled={busyId === item.id}
                                onClick={() => void onDecide(item.id, "approve")}
                              >
                                Approve
                              </button>
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                disabled={busyId === item.id}
                                onClick={() => void onDecide(item.id, "return")}
                              >
                                Return
                              </button>
                            </>
                          ) : null}
                          {canManage ? (
                            <Link
                              to={`/institutions/${item.id}`}
                              className="icon-btn"
                              aria-label={`Manage ${item.name}`}
                              title="Engine settings"
                            >
                              <IconManage size={16} />
                            </Link>
                          ) : null}
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
