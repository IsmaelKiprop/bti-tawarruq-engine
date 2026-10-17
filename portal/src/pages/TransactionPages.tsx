import { FormEvent, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, Application, AuditEvent, BusinessStatus, OfferSummary, Transaction } from "../api/client";
import { DealTape } from "../components/DealTape";
import { HowItWorks, PageExplain } from "../components/PageExplain";
import { Alert, LoadingPanel, PageShell, statusBadgeClass } from "../components/PageShell";
import { ActorChips, StepCallout } from "../components/ProcessGuide";
import { applicationUsesSpot } from "../config/applicationOps";
import { HOW_IT_WORKS, PAGE_EXPLAINS } from "../config/pageExplainers";
import type { ActorId } from "../config/processModel";
import "../components/ui.css";

const LEG_LABELS: Record<string, string> = {
  "1": "Leg 1: Agent purchase",
  "2": "Leg 2: Ownership transfer",
  "3": "Leg 3: Sale to BMIS",
};

/** What each leg means and who executes it, per track. */
const LEG_META: Record<string, { bsas: string; mno: string; actors: ActorId[] }> = {
  "1": {
    bsas: "Buruuj instructs Bursa to buy the commodity as agent. Bursa executes and issues the e-certificate.",
    mno: "Buruuj buys airtime/float from the mobile network as agent, then waits for the possession receipt.",
    actors: ["bti", "bursa"],
  },
  "2": {
    bsas: "Ownership transfers over the counter so the commodity can be sold onward.",
    mno: "Ownership passes to the customer after they accept and sign the Murabaha.",
    actors: ["bti", "customer"],
  },
  "3": {
    bsas: "The commodity is sold to BMIS, which releases the cash for disbursement.",
    mno: "The commodity is liquidated to an independent broker — never the originating MNO pool.",
    actors: ["bti", "partner"],
  },
};

export function TransactionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [transaction, setTransaction] = useState<Transaction | null>(null);
  const [application, setApplication] = useState<Application | null>(null);
  const [offer, setOffer] = useState<OfferSummary | null>(null);
  const [business, setBusiness] = useState<BusinessStatus | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [confirmLeg, setConfirmLeg] = useState<string | null>(null);
  const [certNumber, setCertNumber] = useState("");

  async function load() {
    if (!id) return;
    try {
      const [txn, auditEvents] = await Promise.all([api.getTransaction(id), api.getAudit(id)]);
      setTransaction(txn);
      setAudit(auditEvents);
      if (txn.application_id) {
        const [biz, app, lockedOffer] = await Promise.all([
          api.getBusinessStatus(txn.application_id),
          api.getApplication(txn.application_id).catch(() => null),
          api.getKenyaOffer(txn.application_id).catch(() => null),
        ]);
        setBusiness(biz);
        setApplication(app);
        setOffer(lockedOffer);
      }
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load transaction");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [id]);

  async function handleConfirm(event: FormEvent) {
    event.preventDefault();
    if (!id || !confirmLeg) return;
    try {
      await api.confirmLeg(id, confirmLeg, certNumber);
      setConfirmLeg(null);
      setCertNumber("");
      setMessage("Certificate confirmed");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Confirmation failed");
    }
  }

  if (loading && !transaction) {
    return (
      <PageShell wide>
        <section className="panel">
          <LoadingPanel rows={6} />
        </section>
      </PageShell>
    );
  }

  if (error && !transaction) {
    return (
      <PageShell>
        <Alert tone="error">{error}</Alert>
      </PageShell>
    );
  }

  if (!transaction) return null;

  return (
    <PageShell wide>
      <div className="page-grid">
        <div className="span-2">
          <PageExplain content={PAGE_EXPLAINS["/transactions"]} />
        </div>
        <HowItWorks content={HOW_IT_WORKS["/transactions"]} />
        {application ? (
          <section className="panel">
            <DealTape
              amount={application.amount_requested}
              termMonths={application.term_months}
              currency={application.currency || "KES"}
              includeSpot={applicationUsesSpot(application.currency) || transaction.mode === "mno"}
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
          </section>
        ) : null}
        <section className="panel span-2">
          <div className="panel-header">
            <div>
              <h2>Transaction {transaction.id.slice(0, 8)}…</h2>
              <p className="muted">
                Mode: {transaction.mode} · Commodity: {transaction.commodity_code}
              </p>
            </div>
            <span className={statusBadgeClass(transaction.status)}>{transaction.status}</span>
          </div>

          {transaction.mode === "mno" ? (
            <StepCallout
              title="Kenya track — airtime commodity"
              actors={["bti", "partner", "customer"]}
              mode="automated"
            >
              The mobile network supplies the commodity and an independent broker buys it back. Bursa is not
              involved in this transaction.
            </StepCallout>
          ) : (
            <StepCallout
              title="Malaysia track — Bursa Suq Al-Sila'"
              actors={["bti", "bursa"]}
              mode="external"
            >
              Bursa executes each leg on the exchange. A leg only moves here once its e-certificate has come
              back from the BSAS desk.
            </StepCallout>
          )}

          {business && transaction.mode !== "mno" && (
            <>
              <p className="form-section-title">Business flow</p>
              <StepCallout
                stepLabel="7–8"
                title="Bank-side steps that sit between the legs"
                actors={["bank", "customer"]}
                mode="manual"
              >
                Recording the customer sale and the agency appointment is the institution's paperwork, not an
                exchange action. Disbursement unlocks once all three legs are confirmed.
              </StepCallout>
              <div className="actions-row">
                {!business.customer_sale_recorded && (
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={async () => {
                      await api.recordCustomerSale(transaction.application_id);
                      setMessage("Customer sale recorded");
                      load();
                    }}
                  >
                    Step 7: Customer sale
                  </button>
                )}
                {!business.customer_agency_appointed && (
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={async () => {
                      await api.appointCustomerAgency(transaction.application_id);
                      setMessage("Agency appointed");
                      load();
                    }}
                  >
                    Step 8: Customer agency
                  </button>
                )}
                {transaction.status === "completed" && (
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={async () => {
                      await api.createDisbursement(transaction.application_id, transaction.id);
                      setMessage("Disbursement created");
                    }}
                  >
                    Disburse
                  </button>
                )}
                <Link className="btn btn-secondary btn-sm" to={`/applications/${transaction.application_id}`}>
                  View application
                </Link>
              </div>
            </>
          )}

          {message && <Alert tone="success">{message}</Alert>}
          {error && <Alert tone="error">{error}</Alert>}

          <hr className="section-divider" />

          <p className="form-section-title">Commodity legs</p>
          <p className="muted flow-intro">
            The three legs must complete in order. Each card shows who executes it and what evidence closes it.
          </p>
          <div className="legs-grid">
            {transaction.legs.map((leg) => {
              const meta = LEG_META[leg.leg_number];
              return (
              <article key={leg.id} className="leg-card">
                <div className="leg-header">
                  <strong>{LEG_LABELS[leg.leg_number] ?? `Leg ${leg.leg_number}`}</strong>
                  <span className={statusBadgeClass(leg.status)}>{leg.status}</span>
                </div>
                {meta ? (
                  <>
                    <ActorChips
                      actors={transaction.mode === "mno" && leg.leg_number === "1" ? ["bti", "partner"] : meta.actors}
                    />
                    <p className="meta">{transaction.mode === "mno" ? meta.mno : meta.bsas}</p>
                  </>
                ) : null}
                {leg.external_ref && <p className="meta">Ref: {leg.external_ref}</p>}
                {leg.certificate && (
                  <div className="meta" style={{ marginTop: "0.5rem" }}>
                    <div>Certificate: {leg.certificate.certificate_number}</div>
                    <div>{leg.certificate.issuer}</div>
                    {leg.certificate.seller ? <div>Seller: {leg.certificate.seller}</div> : null}
                    {leg.certificate.buyer ? <div>Buyer: {leg.certificate.buyer}</div> : null}
                    {leg.certificate.product_code ? (
                      <div>
                        {leg.certificate.product_code}
                        {leg.certificate.product_description ? ` — ${leg.certificate.product_description}` : ""}
                      </div>
                    ) : null}
                    {leg.certificate.value_amount ? (
                      <div>
                        Value: {leg.certificate.currency || ""} {leg.certificate.value_amount}
                        {leg.certificate.price_myr_equivalent
                          ? ` · MYR ${leg.certificate.price_myr_equivalent}`
                          : ""}
                      </div>
                    ) : null}
                    {leg.certificate.pdf_filename ? <div>PDF: {leg.certificate.pdf_filename}</div> : null}
                  </div>
                )}
                {leg.status === "awaiting_confirmation" && (
                  <button className="btn btn-secondary btn-sm" onClick={() => setConfirmLeg(leg.leg_number)}>
                    Confirm certificate
                  </button>
                )}
              </article>
              );
            })}
          </div>

          {confirmLeg && (
            <form className="confirm-form" onSubmit={handleConfirm}>
              <h3>Confirm Leg {confirmLeg} certificate</h3>
              <input
                value={certNumber}
                onChange={(e) => setCertNumber(e.target.value)}
                placeholder="Certificate number"
                required
              />
              <div className="actions">
                <button type="submit" className="btn btn-primary btn-sm">
                  Submit
                </button>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => setConfirmLeg(null)}>
                  Cancel
                </button>
              </div>
            </form>
          )}
        </section>

        <section className="panel">
          <h2>Audit trail</h2>
          <p className="muted">Engine events for this transaction</p>
          {audit.length === 0 ? (
            <p className="muted">No audit events yet.</p>
          ) : (
            <ul className="audit-list">
              {audit.map((event) => (
                <li key={event.id}>
                  <span className="audit-action">{event.action}</span>
                  <span className="meta">
                    {event.actor} · {new Date(event.timestamp).toLocaleString()}
                  </span>
                  {event.details && <span className="meta">{event.details}</span>}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </PageShell>
  );
}
