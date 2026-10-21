import { useEffect, useState } from "react";
import { api, type PendingApproval } from "../api/client";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import "../components/ui.css";

export function ApprovalsPage() {
  const [items, setItems] = useState<PendingApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busyId, setBusyId] = useState("");
  const [note, setNote] = useState<Record<string, string>>({});

  async function load() {
    setLoading(true);
    setError("");
    try {
      setItems(await api.listApprovals("pending"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load approvals");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function decide(id: string, action: "approve" | "reject") {
    setBusyId(id);
    setError("");
    setMessage("");
    try {
      if (action === "approve") await api.approvePending(id, note[id]);
      else await api.rejectPending(id, note[id] || "Rejected");
      setMessage(action === "approve" ? "Approved and executed." : "Rejected.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Decision failed");
    } finally {
      setBusyId("");
    }
  }

  return (
    <PageShell wide>
      <header className="page-header">
        <h1>Maker-checker approvals</h1>
        <p className="muted">
          FI Approvers authorize Murabaha, liquidation, and disbursement. You cannot approve a request you
          initiated, and amount limits on the user or institution are enforced.
        </p>
      </header>
      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}
      {loading ? (
        <LoadingPanel rows={4} />
      ) : items.length === 0 ? (
        <EmptyState title="No pending approvals" description="Queued commodity steps appear here for dual control." />
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Step</th>
                <th>Amount</th>
                <th>Application</th>
                <th>Note</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <strong>{item.step}</strong>
                    <div className="meta">{item.action}</div>
                  </td>
                  <td>
                    {item.amount ? `${item.currency} ${item.amount}` : "—"}
                  </td>
                  <td>
                    <code>{item.application_id || "—"}</code>
                  </td>
                  <td>
                    <input
                      value={note[item.id] || ""}
                      onChange={(event) => setNote((current) => ({ ...current, [item.id]: event.target.value }))}
                      placeholder="Decision note"
                    />
                  </td>
                  <td>
                    <div className="cell-actions">
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        disabled={busyId === item.id}
                        onClick={() => void decide(item.id, "approve")}
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        disabled={busyId === item.id}
                        onClick={() => void decide(item.id, "reject")}
                      >
                        Reject
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PageShell>
  );
}
