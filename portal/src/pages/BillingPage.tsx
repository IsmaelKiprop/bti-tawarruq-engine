import { FormEvent, useEffect, useState } from "react";
import { api, type BillingInvoice, type Institution } from "../api/client";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";

export function BillingPage() {
  const [invoices, setInvoices] = useState<BillingInvoice[]>([]);
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [institutionId, setInstitutionId] = useState("");
  const [periodStart, setPeriodStart] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10));
  const [periodEnd, setPeriodEnd] = useState(() => new Date().toISOString().slice(0, 10));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [inv, inst] = await Promise.all([api.listBillingInvoices(), api.listInstitutions().catch(() => [] as Institution[])]);
      setInvoices(inv);
      setInstitutions(inst);
      if (!institutionId && inst[0]?.id) setInstitutionId(inst[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load billing");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function onGenerate(event: FormEvent) {
    event.preventDefault();
    if (!institutionId) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const created = await api.generateInvoice({
        institution_id: institutionId,
        period_start: new Date(periodStart).toISOString(),
        period_end: new Date(`${periodEnd}T23:59:59Z`).toISOString(),
      });
      setMessage(`Invoice ${created.id.slice(0, 8)} issued for ${created.fee_amount} (${created.fee_bps} bps).`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invoice failed");
    } finally {
      setBusy(false);
    }
  }

  async function markPaid(id: string) {
    setBusy(true);
    setError("");
    try {
      await api.payInvoice(id);
      setMessage("Invoice marked paid.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell wide>
      <header className="page-header">
        <h1>Billing & fees</h1>
        <p className="muted">
          Usage invoices are the disbursed volume in the period times the institution fee in basis points.
          Trade execution stays out of scope for Finance.
        </p>
      </header>
      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}

      <section className="panel">
        <h2>Generate invoice</h2>
        <form className="grid-2" onSubmit={onGenerate}>
          <label>
            Institution
            <select value={institutionId} onChange={(event) => setInstitutionId(event.target.value)} required>
              {institutions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} ({item.billing_fee_bps ?? 25} bps)
                </option>
              ))}
            </select>
          </label>
          <label>
            Period start
            <input type="date" value={periodStart} onChange={(event) => setPeriodStart(event.target.value)} required />
          </label>
          <label>
            Period end
            <input type="date" value={periodEnd} onChange={(event) => setPeriodEnd(event.target.value)} required />
          </label>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? "Working…" : "Issue invoice"}
          </button>
        </form>
      </section>

      <section className="panel">
        <h2>Invoices</h2>
        {loading ? (
          <LoadingPanel rows={4} />
        ) : invoices.length === 0 ? (
          <EmptyState title="No invoices" description="Issue a period invoice from disbursed volume above." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Institution</th>
                  <th>Period</th>
                  <th>Volume</th>
                  <th>Fee</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((item) => (
                  <tr key={item.id}>
                    <td>{item.institution_name || item.institution_id}</td>
                    <td>
                      {item.period_start?.slice(0, 10)} → {item.period_end?.slice(0, 10)}
                    </td>
                    <td>
                      {item.currency} {item.volume_amount} ({item.transaction_count} txns)
                    </td>
                    <td>
                      {item.currency} {item.fee_amount} at {item.fee_bps} bps
                    </td>
                    <td>{item.status}</td>
                    <td>
                      {item.status !== "paid" ? (
                        <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => void markPaid(item.id)}>
                          Mark paid
                        </button>
                      ) : (
                        item.paid_at?.slice(0, 10)
                      )}
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
