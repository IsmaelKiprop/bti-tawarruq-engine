import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Institution } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { HowItWorks, PageExplain } from "../components/PageExplain";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import { BSAS_MODE_ORDER, getBsasMode } from "../config/institutions";
import { HOW_IT_WORKS, INSTITUTION_LIMIT_FIELD, MAKER_CHECKER_STEPS_FIELD, PAGE_EXPLAINS } from "../config/pageExplainers";
import "../components/ui.css";

function formatApprovalSteps(raw?: string | null) {
  const parts = (raw || "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  return parts.length ? parts.join(", ") : "None (runs immediately)";
}

function BsasModeField({
  value,
  onChange,
}: {
  value: string;
  onChange: (mode: string) => void;
}) {
  const mode = getBsasMode(value);
  return (
    <label>
      Malaysia desk mode
      <select className="select-input" value={value} onChange={(event) => onChange(event.target.value)}>
        {BSAS_MODE_ORDER.map((id) => (
          <option key={id} value={id}>
            {getBsasMode(id).label}
          </option>
        ))}
      </select>
      <p className="muted">{mode.when}</p>
    </label>
  );
}

export function InstitutionsPage() {
  const { user } = useAuth();
  const canManage = user?.role === "platform_admin" || Boolean(user?.permissions.includes("manage_institutions"));

  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [createdId, setCreatedId] = useState("");

  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [bsasMode, setBsasMode] = useState("manual_bridge");
  const [createLimit, setCreateLimit] = useState("");
  const [createSteps, setCreateSteps] = useState("murabaha,liquidation,disbursement");
  const [busy, setBusy] = useState(false);

  const [editing, setEditing] = useState<Institution | null>(null);
  const [editName, setEditName] = useState("");
  const [editMode, setEditMode] = useState("manual_bridge");
  const [editActive, setEditActive] = useState(true);
  const [editSteps, setEditSteps] = useState("murabaha,liquidation,disbursement");
  const [editLimit, setEditLimit] = useState("");
  const [editFeeBps, setEditFeeBps] = useState("25");
  const [confirmDeleteId, setConfirmDeleteId] = useState("");
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
    load();
  }, []);

  function isProtected(item: Institution) {
    return item.code.toUpperCase() === "DEFAULT";
  }

  function startEdit(item: Institution) {
    setEditing(item);
    setEditName(item.name);
    setEditMode(item.bsas_mode);
    setEditActive(item.active !== false);
    setEditSteps(item.approval_steps || "murabaha,liquidation,disbursement");
    setEditLimit(item.approval_limit_amount || "");
    setEditFeeBps(String(item.billing_fee_bps ?? 25));
    setConfirmDeleteId("");
    setCreatedId("");
    setError("");
    setMessage("");
  }

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
      setMessage(`${created.name} (${created.code}) registered. Next: configure integrations and create ops users.`);
      setName("");
      setCode("");
      setCreateLimit("");
      setCreateSteps("murabaha,liquidation,disbursement");
      setInstitutions(await api.listInstitutions());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create institution");
    } finally {
      setBusy(false);
    }
  }

  async function onUpdate(event: FormEvent) {
    event.preventDefault();
    if (!canManage || !editing) return;
    setBusyId(editing.id);
    setError("");
    setMessage("");
    try {
      const updated = await api.updateInstitution(editing.id, {
        name: editName.trim(),
        bsas_mode: editMode,
        active: editActive,
        approval_steps: editSteps,
        approval_limit_amount: editLimit.trim() || null,
        billing_fee_bps: Number(editFeeBps),
      });
      setEditing(updated);
      setMessage(`Updated ${updated.name} (${updated.code}).`);
      setInstitutions(await api.listInstitutions());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update institution");
    } finally {
      setBusyId("");
    }
  }

  async function onDelete(item: Institution) {
    if (!canManage || isProtected(item)) return;
    if (confirmDeleteId !== item.id) {
      setConfirmDeleteId(item.id);
      return;
    }
    setBusyId(item.id);
    setError("");
    setMessage("");
    try {
      await api.deleteInstitution(item.id);
      if (editing?.id === item.id) setEditing(null);
      if (createdId === item.id) setCreatedId("");
      setConfirmDeleteId("");
      setMessage(`${item.name} was deleted.`);
      setInstitutions(await api.listInstitutions());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete institution");
    } finally {
      setBusyId("");
    }
  }

  return (
    <PageShell wide>
      <div className="page-grid">
        <div className="span-2">
          <PageExplain content={PAGE_EXPLAINS["/institutions"]} />
        </div>
        <HowItWorks content={HOW_IT_WORKS["/institutions"]} />
        <section className="panel">
          {editing ? (
            <>
              <h2>Update {editing.name}</h2>
              <p className="muted">
                Change how this bank appears, its Malaysia desk, dual-control steps, or amount cap. The
                code <code>{editing.code}</code> stays the same because deals and users already point to
                it.
              </p>
              <form className="stack-form" onSubmit={onUpdate}>
                <label>
                  Display name
                  <input value={editName} onChange={(e) => setEditName(e.target.value)} required />
                  <span className="meta">Shown on dashboards, journeys, and certificates.</span>
                </label>
                <BsasModeField value={editMode} onChange={setEditMode} />
                <label>
                  Tenant status
                  <select value={editActive ? "active" : "suspended"} onChange={(event) => setEditActive(event.target.value === "active")}>
                    <option value="active">Active</option>
                    <option value="suspended">Suspended</option>
                  </select>
                </label>
                  <label>
                    Maker-checker steps
                    <input value={editSteps} onChange={(event) => setEditSteps(event.target.value)} />
                    <span className="meta">{MAKER_CHECKER_STEPS_FIELD}</span>
                  </label>
                <label>
                  Approval limit
                  <input value={editLimit} onChange={(event) => setEditLimit(event.target.value)} placeholder="Unlimited if blank" />
                  <span className="meta">{INSTITUTION_LIMIT_FIELD}</span>
                </label>
                <label>
                  Billing fee (bps)
                  <input value={editFeeBps} onChange={(event) => setEditFeeBps(event.target.value)} />
                  <span className="meta">Buruuj usage fee in basis points. 25 means 0.25 percent.</span>
                </label>
                <div className="actions">
                  <button className="btn btn-primary btn-sm" type="submit" disabled={busyId === editing.id}>
                    Save changes
                  </button>
                  <button className="btn btn-secondary btn-sm" type="button" onClick={() => setEditing(null)}>
                    Cancel
                  </button>
                </div>
              </form>
            </>
          ) : (
            <>
              <h2>Register institution</h2>
              <p className="muted">
                Add a client bank or SACCO. Set dual control and the bank-wide amount cap here so testers
                know which steps wait for an FI Approver. After create, open Integrations, then invite FI
                Admin on Users.
              </p>
              {!canManage ? (
                <Alert tone="error">Only platform admins can register institutions.</Alert>
              ) : (
                <form className="stack-form" onSubmit={onCreate}>
                  <label>
                    Display name
                    <input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Mwalimu National SACCO"
                      required
                    />
                    <span className="meta">How the bank appears on dashboards and certificates.</span>
                  </label>
                  <label>
                    Institution code
                    <input
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      placeholder="MWALIMU"
                      required
                    />
                    <span className="meta">
                      Short unique ID for APIs and audit. Letters and numbers only, for example MWALIMU or DIB001.
                    </span>
                  </label>
                  <BsasModeField value={bsasMode} onChange={setBsasMode} />
                  <label>
                    Maker-checker steps
                    <input
                      value={createSteps}
                      onChange={(e) => setCreateSteps(e.target.value)}
                      placeholder="murabaha,liquidation,disbursement"
                    />
                    <span className="meta">{MAKER_CHECKER_STEPS_FIELD}</span>
                  </label>
                  <label>
                    Approval limit (optional)
                    <input
                      value={createLimit}
                      onChange={(e) => setCreateLimit(e.target.value)}
                      placeholder="e.g. 500000"
                    />
                    <span className="meta">{INSTITUTION_LIMIT_FIELD}</span>
                  </label>
                  <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>
                    {busy ? "Creating…" : "Create institution"}
                  </button>
                </form>
              )}
            </>
          )}
        </section>

        <section className="panel">
          <h2>Dual control on this book</h2>
          <p className="muted">
            Maker-checker steps are the deal actions that wait for a second person. FI Operations starts
            the step. It queues. FI Approver opens Approvals and approves or rejects. The same person
            cannot do both.
          </p>
          <ul className="meta-list">
            <li>
              <strong>murabaha.</strong> Sale of the commodity to the customer.
            </li>
            <li>
              <strong>liquidation.</strong> Independent spot sale after wakala.
            </li>
            <li>
              <strong>disbursement.</strong> Paying out after the sale confirms.
            </li>
          </ul>
          <p className="meta">
            Keep all three for full dual control. Remove a word if that step should execute as soon as
            FI Operations clicks it. API keys and the mobile app skip the queue.
          </p>
          <h3>Approval limit</h3>
          <p className="muted">
            This is the bank-wide cap. An FI Approver can also have a personal cap on Users. The engine
            uses the lower of the two. Example: bank 500000, approver 100000. They can approve up to
            100000. Leave both blank for no amount cap.
          </p>
          <h3>Malaysia desk modes</h3>
          <ul className="meta-list">
            {BSAS_MODE_ORDER.map((id) => {
              const item = getBsasMode(id);
              return (
                <li key={id}>
                  <strong>{item.label}.</strong> {item.when}
                </li>
              );
            })}
          </ul>
          <p className="meta">
            This mode is the default for Malaysia. Kenya float purchase uses Agent Dealers and
            Integrations, not this field.
          </p>
          {createdId ? (
            <div className="inline-actions" style={{ marginTop: "1rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              <Link className="btn btn-primary btn-sm" to={`/integrations?institution=${createdId}`}>
                Configure integrations
              </Link>
              <Link className="btn btn-secondary btn-sm" to={`/users?institution=${createdId}`}>
                Create ops users
              </Link>
            </div>
          ) : null}
        </section>

        {(error || message) && (
          <div className="span-2">
            {error ? <Alert tone="error">{error}</Alert> : null}
            {message ? <Alert tone="success">{message}</Alert> : null}
          </div>
        )}

        <section className="panel span-2">
          <h2>Institutions</h2>
          {loading ? (
            <LoadingPanel rows={4} />
          ) : institutions.length === 0 ? (
            <EmptyState title="No institutions yet" description="Register the first bank or SACCO above." />
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Code</th>
                    <th>Malaysia desk</th>
                    <th>Maker-checker</th>
                    <th>Approval limit</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {institutions.map((item) => {
                    const selected = editing?.id === item.id || createdId === item.id;
                    const busyRow = busyId === item.id;
                    const protectedRow = isProtected(item);
                    return (
                      <tr key={item.id} className={selected ? "is-selected" : undefined}>
                        <td data-label="Name">
                          {item.name}
                          {selected ? <span className="row-mark">This institution</span> : null}
                        </td>
                        <td data-label="Code">
                          <code>{item.code}</code>
                        </td>
                        <td data-label="Malaysia desk">{getBsasMode(item.bsas_mode).label}</td>
                        <td data-label="Maker-checker">{formatApprovalSteps(item.approval_steps)}</td>
                        <td data-label="Approval limit">{item.approval_limit_amount || "No cap"}</td>
                        <td data-label="Status">{item.active === false ? "Suspended" : "Active"}</td>
                        <td data-label="Created">{new Date(item.created_at).toLocaleString()}</td>
                        <td data-label="Actions">
                          <div className="cell-actions">
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
                                disabled={busyRow}
                                onClick={() => startEdit(item)}
                              >
                                Update
                              </button>
                            ) : null}
                            {canManage ? (
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                disabled={busyRow || protectedRow}
                                title={protectedRow ? "The default institution cannot be deleted" : undefined}
                                onClick={() => void onDelete(item)}
                              >
                                {confirmDeleteId === item.id ? "Confirm delete" : "Delete"}
                              </button>
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
      </div>
    </PageShell>
  );
}
