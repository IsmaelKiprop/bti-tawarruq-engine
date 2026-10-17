import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, RepaymentBoardItem } from "../api/client";
import { RepaymentTape } from "../components/DealTape";
import { HowItWorks, PageExplain } from "../components/PageExplain";
import { Alert, EmptyState, LoadingPanel, PageShell, statusBadgeClass } from "../components/PageShell";
import { HOW_IT_WORKS, PAGE_EXPLAINS } from "../config/pageExplainers";
import { formatMoney } from "../lib/display";
import "../components/ui.css";

export function RepaymentsPage() {
  const [items, setItems] = useState<RepaymentBoardItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [filter, setFilter] = useState<"all" | "due" | "overdue" | "paid">("all");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setItems(await api.listKenyaOpsRepayments());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load repayments");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const visible = items.filter((item) => {
    if (filter === "all") return true;
    if (filter === "paid") return item.status === "paid";
    if (filter === "overdue") return item.status === "overdue";
    return item.status !== "paid";
  });

  async function collect(id: string) {
    setBusyId(id);
    setError("");
    setMessage("");
    try {
      await api.collectKenyaRepayment(id);
      setMessage("Collection initiated / installment updated.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Collection failed");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <PageShell wide>
      <PageExplain content={PAGE_EXPLAINS["/repayments"]} />
      <HowItWorks content={HOW_IT_WORKS["/repayments"]} />
      <RepaymentTape items={items} />
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Repayment board</h2>
            <p className="muted">Collect deferred Murabaha instalments after disbursement</p>
          </div>
          <button type="button" className="btn btn-secondary btn-sm" onClick={load}>
            Refresh
          </button>
        </div>

        <div className="queue-filters">
          {(
            [
              ["all", "All"],
              ["due", "Outstanding"],
              ["overdue", "Overdue"],
              ["paid", "Paid"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`chip${filter === id ? " active" : ""}`}
              onClick={() => setFilter(id)}
            >
              {label}
            </button>
          ))}
        </div>

        {error && <Alert tone="error">{error}</Alert>}
        {message && <Alert tone="success">{message}</Alert>}

        {loading ? (
          <LoadingPanel rows={6} />
        ) : visible.length === 0 ? (
          <EmptyState
            title="No installments"
            description="Repayment schedules appear after wallet disbursement completes."
          />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>#</th>
                  <th>Due</th>
                  <th>Amount</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {visible.map((item) => (
                  <tr key={item.installment_id}>
                    <td data-label="Customer">
                      <Link className="row-link" to={`/kenya?case=${item.application_id}`}>
                        {item.customer_name}
                      </Link>
                      <div className="meta">{item.customer_ref}</div>
                    </td>
                    <td data-label="Installment">{item.installment_number}</td>
                    <td data-label="Due">
                      {item.due_date ? new Date(item.due_date).toLocaleDateString() : "—"}
                    </td>
                    <td data-label="Amount">{formatMoney("KES", item.amount)}</td>
                    <td data-label="Status">
                      <span className={statusBadgeClass(item.status)}>{item.status}</span>
                    </td>
                    <td>
                      {item.status !== "paid" && (
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          disabled={busyId === item.installment_id}
                          onClick={() => collect(item.installment_id)}
                        >
                          {busyId === item.installment_id ? "…" : "Collect"}
                        </button>
                      )}
                      {item.payment_ref && <span className="meta mono">{item.payment_ref}</span>}
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
