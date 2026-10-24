import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Institution } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { IconManage } from "../components/icons";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import { BSAS_MODE_ORDER, getBsasMode } from "../config/institutions";

function formatApprovalSteps(raw?: string | null) {
  const parts = (raw || "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  return parts.length ? parts.join(", ") : "None";
}

export function InstitutionsPage() {
  const { user } = useAuth();
  const canManage = user?.role === "platform_admin" || Boolean(user?.permissions.includes("manage_institutions"));

  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [createdId, setCreatedId] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [query, setQuery] = useState("");

  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [bsasMode, setBsasMode] = useState("manual_bridge");
  const [createLimit, setCreateLimit] = useState("");
  const [createSteps, setCreateSteps] = useState("murabaha,liquidation,disbursement");
  const [busy, setBusy] = useState(false);

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
    if (!q) return institutions;
    return institutions.filter((item) =>
      [item.name, item.code, item.bsas_mode, item.approval_steps].filter(Boolean).join(" ").toLowerCase().includes(q),
    );
  }, [institutions, query]);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    if (!canManage) return;
    setBusy(true);
    setError("");
    setMessage("");
    setCreatedId("");
    try {
      const created = await api.createInstitution({
        name: name.trim(),
        code: code.trim().toUpperCase(),
        bsas_mode: bsasMode,
        approval_limit_amount: createLimit.trim() || null,
        approval_steps: createSteps.trim() || "murabaha,liquidation,disbursement",
      });
      setCreatedId(created.id);
      setMessage(`${created.name} (${created.code}) registered.`);
      setName("");
      setCode("");
      setCreateLimit("");
      setCreateSteps("murabaha,liquidation,disbursement");
      setCreateOpen(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create institution");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell wide>
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="m-0 text-lg font-semibold">Institutions</h2>
          <p className="muted m-0 mt-1 text-sm">
            {filtered.length} of {institutions.length} client banks / SACCOs
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex min-w-[12rem] flex-col gap-1 text-xs uppercase tracking-wide text-muted">
            Search
            <input
              className="rounded-sm border border-border bg-surface-elevated px-2.5 py-1.5 text-sm normal-case tracking-normal text-foreground"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Name, code…"
            />
          </label>
          {canManage ? (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => setCreateOpen((open) => !open)}
              aria-expanded={createOpen}
            >
              {createOpen ? "Hide register" : "Register institution"}
            </button>
          ) : null}
        </div>
      </header>

      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}
      {createdId ? (
        <div className="flex flex-wrap gap-2">
          <Link className="btn btn-primary btn-sm" to={`/institutions/${createdId}`}>
            Manage institution
          </Link>
          <Link className="btn btn-secondary btn-sm" to={`/integrations?institution=${createdId}`}>
            Integrations
          </Link>
          <Link className="btn btn-secondary btn-sm" to={`/users?institution=${createdId}`}>
            Users
          </Link>
        </div>
      ) : null}

      {createOpen ? (
        <section className="panel">
          <h2>Register institution</h2>
          {!canManage ? (
            <Alert tone="error">Only platform admins can register institutions.</Alert>
          ) : (
            <form className="grid-2" onSubmit={onCreate}>
              <label>
                Display name
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Mwalimu National SACCO"
                  required
                />
              </label>
              <label>
                Institution code
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="MWALIMU"
                  required
                />
              </label>
              <label>
                Malaysia desk mode
                <select className="select-input" value={bsasMode} onChange={(e) => setBsasMode(e.target.value)}>
                  {BSAS_MODE_ORDER.map((id) => (
                    <option key={id} value={id}>
                      {getBsasMode(id).label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Maker-checker steps
                <input
                  value={createSteps}
                  onChange={(e) => setCreateSteps(e.target.value)}
                  placeholder="murabaha,liquidation,disbursement"
                />
              </label>
              <label>
                Approval limit (optional)
                <input
                  value={createLimit}
                  onChange={(e) => setCreateLimit(e.target.value)}
                  placeholder="e.g. 500000"
                />
              </label>
              <button type="submit" className="btn btn-primary" disabled={busy}>
                {busy ? "Creating…" : "Create institution"}
              </button>
            </form>
          )}
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
          <EmptyState title="No institutions" description="Register a bank or SACCO, or clear the search." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Code</th>
                  <th>Malaysia desk</th>
                  <th>Maker-checker</th>
                  <th>Limit</th>
                  <th>Status</th>
                  <th className="w-[1%]">Manage</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <div className="font-medium">{item.name}</div>
                      <div className="meta">{new Date(item.created_at).toLocaleDateString()}</div>
                    </td>
                    <td>
                      <code>{item.code}</code>
                    </td>
                    <td>{getBsasMode(item.bsas_mode).label}</td>
                    <td className="text-sm text-muted">{formatApprovalSteps(item.approval_steps)}</td>
                    <td>{item.approval_limit_amount || "—"}</td>
                    <td>{item.active === false ? "Suspended" : "Active"}</td>
                    <td>
                      <Link
                        to={`/institutions/${item.id}`}
                        className="icon-btn"
                        aria-label={`Manage ${item.name}`}
                        title="Manage institution"
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
