import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, Application, BusinessStatus, OfferSummary, ShariahAuditEntry, Transaction } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { DealTape } from "../components/DealTape";
import { Alert, LoadingPanel, PageShell, statusBadgeClass } from "../components/PageShell";
import { applicationUsesSpot } from "../config/applicationOps";
import { getRoleProfile } from "../config/roles";
import { formatMoney } from "../lib/display";

export function ApplicationDetailPage() {
  const { user, authEnabled } = useAuth();
  const profile = getRoleProfile(user?.role);
  const canWrite = !authEnabled || !user || profile.showWriteActions;
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [application, setApplication] = useState<Application | null>(null);
  const [business, setBusiness] = useState<BusinessStatus | null>(null);
  const [transaction, setTransaction] = useState<Transaction | null>(null);
  const [shariah, setShariah] = useState<ShariahAuditEntry[]>([]);
  const [offer, setOffer] = useState<OfferSummary | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function load() {
    if (!id) return;
    setLoading(true);
    try {
      const [app, biz, txns, audit, lockedOffer] = await Promise.all([
        api.getApplication(id),
        api.getBusinessStatus(id),
        api.listTransactions(),
        api.getShariahAudit(id).catch(() => [] as ShariahAuditEntry[]),
        api.getKenyaOffer(id).catch(() => null),
      ]);
      setApplication(app);
      setBusiness(biz);
      setTransaction(txns.find((t) => t.application_id === id) ?? null);
      setShariah(audit);
      setOffer(lockedOffer);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load application");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [id]);

  async function onDelete() {
    if (!id || !application) return;
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    setDeleting(true);
    setError("");
    try {
      await api.deleteApplication(id);
      navigate("/applications", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete application");
      setDeleting(false);
    }
  }

  async function runAction(action: () => Promise<unknown>, success: string) {
    setMessage("");
    setError("");
    try {
      await action();
      setMessage(success);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    }
  }

  if (loading && !application) {
    return (
      <PageShell wide>
        <section className="panel">
          <LoadingPanel rows={6} />
        </section>
      </PageShell>
    );
  }

  if (!application) {
    return (
      <PageShell>
        <Alert tone="error">{error || "Application not found"}</Alert>
      </PageShell>
    );
  }

  return (
    <PageShell wide>
      <div className="page-grid">
        <section className="panel span-2">
          <div className="panel-header">
            <div>
              <h2>{application.customer_ref}</h2>
              <p className="muted">{application.purpose}</p>
            </div>
            <span className={statusBadgeClass(application.status)}>{application.status}</span>
          </div>

          <p className="muted">
            Amount is commodity cost. Murabaha is cost plus profit. The customer still owes that
            total after disbursement, not the float or the palm oil.
          </p>
          <DealTape
            amount={application.amount_requested}
            termMonths={application.term_months}
            currency={application.currency || "KES"}
            includeSpot={applicationUsesSpot(application.currency)}
            offer={
              offer
                ? {
                    cost_price: offer.cost_price,
                    profit_amount: offer.profit_amount,
                    total_payable: offer.total_payable,
                  }
                : null
            }
          />
          <div className="info-grid">
            <div className="info-item">
              <span>Amount requested</span>
              <strong>{formatMoney(application.currency, application.amount_requested)}</strong>
            </div>
            <div className="info-item">
              <span>Term</span>
              <strong>{application.term_months} months</strong>
            </div>
            <div className="info-item">
              <span>Created</span>
              <strong>{new Date(application.created_at).toLocaleString()}</strong>
            </div>
            <div className="info-item">
              <span>Application ID</span>
              <strong className="mono">{application.id.slice(0, 12)}…</strong>
            </div>
          </div>

          {error && <Alert tone="error">{error}</Alert>}
          {message && <Alert tone="success">{message}</Alert>}

          <hr className="section-divider" />

          <p className="form-section-title">{canWrite ? "Workflow actions" : "Records"}</p>
          <div className="actions-row">
            {canWrite && application.status === "draft" && (
              <button
                className="btn btn-primary btn-sm"
                onClick={() => runAction(() => api.createOffer(id!), "Offer generated")}
              >
                Generate offer
              </button>
            )}
            {canWrite && application.status === "offer_pending" && (
              <button
                className="btn btn-primary btn-sm"
                onClick={() => runAction(() => api.acceptOffer(id!), "Offer accepted")}
              >
                Accept offer
              </button>
            )}
            {canWrite && application.status === "offer_accepted" && !transaction && (
              <button
                className="btn btn-primary btn-sm"
                onClick={() => runAction(() => api.createTransaction(id!), "Transaction started")}
              >
                Start transaction (mock)
              </button>
            )}
            {canWrite && business && !business.customer_sale_recorded && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => runAction(() => api.recordCustomerSale(id!), "Customer sale recorded")}
              >
                Step 7: Customer sale
              </button>
            )}
            {canWrite && business && !business.customer_agency_appointed && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => runAction(() => api.appointCustomerAgency(id!), "Agency appointed")}
              >
                Step 8: Customer agency
              </button>
            )}
            {canWrite && transaction?.status === "completed" && (
              <button
                className="btn btn-primary btn-sm"
                onClick={() =>
                  runAction(() => api.createDisbursement(id!, transaction.id), "Disbursement created")
                }
              >
                Disburse funds
              </button>
            )}
            {transaction && (
              <Link className="btn btn-secondary btn-sm" to={`/transactions/${transaction.id}`}>
                View transaction
              </Link>
            )}
            {canWrite ? (
              <Link className="btn btn-secondary btn-sm" to={`/kenya?case=${application.id}`}>
                Open in Kenya ops
              </Link>
            ) : (
              <Link className="btn btn-secondary btn-sm" to={`/customer/${encodeURIComponent(application.customer_ref)}`}>
                View journey
              </Link>
            )}
            {profile.showShariah ? (
              <Link className="btn btn-secondary btn-sm" to="/shariah">
                Shariah compliance
              </Link>
            ) : null}
            {canWrite ? (
              <button type="button" className="btn btn-secondary btn-sm" disabled={deleting} onClick={() => void onDelete()}>
                {confirmDelete ? "Confirm delete" : "Delete"}
              </button>
            ) : null}
          </div>

          {business && (
            <ul className="meta-list">
              <li>Customer sale: {business.customer_sale_recorded ? "recorded" : "pending"}</li>
              <li>Customer agency: {business.customer_agency_appointed ? "appointed" : "pending"}</li>
              <li>Ready for Leg 3: {business.ready_for_leg_3 ? "yes" : "no"}</li>
            </ul>
          )}
        </section>

        {profile.showShariah ? (
        <section className="panel">
          <h2>Shariah audit</h2>
          <p className="muted">Immutable step ledger for this application</p>
          {shariah.length === 0 ? (
            <EmptyStateInline title="No audit entries" description="Entries appear as workflow steps complete." />
          ) : (
            <ul className="audit-list">
              {shariah.map((entry) => (
                <li key={entry.id}>
                  <span className="audit-action">{entry.step_id}</span>
                  <span className="meta">{new Date(entry.timestamp).toLocaleString()}</span>
                  <span className="meta mono">{entry.payload_hash.slice(0, 16)}…</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        ) : null}
      </div>
    </PageShell>
  );
}

function EmptyStateInline({ title, description }: { title: string; description: string }) {
  return (
    <div className="empty-state" style={{ padding: "1.25rem 1rem" }}>
      <strong>{title}</strong>
      <p style={{ marginBottom: 0 }}>{description}</p>
    </div>
  );
}
