import { useEffect, useState } from "react";
import { api, type ReconciliationRow } from "../api/client";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import "../components/ui.css";

export function ReconciliationPage() {
  const [items, setItems] = useState<ReconciliationRow[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<Record<string, string>>({});

  async function load(status = filter) {
    setLoading(true);
    setError("");
    try {
      setItems(await api.listReconciliation(status || undefined));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load reconciliation");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function scan() {
    setBusy(true);
    setError("");
    try {
      const result = await api.scanReconciliation();
      setMessage(`Scan complete. ${result.created_or_updated} items created or refreshed.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setBusy(false);
    }
  }

  async function resolve(id: string, status: string) {
    setBusy(true);
    setError("");
    try {
      await api.resolveReconciliation(id, status, note[id]);
      setMessage(`Marked ${status}.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Resolve failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell wide>
      <header className="page-header">
        <h1>Reconciliation & settlement</h1>
        <p className="muted">
          Match commodity confirmations to disbursed amounts. Exceptions stay on the ledger with an
          auditable note.
        </p>
      </header>
      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}

      <section className="panel">
        <div className="actions">
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void scan()}>
            {busy ? "Working…" : "Scan trades vs settlement"}
          </button>
          <label>
            Status
            <select
              value={filter}
              onChange={(event) => {
                setFilter(event.target.value);
                void load(event.target.value);
              }}
            >
              <option value="">All</option>
              <option value="outstanding">Outstanding</option>
              <option value="mismatch">Mismatch</option>
              <option value="matched">Matched</option>
              <option value="exception">Exception</option>
            </select>
          </label>
        </div>
      </section>

      <section className="panel">
        {loading ? (
          <LoadingPanel rows={4} />
        ) : items.length === 0 ? (
          <EmptyState title="No items" description="Run a scan to compare completed trades with disbursements." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Transaction</th>
                  <th>Expected</th>
                  <th>Settled</th>
                  <th>Status</th>
                  <th>Note</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <code>{item.transaction_id.slice(0, 8)}</code>
                      <div className="meta">{item.institution_name}</div>
                    </td>
                    <td>
                      {item.currency} {item.expected_amount}
                    </td>
                    <td>
                      {item.currency} {item.settled_amount}
                    </td>
                    <td>{item.status}</td>
                    <td>
                      <input
                        value={note[item.id] || item.note || ""}
                        onChange={(event) => setNote((current) => ({ ...current, [item.id]: event.target.value }))}
                      />
                    </td>
                    <td>
                      <div className="cell-actions">
                        <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => void resolve(item.id, "matched")}>
                          Match
                        </button>
                        <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => void resolve(item.id, "exception")}>
                          Exception
                        </button>
                      </div>
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
