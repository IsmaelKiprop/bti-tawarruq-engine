import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Application } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ApplicationExplain } from "../components/ApplicationExplain";
import { Alert, EmptyState, LoadingPanel, PageShell, statusBadgeClass } from "../components/PageShell";
import { APPLICATION_STEP_GUIDE, previewApplicationDeal } from "../config/applicationOps";
import { getRoleProfile } from "../config/roles";
import { displayCustomerName, formatMoney, formatWorkflowLabel } from "../lib/display";
import "../components/ui.css";

export function ApplicationsListPage() {
  const { user, authEnabled } = useAuth();
  const profile = getRoleProfile(user?.role);
  const canWrite = !authEnabled || !user || profile.showWriteActions;
  const [items, setItems] = useState<Application[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [confirmDeleteId, setConfirmDeleteId] = useState("");
  const [busyId, setBusyId] = useState("");

  useEffect(() => {
    api
      .listApplications()
      .then(setItems)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function onDelete(item: Application) {
    if (confirmDeleteId !== item.id) {
      setConfirmDeleteId(item.id);
      setMessage("");
      return;
    }
    setBusyId(item.id);
    setError("");
    setMessage("");
    try {
      await api.deleteApplication(item.id);
      setItems((current) => current.filter((row) => row.id !== item.id));
      setConfirmDeleteId("");
      setMessage(`${displayCustomerName(item)} (${item.customer_ref}) was deleted.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete application");
    } finally {
      setBusyId("");
    }
  }

  return (
    <PageShell wide>
      <div className="page-grid">
        <div className="span-2">
          <ApplicationExplain />
        </div>
        <section className="panel span-2">
          <h2>How applications work</h2>
          <p className="muted">
            This book is the customer side. Open a row for the locked offer, or start a new request
            from a customer already on Customers. Murabaha on this list is a 5% preview until the
            offer locks on the detail page.
          </p>
          <ol className="flow-list numbered">
            {APPLICATION_STEP_GUIDE.map((step) => (
              <li key={step.n}>
                <strong>
                  {step.n}. {step.title}.
                </strong>{" "}
                {step.body}
              </li>
            ))}
          </ol>
          <p className="meta">
            Amount is commodity cost. Murabaha is cost plus profit. The customer repays that total,
            not the float or the palm oil.
          </p>
        </section>
      <section className="panel span-2">
        <div className="table-toolbar">
          <div>
            <h2>All applications</h2>
            <p className="muted">
              {profile.scope === "platform"
                ? "Financing requests across institutions. Amount is cost. Murabaha is what the customer owes."
                : "Financing requests for this institution. Amount is cost. Murabaha is what the customer owes."}
            </p>
          </div>
          {canWrite ? (
            <Link className="btn btn-primary btn-sm" to="/applications/new">
              New application
            </Link>
          ) : null}
        </div>

        {error && <Alert tone="error">{error}</Alert>}
        {message && <Alert tone="success">{message}</Alert>}

        {loading ? (
          <LoadingPanel rows={5} />
        ) : items.length === 0 && !error ? (
          <EmptyState
            title="No applications yet"
            description="Create your first financing application to start a Tawarruq journey."
            action={
              canWrite ? (
                <Link className="btn btn-primary btn-sm" to="/applications/new">
                  Create application
                </Link>
              ) : undefined
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                  <tr>
                  <th>Customer</th>
                  <th>Reference</th>
                  {profile.scope === "platform" ? <th>Institution</th> : null}
                  <th>Cost / Murabaha</th>
                  <th>Term</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td data-label="Customer">
                      <Link className="row-link" to={`/applications/${item.id}`}>
                        {displayCustomerName(item)}
                      </Link>
                    </td>
                    <td data-label="Reference" className="mono">
                      {item.customer_ref}
                    </td>
                    {profile.scope === "platform" ? (
                      <td data-label="Institution">{item.institution_name || "Institution"}</td>
                    ) : null}
                    <ApplicationCostCell item={item} />
                    <td data-label="Term">{item.term_months}m</td>
                    <td data-label="Status">
                      <span className={statusBadgeClass(item.status)}>
                        {formatWorkflowLabel(item.status, item.current_phase)}
                      </span>
                    </td>
                    <td className="muted" data-label="Created">
                      {new Date(item.created_at).toLocaleString()}
                    </td>
                    <td data-label="Actions">
                      <div className="cell-actions">
                        <Link className="btn btn-secondary btn-sm" to={`/applications/${item.id}`}>
                          Open
                        </Link>
                        <Link className="btn btn-secondary btn-sm" to={`/customer/${encodeURIComponent(item.customer_ref)}`}>
                          Journey
                        </Link>
                        {canWrite ? (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            disabled={busyId === item.id}
                            onClick={() => void onDelete(item)}
                          >
                            {confirmDeleteId === item.id ? "Confirm delete" : "Delete"}
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      </div>
    </PageShell>
  );
}

function ApplicationCostCell({ item }: { item: Application }) {
  const deal = previewApplicationDeal({
    amount: item.amount_requested,
    termMonths: item.term_months,
  });
  return (
    <td data-label="Cost / Murabaha">
      <div>{formatMoney(item.currency, deal.cost)}</div>
      <div className="meta">
        Murabaha {formatMoney(item.currency, deal.total)} · {deal.termMonths} ×{" "}
        {formatMoney(item.currency, deal.installment)}
      </div>
    </td>
  );
}
