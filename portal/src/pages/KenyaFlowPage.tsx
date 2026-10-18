import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CustomerPicker, type CustomerPickerHandle } from "../components/CustomerPicker";
import {
  AgentDealerSummary,
  api,
  BrokerInfo,
  CustomerJourney,
  KenyaOpsCase,
  ShariahAuditEntry,
  ShariahIntegrity,
} from "../api/client";
import { BtiKenyaCertificate } from "../components/BtiKenyaCertificate";
import { Alert, EmptyState, LoadingPanel, PageShell, statusBadgeClass } from "../components/PageShell";
import { AuditTape, DealTape, MurabahaTape, PossessionTape, SettlementTape, WakalaTape } from "../components/DealTape";
import { FloatExplain } from "../components/FloatExplain";
import { ActorChips, StepCallout } from "../components/ProcessGuide";
import { DEFAULT_PROFIT_RATE_PCT, KENYA_QUEUES, KENYA_STEP_GUIDE, type KenyaQueueId } from "../config/kenyaOps";
import type { ActorId } from "../config/processModel";
import "../components/ui.css";

type QueueFilter = KenyaQueueId;

const JOURNEY_STEPS = [
  { key: "eligibility", label: "1. Facility Application and Agency Mandate" },
  { key: "purchase", label: "2. Float Purchase Order" },
  { key: "possession", label: "3. Supplier Transfer and Possession" },
  { key: "offer", label: "4. Murabahah Deferred Sale" },
  { key: "wakala", label: "5. Agency Activation" },
  { key: "liquidate", label: "6. Spot Sale to Secondary Purchaser" },
  { key: "disburse", label: "7. Clearing and Settlement" },
  { key: "repay", label: "8. Disbursement and Repayments" },
];

/** Who is holding the case right now, keyed by the engine's next_action code. */
const NEXT_ACTION_OWNER: Record<string, { actors: ActorId[]; note: string }> = {
  eligibility: { actors: ["bti"], note: "The engine scores the request before anything is bought." },
  eligibility_failed: { actors: ["bank"], note: "Bank ops must review the customer before retrying." },
  start_transaction: { actors: ["bti", "partner"], note: "Open the commodity transaction (MNO or Agent Dealer)." },
  purchase: { actors: ["bti", "amanah", "partner"], note: "Buruuj buys float from the MNO or an Agent Dealer pool." },
  possession: {
    actors: ["partner", "bti"],
    note: "Waiting on the supplier receipt that proves constructive possession.",
  },
  offer: { actors: ["bank"], note: "The institution prices cost plus profit for the customer." },
  accept: { actors: ["customer"], note: "Nothing moves until the customer accepts the Murabaha offer." },
  murabaha: { actors: ["bank"], note: "Draw up the Murabaha contract from the accepted offer." },
  sign: { actors: ["customer"], note: "Waiting on the customer's signature." },
  transfer: { actors: ["bti", "amanah"], note: "Leg 2 moves ownership to the customer." },
  wakala: { actors: ["customer", "bti"], note: "Customer must appoint Buruuj as selling agent." },
  liquidate: { actors: ["bti", "partner"], note: "Leg 3 sells to an independent broker under No-Inah." },
  disburse: { actors: ["bti", "partner"], note: "Net proceeds go to the customer's wallet." },
  repay: { actors: ["bank", "customer"], note: "Collect instalments against the schedule." },
  complete: { actors: ["shariah"], note: "Journey finished — only the audit record remains." },
};

function stepDone(caseData: KenyaOpsCase, key: string): boolean {
  switch (key) {
    case "eligibility":
      return caseData.eligibility_passed === true;
    case "purchase":
      return caseData.legs.some((l) => l.leg_number === "1" && l.status !== "pending");
    case "possession":
      return caseData.possession_sealed;
    case "offer":
      return (
        caseData.offer_accepted &&
        caseData.murabaha_signed &&
        caseData.legs.some((l) => l.leg_number === "2" && l.status === "confirmed")
      );
    case "wakala":
      return caseData.wakala_appointed;
    case "liquidate":
      return caseData.legs.some((l) => l.leg_number === "3" && l.status === "confirmed");
    case "disburse":
      return caseData.wallet_credited;
    case "repay":
      return caseData.installments_total > 0 && caseData.installments_paid >= caseData.installments_total;
    default:
      return false;
  }
}

export function KenyaFlowPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get("case");
  const [queue, setQueue] = useState<QueueFilter>("all");
  const [cases, setCases] = useState<KenyaOpsCase[]>([]);
  const [selected, setSelected] = useState<KenyaOpsCase | null>(null);
  const [brokers, setBrokers] = useState<BrokerInfo[]>([]);
  const [audit, setAudit] = useState<ShariahAuditEntry[]>([]);
  const [integrity, setIntegrity] = useState<ShariahIntegrity | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [showBtiCert, setShowBtiCert] = useState(false);
  const [certJourney, setCertJourney] = useState<CustomerJourney | null>(null);

  const [dealerSummary, setDealerSummary] = useState<AgentDealerSummary | null>(null);

  const [receiptId, setReceiptId] = useState("");
  const [batchId, setBatchId] = useState("");
  const [wakalaRef, setWakalaRef] = useState(`WAKALA-${Date.now().toString(36).toUpperCase()}`);
  const [wakalaNotes, setWakalaNotes] = useState(
    "I appoint Buruuj as my agent to sell the digital commodity to an independent third-party broker.",
  );
  const [profitRate, setProfitRate] = useState(DEFAULT_PROFIT_RATE_PCT);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const q = queue === "all" ? undefined : queue;
      const [caseList, brokerList, summary] = await Promise.all([
        api.listKenyaOpsCases(q),
        api.listKenyaBrokers().catch(() => [] as BrokerInfo[]),
        api.getAgentDealerSummary().catch(() => null),
      ]);
      setCases(caseList);
      setBrokers(brokerList);
      setDealerSummary(summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Kenya ops queue");
    } finally {
      setLoading(false);
    }
  }, [queue]);

  const loadCase = useCallback(async (id: string) => {
    try {
      const [caseData, shariah, verify] = await Promise.all([
        api.getKenyaOpsCase(id),
        api.getKenyaShariahAudit(id).catch(() => [] as ShariahAuditEntry[]),
        api.verifyKenyaShariah(id).catch(() => null),
      ]);
      setSelected(caseData);
      if (caseData.offer) {
        const cost = Number(caseData.offer.cost_price);
        const profit = Number(caseData.offer.profit_amount);
        setProfitRate(cost > 0 ? Number(((profit / cost) * 100).toFixed(2)) : DEFAULT_PROFIT_RATE_PCT);
      } else {
        setProfitRate(DEFAULT_PROFIT_RATE_PCT);
      }
      setAudit(shariah);
      setIntegrity(verify);
      if (caseData.batch_id) setBatchId(caseData.batch_id);
      if (caseData.mno_receipt_id) setReceiptId(caseData.mno_receipt_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load case");
    }
  }, []);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  useEffect(() => {
    if (selectedId) loadCase(selectedId);
    else setSelected(null);
  }, [selectedId, loadCase]);

  function openCase(id: string) {
    setSearchParams({ case: id });
    setMessage("");
    setError("");
  }

  async function refreshAll() {
    await loadQueue();
    if (selectedId) await loadCase(selectedId);
  }

  async function runAction(label: string, action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
      setMessage(label);
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  async function handlePossession(event: FormEvent) {
    event.preventDefault();
    if (!selected?.transaction_id) return;
    await runAction("Constructive possession confirmed", () =>
      api.kenyaPossessionConfirm(
        selected.transaction_id!,
        batchId || undefined,
        receiptId || `MNO-RCPT-${Date.now()}`,
      ),
    );
  }

  async function handleWakala(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    await runAction("Wakala consent recorded", () =>
      api.kenyaWakala(selected.application_id, wakalaRef, wakalaNotes),
    );
  }

  async function openBtiCertModal(customerRef: string) {
    setBusy(true);
    setError("");
    try {
      const journey = await api.getCustomerJourney(customerRef);
      setCertJourney(journey);
      setShowBtiCert(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Shariah certificate");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell wide>
      <FloatExplain />
      {dealerSummary && (
        <div className={`kenya-float-banner health-${dealerSummary.health}`}>
          <div className="kenya-float-copy">
            <span className="kenya-float-dot" aria-hidden="true" />
            <div>
              <strong>
                Agent dealer float pool: KES{" "}
                {dealerSummary.total_float_balance.toLocaleString("en-KE", { minimumFractionDigits: 2 })}
              </strong>
              <p>
                {dealerSummary.primary_dealer
                  ? `${dealerSummary.primary_dealer.business_name} · Till ${dealerSummary.primary_dealer.mpesa_till_number || "N/A"}`
                  : `${dealerSummary.total_active_dealers} active dealer(s)`}
                . Step 2 drains this pool when a dealer is active. Ask the dealer to add float if the pool is short.
              </p>
            </div>
          </div>
          <div className="kenya-float-actions">
            <Link to="/agent-dealers" className="btn btn-ghost btn-sm">
              View dealers
            </Link>
          </div>
        </div>
      )}

      <div className="kenya-ops-layout">
        <aside className="panel kenya-queue">
          <div className="panel-header">
            <div>
              <h2>Kenya ops queue</h2>
              <p className="muted">Cases waiting on the next of the eight steps</p>
            </div>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setShowNew(true)}>
              New case
            </button>
          </div>

          <div className="queue-filters">
            {KENYA_QUEUES.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`chip${queue === item.id ? " active" : ""}`}
                title={item.hint}
                onClick={() => setQueue(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <p className="meta">{KENYA_QUEUES.find((item) => item.id === queue)?.hint}</p>

          {loading ? (
            <LoadingPanel rows={5} />
          ) : cases.length === 0 ? (
            <EmptyState
              title="No cases in this queue"
              description={
                KENYA_QUEUES.find((item) => item.id === queue)?.hint ||
                "Create a Kenya financing case or switch filters."
              }
            />
          ) : (
            <ul className="case-list">
              {cases.map((item) => (
                <li key={item.application_id}>
                  <button
                    type="button"
                    className={`case-row${selectedId === item.application_id ? " active" : ""}`}
                    onClick={() => openCase(item.application_id)}
                  >
                    <div className="case-row-top">
                      <strong>{item.customer_name}</strong>
                      <span className={statusBadgeClass(item.status)}>{item.status}</span>
                    </div>
                    <span className="meta">
                      KES {item.amount_requested} · {item.term_months} mo
                    </span>
                    <span className="case-next">{item.next_action_label}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <div className="kenya-case-main">
          {error && <Alert tone="error">{error}</Alert>}
          {message && <Alert tone="success">{message}</Alert>}

          {showNew && (
            <NewKenyaCase
              onClose={() => setShowNew(false)}
              onCreated={async (id) => {
                setShowNew(false);
                await loadQueue();
                openCase(id);
              }}
              onError={setError}
            />
          )}

          {!selected && !showNew && (
            <section className="panel">
              <h2>How Kenya Ops works</h2>
              <p className="muted">
                This is the eight-step desk. The commodity is float (see What float means above).
                Pick a customer already on Customers, create a case, then run only the next action
                the case names. Do not skip ahead.
              </p>
              <ol className="flow-list numbered">
                {KENYA_STEP_GUIDE.map((step) => (
                  <li key={step.n}>
                    <strong>
                      {step.n}. {step.title}.
                    </strong>{" "}
                    {step.body}
                  </li>
                ))}
              </ol>
              <p className="meta">
                Hard rules: possession (step 3) before Murabaha (step 4). Wakala (step 5) before the
                independent sale (step 6). No-Inah blocks sale back to the same dealer or MNO pool
                that supplied the float.
              </p>
              <p className="meta">
                Use New case to start. Use Run automated 8-step flow only for a mock demo after the
                case exists. Live desks should click the next action one step at a time.
              </p>
            </section>
          )}

          {selected && (
            <>
              <section className="panel">
                <div className="panel-header">
                  <div>
                    <h2>{selected.customer_name}</h2>
                    <p className="muted">
                      {selected.customer_phone || selected.customer_ref} · KES {selected.amount_requested} ·{" "}
                      {selected.term_months} months
                    </p>
                  </div>
                  <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    {selected.possession_sealed && (
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => openBtiCertModal(selected.customer_ref)}
                      >
                        View Shariah Certificate
                      </button>
                    )}
                    <span className={statusBadgeClass(selected.status)}>{selected.status}</span>
                  </div>
                </div>

                <div className="journey-track">
                  {JOURNEY_STEPS.map((step) => (
                    <div
                      key={step.key}
                      className={`journey-step${stepDone(selected, step.key) ? " done" : ""}${
                        selected.next_action === step.key ||
                        (step.key === "purchase" && selected.next_action === "start_transaction") ||
                        (step.key === "offer" &&
                          ["accept", "murabaha", "sign", "transfer"].includes(selected.next_action)) ||
                        (step.key === "disburse" && selected.next_action === "disburse")
                          ? " current"
                          : ""
                      }`}
                    >
                      <span className="journey-dot" />
                      <span>{step.label}</span>
                    </div>
                  ))}
                </div>

                <p className="meta">
                  Do the action named below. The engine blocks any step whose prerequisite is missing.
                </p>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "12px", gap: "12px" }}>
                  <div style={{ flex: 1 }}>
                    <Alert tone="info">
                      <strong>Next for ops:</strong> {selected.next_action_label}
                    </Alert>
                  </div>
                  {selected.status !== "completed" && (
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      style={{ whiteSpace: "nowrap" }}
                      disabled={busy}
                      onClick={() =>
                        runAction("8-step automated flow completed.", () =>
                          api.runKenyaFullFlow(selected.application_id),
                        )
                      }
                      title="Runs the remaining steps in order. Use for mock demos. Live desks should click the next action instead."
                    >
                      Run automated 8-step flow
                    </button>
                  )}
                </div>
                {selected.status !== "completed" ? (
                  <p className="meta">
                    Automated flow is for mock demos. A live desk should click the next action only.
                  </p>
                ) : null}
                {NEXT_ACTION_OWNER[selected.next_action] ? (
                  <div className="turn-indicator">
                    <span className="turn-label">Currently with</span>
                    <ActorChips actors={NEXT_ACTION_OWNER[selected.next_action].actors} />
                    <span className="turn-note">{NEXT_ACTION_OWNER[selected.next_action].note}</span>
                  </div>
                ) : null}
                <DealTape
                  amount={selected.amount_requested}
                  termMonths={selected.term_months}
                  profitRatePct={profitRate}
                  onProfitRateChange={selected.offer ? undefined : setProfitRate}
                  offer={selected.offer}
                  installmentsTotal={selected.installments_total}
                  installmentsPaid={selected.installments_paid}
                />
              </section>

              <div className="page-grid">
                <PossessionPanel
                  caseData={selected}
                  dealer={dealerSummary}
                  busy={busy}
                  batchId={batchId}
                  receiptId={receiptId}
                  setBatchId={setBatchId}
                  setReceiptId={setReceiptId}
                  onSubmit={handlePossession}
                  onPurchase={() =>
                    selected.transaction_id &&
                    runAction("Leg 1 purchase initiated", () => api.kenyaPurchase(selected.transaction_id!))
                  }
                  onStartTxn={() =>
                    runAction("Float purchase started", () =>
                      api.startKenyaTransaction(selected.application_id),
                    )
                  }
                  onEligibility={() =>
                    runAction("Eligibility completed", () => api.runKenyaEligibility(selected.application_id))
                  }
                />

                <MurabahaPanel
                  caseData={selected}
                  profitRatePct={profitRate}
                  onProfitRateChange={setProfitRate}
                  busy={busy}
                  onOffer={() =>
                    runAction(
                      selected.customer_email
                        ? `Murabaha offer locked. Accept email sent to ${selected.customer_email}.`
                        : "Murabaha offer locked. Add an email on Customers, or copy the journey link.",
                      () => api.kenyaOffer(selected.application_id, { profit_rate_pct: profitRate }),
                    )
                  }
                  onResendEmail={() =>
                    runAction("Accept email resent", () => api.kenyaResendOfferEmail(selected.application_id))
                  }
                  onContract={() =>
                    runAction("Murabaha contract created", () => api.kenyaMurabaha(selected.application_id))
                  }
                  onTransfer={() =>
                    selected.transaction_id &&
                    runAction("Ownership transferred to customer", () =>
                      api.kenyaTransfer(selected.transaction_id!),
                    )
                  }
                />

                <WakalaPanel
                  caseData={selected}
                  busy={busy}
                  wakalaRef={wakalaRef}
                  wakalaNotes={wakalaNotes}
                  setWakalaRef={setWakalaRef}
                  setWakalaNotes={setWakalaNotes}
                  onSubmit={handleWakala}
                />

                <SettlementPanel
                  caseData={selected}
                  brokers={brokers}
                  busy={busy}
                  onLiquidate={() =>
                    selected.transaction_id &&
                    runAction("Independent broker liquidation complete", () =>
                      api.kenyaLiquidate(selected.transaction_id!),
                    )
                  }
                  onSettle={() =>
                    runAction("Wallet credited + repayment schedule created", () =>
                      api.kenyaCompleteSettlement(selected.application_id),
                    )
                  }
                />

                {/* ── Buruuj Certificate + Dealer Info panel ── */}
                {(selected.wallet_credited || selected.status === "completed") && (
                  <section className="panel span-2">
                    <div className="panel-header">
                      <div>
                        <h2>Buruuj Shariah Certificate &amp; Journey</h2>
                        <p className="muted">Available once wallet is credited. Numbers match the settlement card.</p>
                      </div>
                      <div className="actions-row">
                        <Link
                          className="btn btn-secondary btn-sm"
                          to={`/customer/${selected.customer_ref}`}
                          target="_blank"
                        >
                          Customer journey
                        </Link>
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          disabled={busy}
                          onClick={async () => {
                            try {
                              const j = await api.getCustomerJourney(selected.customer_ref);
                              setCertJourney(j);
                              setShowBtiCert(true);
                            } catch {
                              /* journey not yet available */
                            }
                          }}
                        >
                          View certificate
                        </button>
                      </div>
                    </div>
                    <SettlementTape caseData={selected} />
                    <ul className="status-list compact">
                      <li className="status-row">
                        <span>Customer ref</span>
                        <span className="meta mono">{selected.customer_ref}</span>
                      </li>
                      <li className="status-row">
                        <span>Commodity</span>
                        <span className="meta">{selected.commodity_code || "—"}</span>
                      </li>
                      {selected.broker_name && (
                        <li className="status-row">
                          <span>Dealer / Broker</span>
                          <span className="meta">{selected.broker_name} ({selected.broker_code})</span>
                        </li>
                      )}
                      <li className="status-row">
                        <span>No-Inah validated</span>
                        <span className={`badge ${selected.no_inah_validated ? "success" : "warning"}`}>
                          {selected.no_inah_validated ? "Yes" : "Pending"}
                        </span>
                      </li>
                    </ul>
                  </section>
                )}

                <section className="panel span-2">
                  <div className="panel-header">
                    <div>
                      <h2>Shariah audit trail</h2>
                      <p className="muted">
                        Append-only ledger written by the engine as each party acts — evidence, not a log you
                        can edit
                      </p>
                    </div>
                    <div className="actions-row">
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        disabled={busy}
                        onClick={() =>
                          runAction("Integrity re-checked", async () => {
                            const result = await api.verifyKenyaShariah(selected.application_id);
                            setIntegrity(result);
                          })
                        }
                      >
                        Verify integrity
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        disabled={busy}
                        onClick={() =>
                          runAction("Export downloaded", () =>
                            api.downloadShariahExport({
                              format: "csv",
                              application_id: selected.application_id,
                            }),
                          )
                        }
                      >
                        Export CSV
                      </button>
                      <Link className="btn btn-secondary btn-sm" to="/shariah">
                        Compliance desk
                      </Link>
                      <Link className="btn btn-secondary btn-sm" to="/repayments">
                        Repayments board
                      </Link>
                    </div>
                  </div>
                  <AuditTape caseData={selected} />

                  {integrity && (
                    <ul className="status-list compact">
                      <li className="status-row">
                        <span>Ledger valid</span>
                        <span className={`badge ${integrity.valid ? "success" : "warning"}`}>
                          {integrity.valid ? "Yes" : "No"}
                        </span>
                      </li>
                      <li className="status-row">
                        <span>Possession sealed</span>
                        <span className={`badge ${integrity.possession_sealed ? "success" : "warning"}`}>
                          {integrity.possession_sealed ? "Yes" : "No"}
                        </span>
                      </li>
                      <li className="status-row">
                        <span>Entries</span>
                        <span className="meta">{integrity.entry_count}</span>
                      </li>
                    </ul>
                  )}

                  {audit.length === 0 ? (
                    <p className="muted">No Shariah entries yet.</p>
                  ) : (
                    <ul className="audit-list">
                      {audit.map((entry) => (
                        <li key={entry.id}>
                          <span className="audit-action">{entry.step_id}</span>
                          <span className="meta">
                            {entry.actor_from} → {entry.actor_to}
                          </span>
                          <span className="meta mono">
                            {entry.asset_ref_no || entry.mno_receipt_id || entry.payload_hash.slice(0, 12)}…
                          </span>
                          <span className="meta">{new Date(entry.timestamp).toLocaleString()}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Buruuj Kenya Certificate Modal */}
      {showBtiCert && certJourney && (
        <BtiKenyaCertificate
          journey={certJourney}
          onClose={() => { setShowBtiCert(false); setCertJourney(null); }}
        />
      )}

    </PageShell>
  );
}

function NewKenyaCase({
  onClose,
  onCreated,
  onError,
}: {
  onClose: () => void;
  onCreated: (id: string) => void;
  onError: (msg: string) => void;
}) {
  const customerPickerRef = useRef<CustomerPickerHandle>(null);
  const [amount, setAmount] = useState("50000");
  const [term, setTerm] = useState(6);
  const [profitRate, setProfitRate] = useState(DEFAULT_PROFIT_RATE_PCT);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const customer = await customerPickerRef.current?.ensureCustomer();
      if (!customer) {
        throw new Error("Select the onboarded customer for this case.");
      }
      const app = await api.createKenyaApplication({
        customer_id: customer.id,
        amount_requested: amount,
        term_months: term,
        purpose: "Safaricom Digital Float / Airtime financing",
      });
      await api.runKenyaEligibility(app.id);
      onCreated(app.id);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to create case");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Step 1: Originate Financing Case (Wa'd &amp; Wakalah)</h2>
          <p className="muted">
            Step 1. Attach a customer already on Customers. The engine records the Wa'd (undertaking
            to purchase) and scores eligibility. Do not register the same person again.
          </p>
        </div>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
          Cancel
        </button>
      </div>
      <form className="form-grid" onSubmit={submit}>
        <div className="span-2">
          <CustomerPicker ref={customerPickerRef} />
        </div>
        <label>
          Financing amount (KES)
          <input value={amount} onChange={(e) => setAmount(e.target.value)} required />
          <span className="meta">
            Facility size. This is also the float cost the institution must possess before Murabaha.
          </span>
        </label>
        <label>
          Term (months)
          <input type="number" value={term} onChange={(e) => setTerm(Number(e.target.value))} required />
          <span className="meta">How many Murabaha instalments the customer will repay after payout.</span>
        </label>
        <div className="span-2">
          <DealTape
            amount={amount}
            termMonths={term}
            profitRatePct={profitRate}
            onProfitRateChange={setProfitRate}
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? "Creating…" : "Create case"}
        </button>
      </form>
    </section>
  );
}

function PossessionPanel({
  caseData,
  dealer,
  busy,
  batchId,
  receiptId,
  setBatchId,
  setReceiptId,
  onSubmit,
  onPurchase,
  onStartTxn,
  onEligibility,
}: {
  caseData: KenyaOpsCase;
  dealer: AgentDealerSummary | null;
  busy: boolean;
  batchId: string;
  receiptId: string;
  setBatchId: (v: string) => void;
  setReceiptId: (v: string) => void;
  onSubmit: (e: FormEvent) => void;
  onPurchase: () => void;
  onStartTxn: () => void;
  onEligibility: () => void;
}) {
  return (
    <section className="panel">
      <h2>Possession desk</h2>
      <StepCallout
        stepLabel="1–3"
        title="Apply, buy the float, and prove possession"
        actors={["bti", "amanah", "partner"]}
        mode="automated"
      >
        Step 1 scores eligibility. Step 2 buys float from the MNO or an Agent Dealer. Step 3 seals
        constructive possession. Nothing may be sold to the customer until this is sealed.
      </StepCallout>
      <PossessionTape caseData={caseData} dealer={dealer} />
      <ul className="status-list compact">
        <li className="status-row">
          <span>Eligibility</span>
          <span className={`badge ${caseData.eligibility_passed ? "success" : "warning"}`}>
            {caseData.eligibility_passed ? "Passed" : "Pending"}
          </span>
        </li>
        <li className="status-row">
          <span>Possession sealed</span>
          <span className={`badge ${caseData.possession_sealed ? "success" : "warning"}`}>
            {caseData.possession_sealed ? "Yes" : "No"}
          </span>
        </li>
        <li className="status-row">
          <span>Batch / asset ref</span>
          <span className="meta mono">{caseData.asset_ref_hash?.slice(0, 16) || "—"}</span>
        </li>
        <li className="status-row">
          <span>MNO receipt</span>
          <span className="meta mono">{caseData.mno_receipt_id || "—"}</span>
        </li>
      </ul>

      {caseData.next_action === "eligibility" && (
        <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={onEligibility}>
          Run eligibility
        </button>
      )}
      {caseData.next_action === "start_transaction" && (
        <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={onStartTxn}>
          Start float purchase
        </button>
      )}
      {caseData.next_action === "purchase" && (
        <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={onPurchase}>
          Execute Leg 1 purchase
        </button>
      )}
      {caseData.next_action === "possession" && caseData.transaction_id && (
        <form className="stack-form" onSubmit={onSubmit}>
          <label>
            Batch ID
            <input value={batchId} onChange={(e) => setBatchId(e.target.value)} placeholder="Optional batch id" />
            <span className="meta">Supplier lot number. Leave blank if the engine already issued one.</span>
          </label>
          <label>
            MNO receipt ID
            <input
              value={receiptId}
              onChange={(e) => setReceiptId(e.target.value)}
              placeholder="MNO receipt / confirmation id"
              required
            />
            <span className="meta">
              Supplier confirmation that the float left the MNO or Dealer A. Required to seal step 3.
            </span>
          </label>
          <button type="submit" className="btn btn-primary btn-sm" disabled={busy || caseData.possession_sealed}>
            Confirm constructive possession
          </button>
        </form>
      )}
    </section>
  );
}

function MurabahaPanel({
  caseData,
  profitRatePct,
  onProfitRateChange,
  busy,
  onOffer,
  onResendEmail,
  onContract,
  onTransfer,
}: {
  caseData: KenyaOpsCase;
  profitRatePct: number;
  onProfitRateChange: (rate: number) => void;
  busy: boolean;
  onOffer: () => void;
  onResendEmail: () => void;
  onContract: () => void;
  onTransfer: () => void;
}) {
  const [copied, setCopied] = useState("");

  function copyJourneyLink() {
    const url = `${window.location.origin}/customer/${encodeURIComponent(caseData.customer_ref)}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopied(caseData.customer_ref);
      setTimeout(() => setCopied(""), 2500);
    });
  }

  return (
    <section className="panel">
      <h2>Murabaha & title transfer</h2>
      <StepCallout
        stepLabel="4"
        title="Murabahah deferred sale to the customer"
        actors={["bank", "customer", "bti"]}
        mode="manual"
      >
        Step 4: the bank locks cost plus disclosed profit. The customer accepts and signs on their
        journey. Ops then creates the contract and runs Leg 2. Ops does not accept for the customer.
      </StepCallout>
      <MurabahaTape
        caseData={caseData}
        profitRatePct={profitRatePct}
        onProfitRateChange={onProfitRateChange}
      />
      {caseData.offer ? (
        <p className="meta">
          {caseData.offer.accepted
            ? "The customer accepted the locked offer on their journey."
            : caseData.customer_email
              ? `Offer locked. We emailed ${caseData.customer_email} the accept link. If SMTP is not set, the engine wrote a local copy. Ops cannot accept for them.`
              : "Offer locked. This customer has no email. Copy the journey link, or add email on Customers. Ops cannot accept for them."}
        </p>
      ) : (
        <p className="muted">
          {caseData.possession_sealed
            ? "Generate the offer to lock these numbers. The customer then gets the accept email."
            : "Possession must be sealed before you can generate the offer."}
        </p>
      )}
      <div className="actions-row wrap">
        {caseData.next_action === "offer" && (
          <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={onOffer}>
            Generate offer
          </button>
        )}
        {caseData.next_action === "accept" && (
          <>
            <Link className="btn btn-secondary btn-sm" to={`/customer/${caseData.customer_ref}`}>
              Open customer journey
            </Link>
            <button type="button" className="btn btn-secondary btn-sm" onClick={copyJourneyLink}>
              {copied === caseData.customer_ref ? "Link copied" : "Copy journey link"}
            </button>
            {caseData.customer_email ? (
              <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={onResendEmail}>
                Resend accept email
              </button>
            ) : null}
          </>
        )}
        {caseData.next_action === "murabaha" && (
          <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={onContract}>
            Create contract
          </button>
        )}
        {caseData.next_action === "sign" && (
          <Link className="btn btn-secondary btn-sm" to={`/customer/${caseData.customer_ref}`}>
            Open customer journey
          </Link>
        )}
        {caseData.next_action === "transfer" && (
          <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={onTransfer}>
            Transfer title to customer
          </button>
        )}
      </div>
    </section>
  );
}

function WakalaPanel({
  caseData,
  busy,
  wakalaRef,
  wakalaNotes,
  setWakalaRef,
  setWakalaNotes,
  onSubmit,
}: {
  caseData: KenyaOpsCase;
  busy: boolean;
  wakalaRef: string;
  wakalaNotes: string;
  setWakalaRef: (v: string) => void;
  setWakalaNotes: (v: string) => void;
  onSubmit: (e: FormEvent) => void;
}) {
  return (
    <section className="panel">
      <h2>Wakala consent</h2>
      <StepCallout
        stepLabel="5"
        title="Agency activation: customer appoints Buruuj as selling agent"
        actors={["customer", "bti"]}
        mode="manual"
      >
        Step 5 Wakala. Without recorded consent the platform has no authority to sell the customer's
        commodity, so step 6 liquidation stays blocked.
      </StepCallout>
      <WakalaTape caseData={caseData} />
      {caseData.wakala_appointed ? (
        <Alert tone="success">
          Wakala recorded{caseData.wakala_notes ? `: ${caseData.wakala_notes}` : "."}
        </Alert>
      ) : (
        <form className="stack-form" onSubmit={onSubmit}>
          <label>
            Consent reference
            <input value={wakalaRef} onChange={(e) => setWakalaRef(e.target.value)} required />
            <span className="meta">The customer's or bank's ticket for this agency appointment.</span>
          </label>
          <label>
            Customer consent notes
            <textarea value={wakalaNotes} onChange={(e) => setWakalaNotes(e.target.value)} rows={3} />
            <span className="meta">
              Wording that Buruuj may sell the float to an independent buyer. Stored on the audit trail.
            </span>
          </label>
          <button
            type="submit"
            className="btn btn-primary btn-sm"
            disabled={busy || caseData.next_action !== "wakala"}
          >
            Record Wakala appointment
          </button>
          {caseData.next_action !== "wakala" && (
            <p className="meta">Available when ownership has transferred to the customer.</p>
          )}
        </form>
      )}
    </section>
  );
}

function SettlementPanel({
  caseData,
  brokers,
  busy,
  onLiquidate,
  onSettle,
}: {
  caseData: KenyaOpsCase;
  brokers: BrokerInfo[];
  busy: boolean;
  onLiquidate: () => void;
  onSettle: () => void;
}) {
  const eligible = brokers.filter((b) => b.eligible_for_liquidation);
  const blocked = brokers.filter((b) => b.is_mno_pool);

  return (
    <section className="panel">
      <h2>Independent liquidation & wallet</h2>
      <StepCallout
        stepLabel="6–8"
        title="Independent sale, clearing, then wallet and repayments"
        actors={["bti", "partner", "customer"]}
        mode="automated"
      >
        Step 6 sells to an independent broker (No-Inah: never the originating MNO or dealer pool).
        Step 7 clears proceeds.         Step 8 credits the wallet and opens the repayment schedule.
      </StepCallout>
      <SettlementTape caseData={caseData} />

      <ul className="status-list compact">
        <li className="status-row">
          <span>Broker</span>
          <span className="meta">{caseData.broker_name || caseData.broker_code || "Not yet selected"}</span>
        </li>
        <li className="status-row">
          <span>No-Inah validated</span>
          <span className={`badge ${caseData.no_inah_validated ? "success" : "warning"}`}>
            {caseData.no_inah_validated ? "Yes" : "Pending"}
          </span>
        </li>
        <li className="status-row">
          <span>Wallet</span>
          <span className="meta">
            {caseData.wallet_status || "not credited"}
            {caseData.wallet_external_txn_id ? ` · ${caseData.wallet_external_txn_id}` : ""}
          </span>
        </li>
      </ul>

      <div className="broker-split">
        <div>
          <p className="form-section-title">Eligible brokers</p>
          <ul className="meta-list">
            {eligible.map((b) => (
              <li key={b.id}>
                {b.name} ({b.code})
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="form-section-title">Blocked (MNO pool / Inah risk)</p>
          <ul className="meta-list">
            {blocked.length === 0 ? <li>None flagged</li> : blocked.map((b) => <li key={b.id}>{b.code}</li>)}
          </ul>
        </div>
      </div>

      <div className="actions-row wrap">
        {caseData.next_action === "liquidate" && (
          <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={onLiquidate}>
            Liquidate via independent broker
          </button>
        )}
        {(caseData.next_action === "disburse" || caseData.next_action === "liquidate") && (
          <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={onSettle}>
            Complete settlement (liquidate + wallet + schedule)
          </button>
        )}
        {caseData.next_action === "repay" && (
          <Link className="btn btn-primary btn-sm" to="/repayments">
            Open repayments board
          </Link>
        )}
      </div>
    </section>
  );
}
