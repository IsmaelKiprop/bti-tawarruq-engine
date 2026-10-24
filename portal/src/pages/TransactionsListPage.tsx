import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Transaction } from "../api/client";
import { DealTape } from "../components/DealTape";
import { Alert, EmptyState, LoadingPanel, PageShell, statusBadgeClass } from "../components/PageShell";

export function TransactionsListPage() {
  const [items, setItems] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .listTransactions()
      .then(setItems)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load transactions"))
      .finally(() => setLoading(false));
  }, []);

  const preview = items[0];

  return (
    <PageShell wide>
      {error ? <Alert tone="error">{error}</Alert> : null}
      {preview ? (
        <DealTape
          amount={(preview as { amount?: string }).amount || "0"}
          termMonths={1}
          currency={(preview as { currency?: string }).currency || "KES"}
        />
      ) : null}
      <section className="panel">
        <h2>Commodity transactions</h2>
        {loading ? (
          <LoadingPanel rows={5} />
        ) : items.length === 0 ? (
          <EmptyState title="No transactions" description="Commodity legs appear here after Kenya or Malaysia desks start." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Status</th>
                  <th>Mode</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td className="mono">{item.id}</td>
                    <td>
                      <span className={statusBadgeClass(item.status)}>{item.status}</span>
                    </td>
                    <td>{(item as { mode?: string }).mode || (item as { track?: string }).track || "—"}</td>
                    <td>
                      <Link className="btn btn-secondary btn-sm" to={`/transactions/${item.id}`}>
                        Open
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
