import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  api,
  Certificate,
  DeskBatch,
  Leg,
  ManualBridgeDetail,
  ManualBridgeInbox,
  ManualBridgePendingItem,
  Transaction,
} from "../api/client";
import { BsasCertificateModal } from "../components/BsasCertificateModal";
import { CommodityExplain } from "../components/CommodityExplain";
import { CustomerPicker, type CustomerPickerHandle } from "../components/CustomerPicker";
import { DealTape, MalaysiaLegTape, MalaysiaSettlementTape } from "../components/DealTape";
import { Alert, EmptyState, LoadingPanel, PageShell, statusBadgeClass } from "../components/PageShell";
import { ActorChips, StepCallout } from "../components/ProcessGuide";
import { MALAYSIA_STEP_GUIDE } from "../config/malaysiaOps";
import "../components/ui.css";

const LEG_ACTION: Record<string, "purchase" | "transfer" | "sale"> = {
  "1": "purchase",
  "2": "transfer",
  "3": "sale",
};

export function MalaysiaManualBridgePage() {
  const customerPickerRef = useRef<CustomerPickerHandle>(null);
  const [amount, setAmount] = useState("550000");
  const [profitRate, setProfitRate] = useState("5");
  const [currency, setCurrency] = useState("MYR");
  const [term, setTerm] = useState(12);
  const [purpose, setPurpose] = useState("Working capital (Malaysia BSAS)");
  const [pending, setPending] = useState<ManualBridgePendingItem[]>([]);
  const [inbox, setInbox] = useState<ManualBridgeInbox | null>(null);
  const [deskBatch, setDeskBatch] = useState<DeskBatch | null>(null);
  const [selected, setSelected] = useState<ManualBridgeDetail | null>(null);
  const [transaction, setTransaction] = useState<Transaction | null>(null);
  const [certNumber, setCertNumber] = useState("");
  const [issuer, setIssuer] = useState("Bursa Malaysia Islamic Services Sdn.Bhd.");
  const [seller, setSeller] = useState("");
  const [buyer, setBuyer] = useState("Bursa Malaysia Islamic Services");
  const [bidNo, setBidNo] = useState("1");
  const [sellingTime, setSellingTime] = useState("");
  const [sellingDate, setSellingDate] = useState("");
  const [valueDate, setValueDate] = useState("");
  const [productCode, setProductCode] = useState("CPO-MSIA-09");
  const [productDescription, setProductDescription] = useState("Crude Palm Oil - Malaysia - Listed 09");
  const [unit, setUnit] = useState("Tonnage");
  const [volume, setVolume] = useState("");
  const [certCurrency, setCertCurrency] = useState("MYR");
  const [price, setPrice] = useState("");
  const [priceMyr, setPriceMyr] = useState("");
  const [valueAmount, setValueAmount] = useState("");
  const [transactionType, setTransactionType] = useState("-");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [log, setLog] = useState<string[]>([]);
  const [copied, setCopied] = useState("");
  const [viewCert, setViewCert] = useState<Certificate | null>(null);
  const [viewCertLeg, setViewCertLeg] = useState<string>("1");
  const [dealSnapshot, setDealSnapshot] = useState<{
    currency: string;
    bid: string;
    profit?: string | null;
    total?: string | null;
    termMonths: number;
    legNumber?: string;
  } | null>(null);

  const append = (msg: string) => setLog((prev) => [...prev, `${new Date().toLocaleTimeString()} · ${msg}`]);

  const refresh = useCallback(async () => {
    try {
      const [items, inboxSummary, batch] = await Promise.all([
        api.listManualBridgePending(),
        api.getManualBridgeInbox(),
        api.getManualBridgeDeskBatch().catch(() => null),
      ]);
      setPending(items);
      setInbox(inboxSummary);
      setDeskBatch(batch);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load manual-bridge inbox");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 8000);
    return () => clearInterval(timer);
  }, [refresh]);

  async function copyText(label: string, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(label);
      setTimeout(() => setCopied(""), 2000);
    } catch {
      setError("Could not copy to clipboard");
    }
  }

  async function openItem(item: ManualBridgePendingItem) {
    setError("");
    setMessage("");
    try {
      const [detail, txn] = await Promise.all([
        api.getManualBridgeLeg(item.transaction_id, item.leg_number),
        api.getTransaction(item.transaction_id),
      ]);
      setSelected(detail);
      setDealSnapshot({
        currency: detail.currency || "MYR",
        bid: detail.bid_amount || detail.amount_requested || "0",
        profit: detail.profit_amount,
        total: detail.murabaha_total,
        termMonths: term,
        legNumber: detail.leg_number,
      });
      setTransaction(txn);
      setCertNumber("");
      setSeller(detail.customer_name || "");
      setValueAmount(detail.bid_amount || detail.amount_requested || "");
      setCertCurrency(detail.currency || "MYR");
      setPdfFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load leg detail");
    }
  }

  async function runMockFullFlow() {
    setBusy(true);
    setError("");
    setMessage("");
    setLog([]);
    try {
      const customer = await customerPickerRef.current?.ensureCustomer();
      if (!customer) {
        throw new Error("Select the onboarded customer for this deal.");
      }
      append(`Creating MYR application for ${customer.full_name}…`);
      const application = await api.createApplication({
        customer_id: customer.id,
        customer_name: customer.full_name,
        currency,
        amount_requested: amount,
        term_months: term,
        purpose,
      });
      await api.createOffer(application.id, { cost_price: amount, profit_rate_pct: profitRate });
      await api.acceptOffer(application.id);
      append(`Accepted ${application.customer_ref}. Running mock 3-leg flow…`);
      const result = await api.runFullMalaysiaFlow(application.id);
      append(
        `Completed. Legs ${result.legs_confirmed}/3. Certificate ${result.certificate_number || "issued"}.`,
      );
      setMessage("Mock Malaysia E2E finished. Open the customer tracker with the application reference.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Mock Malaysia flow failed");
      append(`Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  async function startMalaysiaFlow(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    setLog([]);
    try {
      const customer = await customerPickerRef.current?.ensureCustomer();
      if (!customer) {
        throw new Error("Select the onboarded customer for this deal.");
      }
      append(`Creating financing application for ${customer.full_name}…`);
      const application = await api.createApplication({
        customer_id: customer.id,
        customer_name: customer.full_name,
        currency,
        amount_requested: amount,
        term_months: term,
        purpose,
      });
      append(`Application ${application.customer_ref} created for ${customer.full_name}`);

      append("Generating and accepting offer…");
      await api.createOffer(application.id, { cost_price: amount, profit_rate_pct: profitRate });
      await api.acceptOffer(application.id);

      append("Starting manual_bridge transaction (PALM_OIL → ACPO)…");
      const txn = await api.createTransaction(application.id, "manual_bridge", "PALM_OIL");
      setDealSnapshot({
        currency,
        bid: amount,
        termMonths: term,
        legNumber: "1",
      });
      setTransaction(txn);

      append("Advancing Leg 1 (generates Bursa desk packet)…");
      const advanced = await api.advanceManualBridge(txn.id);
      setTransaction(advanced);

      const awaiting = advanced.legs.find((l) => l.status === "awaiting_confirmation");
        if (awaiting) {
        const detail = await api.getManualBridgeLeg(advanced.id, awaiting.leg_number);
        setSelected(detail);
        setDealSnapshot({
          currency: detail.currency || currency,
          bid: detail.bid_amount || detail.amount_requested || amount,
          profit: detail.profit_amount,
          total: detail.murabaha_total,
          termMonths: term,
          legNumber: detail.leg_number,
        });
        append(`Desk request ready: ${awaiting.external_ref}. Copy email/JSON, send to BSAS Ops, paste e-certificate.`);
      }

      setMessage("Bursa desk packet generated. Copy the email body and send to BSAS Ops.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start Malaysia flow");
      append(`Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  async function confirmCertificate(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      append(`Confirming Leg ${selected.leg_number} with certificate ${certNumber}…`);
      const confirmed = await api.confirmEcert(selected.transaction_id, selected.leg_number, {
        certificate_number: certNumber,
        issuer,
        seller,
        buyer,
        bid_no: bidNo,
        selling_time: sellingTime,
        selling_date: sellingDate,
        value_date: valueDate,
        product_code: productCode,
        product_description: productDescription,
        unit,
        volume,
        currency: certCurrency,
        price,
        price_myr_equivalent: priceMyr,
        value_amount: valueAmount,
        transaction_type: transactionType,
        file: pdfFile,
      });
      setTransaction(confirmed);
      setMessage(`Leg ${selected.leg_number} confirmed with Bursa e-cert metadata.`);
      setPdfFile(null);
      const nextPending = confirmed.legs.find((l) => l.status === "pending");
      if (nextPending) {
        append("Advancing next leg…");
        if (selected.leg_number === "2") {
          try {
            await api.recordCustomerSale(selected.application_id);
            await api.appointCustomerAgency(selected.application_id);
            append("Customer sale and agency recorded for Leg 3 readiness.");
          } catch {
            append("Business steps may already be recorded.");
          }
        }
        const advanced = await api.advanceManualBridge(selected.transaction_id);
        setTransaction(advanced);
        const awaiting = advanced.legs.find((l) => l.status === "awaiting_confirmation");
        if (awaiting) {
          const detail = await api.getManualBridgeLeg(advanced.id, awaiting.leg_number);
          setSelected(detail);
          setDealSnapshot({
            currency: detail.currency || currency,
            bid: detail.bid_amount || detail.amount_requested || amount,
            profit: detail.profit_amount,
            total: detail.murabaha_total,
            termMonths: term,
            legNumber: detail.leg_number,
          });
          setCertNumber("");
          append(`Next request ready: ${awaiting.external_ref}`);
        } else if (advanced.status === "completed") {
          setSelected(null);
          append("All legs complete. Ready to disburse.");
        }
      } else if (confirmed.status === "completed") {
        setSelected(null);
        append("All legs complete.");
      }

      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Certificate confirm failed");
      append(`Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  async function disburse() {
    if (!transaction) return;
    setBusy(true);
    try {
      const result = await api.createDisbursement(transaction.application_id, transaction.id);
      setMessage(
        `Disbursement created${
          result.tawarruq_certificate
            ? ` · financing cert ${result.tawarruq_certificate.certificate_number}`
            : ""
        }`,
      );
      append("Disbursement created.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Disbursement failed");
    } finally {
      setBusy(false);
    }
  }

  async function rebuildBatch() {
    setBusy(true);
    try {
      const batch = await api.getManualBridgeDeskBatch();
      setDeskBatch(batch);
      setMessage(`Desk batch rebuilt · ${batch.customer_count} customer(s)`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to build desk batch");
    } finally {
      setBusy(false);
    }
  }

  const activeDeal = {
    currency: selected?.currency || dealSnapshot?.currency || currency,
    bid: selected?.bid_amount || selected?.amount_requested || dealSnapshot?.bid || amount,
    profit: selected?.profit_amount || dealSnapshot?.profit,
    total: selected?.murabaha_total || dealSnapshot?.total,
    termMonths: dealSnapshot?.termMonths || term,
    legNumber: selected?.leg_number || dealSnapshot?.legNumber,
  };

  return (
    <PageShell wide>
      <div className="page-grid">
        <div className="span-2">
          <CommodityExplain />
        </div>
        <section className="panel">
          <h2>Start Malaysia Tawarruq</h2>
          <StepCallout
            stepLabel="1–3"
            title="Bank captures the deal, then instructs Buruuj"
            actors={["bank", "customer", "bti"]}
            mode="manual"
          >
            You are acting for the institution here. Pick the onboarded customer, then this creates the
            application, the accepted Murabaha offer, and the first Bursa desk packet. Nothing has
            reached Bursa yet.
          </StepCallout>
          <form className="form" onSubmit={startMalaysiaFlow}>
            <CustomerPicker ref={customerPickerRef} />
            <div className="form-grid">
              <label>
                Bid amount (cost)
                <input value={amount} onChange={(e) => setAmount(e.target.value)} required />
                <span className="meta">Commodity cost on Suq Al-Sila'. This is Leg 1, not a cash loan.</span>
              </label>
              <label>
                Profit rate %
                <input value={profitRate} onChange={(e) => setProfitRate(e.target.value)} required />
                <span className="meta">Disclosed markup. Murabaha total is cost plus this rate.</span>
              </label>
              <label>
                Currency
                <select className="select-input" value={currency} onChange={(e) => setCurrency(e.target.value)}>
                  <option value="KES">KES</option>
                  <option value="MYR">MYR</option>
                  <option value="USD">USD</option>
                </select>
              </label>
              <label>
                Term (months)
                <input
                  type="number"
                  min={1}
                  max={360}
                  value={term}
                  onChange={(e) => setTerm(Number(e.target.value))}
                  required
                />
              </label>
              <label className="span-2">
                Purpose
                <input value={purpose} onChange={(e) => setPurpose(e.target.value)} required />
              </label>
              <div className="span-2">
                <DealTape
                  amount={amount}
                  termMonths={term}
                  profitRatePct={Number(profitRate) || 5}
                  currency={currency}
                  includeSpot={false}
                />
              </div>
            </div>
            <div className="actions">
              <button className="btn btn-primary" type="submit" disabled={busy}>
                {busy ? "Starting" : "Start Suq Al-Sila' desk flow"}
              </button>
              <button
                className="btn btn-secondary"
                type="button"
                disabled={busy}
                onClick={() => void runMockFullFlow()}
              >
                Run mock E2E
              </button>
            </div>
          </form>
        </section>

        <section className="panel">
          <h2>How the handoff works</h2>
          <p className="muted flow-intro">
            This is the twelve-step desk. The commodity is crude palm oil on Bursa Suq Al-Sila' (see What
            the commodity is above). Pick a customer already on Customers, start the desk flow, then run
            only the next unanswered packet. Do not skip ahead. The numbers on Start update as you type
            bid, profit rate, and term.
          </p>
          <ol className="flow-list numbered">
            {MALAYSIA_STEP_GUIDE.map((step) => (
              <li key={step.n}>
                <strong>
                  {step.n}. {step.title}.
                </strong>{" "}
                {step.body}
              </li>
            ))}
          </ol>
          <p className="meta">
            Hard rules: Leg 1 before Leg 2. Customer sale and Wakala before Leg 3. All legs before
            disbursement. Until Buruuj is admitted, this page writes a desk packet. After onboarding, switch
            the institution to live and set the Malaysia commodity desk to bsas or eiger.
          </p>
          <h3>How the desk packet moves</h3>
          <ol className="handoff-list">
            <li>
              <ActorChips actors={["bti", "amanah"]} />
              <span>Engine writes a Bursa-shaped desk email and JSON packet for the pending leg.</span>
            </li>
            <li>
              <ActorChips actors={["bank"]} />
              <span>You copy that packet and send it to BSAS Ops as the Agent purchase instruction.</span>
            </li>
            <li>
              <ActorChips actors={["bursa"]} />
              <span>
                Bursa executes on the exchange, applies fees, and returns the Islamic Services Receipt.
              </span>
            </li>
            <li>
              <ActorChips actors={["bank", "bti"]} />
              <span>You paste the certificate below; the engine confirms the leg and unlocks the next.</span>
            </li>
            <li>
              <ActorChips actors={["bti", "customer"]} />
              <span>After Leg 3 the engine disburses and issues the financing certificate.</span>
            </li>
          </ol>
          {inbox && (
            <div className="info-grid" style={{ marginTop: "1rem" }}>
              <div className="info-item">
                <span>Inbox</span>
                <strong className="mono" style={{ fontSize: "0.75rem" }}>
                  {inbox.inbox_dir}
                </strong>
              </div>
              <div className="info-item">
                <span>Requests</span>
                <strong>{inbox.request_count}</strong>
              </div>
              <div className="info-item">
                <span>Replies</span>
                <strong>{inbox.reply_count}</strong>
              </div>
              <div className="info-item">
                <span>Unanswered</span>
                <strong>{inbox.unanswered_request_refs.length}</strong>
              </div>
            </div>
          )}
        </section>

        {(error || message) && (
          <div className="span-2">
            {error && <Alert tone="error">{error}</Alert>}
            {message && <Alert tone="success">{message}</Alert>}
          </div>
        )}

        <section className="panel span-2">
          <div className="table-toolbar">
            <div>
              <h2>Bursa desk batch email</h2>
              <p className="muted">
                Multi-customer REQUEST FOR LIVE ACCESS format (same shape as the BSAS Ops sample)
              </p>
            </div>
            <button type="button" className="btn btn-secondary btn-sm" onClick={rebuildBatch} disabled={busy}>
              Rebuild batch
            </button>
          </div>
          <StepCallout
            stepLabel="4"
            title="Leg 1 instruction leaving Buruuj for the Bursa desk"
            actors={["bti", "bursa"]}
            mode="manual"
          >
            One email covering every unanswered Leg 1 packet. Each line is a spot buy of palm oil at the
            bid (cost). Send it to BSAS Ops as-is. The format matches what their desk expects.
          </StepCallout>
          {deskBatch ? (
            <>
              <div className="info-grid">
                <div className="info-item">
                  <span>Institution</span>
                  <strong>{deskBatch.institution_name || deskBatch.institution_code || "—"}</strong>
                </div>
                <div className="info-item">
                  <span>Customers in batch</span>
                  <strong>{deskBatch.customer_count}</strong>
                </div>
              </div>
              {deskBatch.customers.length === 1 ? (
                <MalaysiaLegTape
                  currency={deskBatch.customers[0].currency || "MYR"}
                  bid={String(deskBatch.customers[0].bid_amount)}
                  profit={String(deskBatch.customers[0].profit_amount)}
                  total={String(deskBatch.customers[0].murabaha_total)}
                  legNumber="1"
                />
              ) : deskBatch.customers.length > 1 ? (
                <MalaysiaLegTape
                  currency={deskBatch.customers[0].currency || "MYR"}
                  bid={String(deskBatch.customers.reduce((sum, row) => sum + Number(row.bid_amount || 0), 0))}
                  profit={String(deskBatch.customers.reduce((sum, row) => sum + Number(row.profit_amount || 0), 0))}
                  total={String(deskBatch.customers.reduce((sum, row) => sum + Number(row.murabaha_total || 0), 0))}
                  legNumber="1"
                />
              ) : null}
              <div className="actions" style={{ margin: "0.75rem 0" }}>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={() => copyText("batch", deskBatch.email_body)}
                >
                  {copied === "batch" ? "Copied" : "Copy batch email"}
                </button>
              </div>
              <pre className="code-block">{deskBatch.email_body}</pre>
            </>
          ) : (
            <EmptyState
              title="No unanswered Leg 1 packets"
              description="Start a manual-bridge flow to populate the Bursa desk batch."
            />
          )}
        </section>

        <section className="panel">
          <div className="table-toolbar">
            <div>
              <h2>Pending certificate paste</h2>
              <p className="muted">Legs awaiting BSAS e-certificate confirmation</p>
            </div>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => refresh()} disabled={loading}>
              Refresh
            </button>
          </div>
          <StepCallout
            stepLabel="5"
            title="Waiting on Bursa"
            actors={["bursa", "bti"]}
            mode="external"
          >
            Each row is a leg the engine has already instructed. It stays here until BSAS Ops returns the
            e-certificate, so a long queue means the desk owes you replies, not that the engine is stuck.
            Bid is the commodity cost. Murabaha is cost plus profit.
          </StepCallout>

          {loading ? (
            <LoadingPanel rows={4} />
          ) : pending.length === 0 ? (
            <EmptyState
              title="No pending certificates"
              description="Start a manual-bridge flow, or advance an existing transaction so Amanah generates a BSAS request."
            />
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Customer</th>
                    <th>Bid / Murabaha</th>
                    <th>Product</th>
                    <th>Leg</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {pending.map((item) => (
                    <tr key={`${item.transaction_id}-${item.leg_number}`}>
                      <td data-label="Customer">
                        <div>{item.customer_name || item.customer_ref || "—"}</div>
                        <div className="meta">{item.external_ref}</div>
                      </td>
                      <td data-label="Bid / Murabaha">
                        <div>
                          {item.currency || "MYR"} {item.bid_amount ?? item.amount_requested}
                        </div>
                        <div className="meta">Murabaha {item.murabaha_total ?? "—"}</div>
                      </td>
                      <td data-label="Product">
                        <code>{item.product_code || item.commodity_code}</code>
                        <div className="meta">Agent ({item.purchase_type || "A"})</div>
                      </td>
                      <td data-label="Leg">
                        <span className={statusBadgeClass(item.leg_status)}>{item.leg_label}</span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => openItem(item)}
                        >
                          Open
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="panel">
          <h2>Paste e-certificate</h2>
          <StepCallout
            stepLabel="5–6"
            title="Recording Bursa's evidence back into Buruuj"
            actors={["bank", "bti", "shariah"]}
            mode="manual"
          >
            Copy the fields straight off the Bursa receipt. This is the evidence the Shariah audit chain
            points at, so the certificate number and amounts must match the receipt exactly.
          </StepCallout>
          {!selected ? (
            <EmptyState
              title="Select a pending leg"
              description="Open an item from the pending list to view the Bursa desk packet and paste the certificate."
            />
          ) : (
            <>
              <MalaysiaLegTape
                currency={selected.currency || "MYR"}
                bid={String(selected.bid_amount || selected.amount_requested || "0")}
                profit={String(selected.profit_amount ?? "0")}
                total={String(selected.murabaha_total ?? "0")}
                legNumber={String(selected.leg_number ?? "1")}
              />
              <div className="info-grid">
                <div className="info-item">
                  <span>End customer</span>
                  <strong>{selected.customer_name || selected.customer_ref || "—"}</strong>
                </div>
                <div className="info-item">
                  <span>Product</span>
                  <strong>
                    {selected.product_code || selected.commodity_code} · Agent ({selected.purchase_type || "A"})
                  </strong>
                </div>
                <div className="info-item">
                  <span>Bid / Profit / Murabaha</span>
                  <strong>
                    {selected.currency} {selected.bid_amount} / {selected.profit_amount} / {selected.murabaha_total}
                  </strong>
                </div>
                <div className="info-item">
                  <span>External ref</span>
                  <strong className="mono">{selected.external_ref ?? "—"}</strong>
                </div>
              </div>

              {selected.ops_instructions?.length > 0 && (
                <ol className="flow-list numbered" style={{ marginTop: "1rem" }}>
                  {selected.ops_instructions.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
              )}

              {selected.email_body ? (
                <>
                  <div className="actions" style={{ margin: "0.75rem 0" }}>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => copyText("email", selected.email_body || "")}
                    >
                      {copied === "email" ? "Copied" : "Copy desk email"}
                    </button>
                    {selected.request ? (
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => copyText("json", JSON.stringify(selected.request, null, 2))}
                      >
                        {copied === "json" ? "Copied" : "Copy JSON packet"}
                      </button>
                    ) : null}
                  </div>
                  <pre className="code-block">{selected.email_body}</pre>
                </>
              ) : selected.request ? (
                <pre className="code-block">{JSON.stringify(selected.request, null, 2)}</pre>
              ) : null}

              <form className="form" onSubmit={confirmCertificate} style={{ marginTop: "1rem" }}>
                <p className="muted">Enter fields from the Bursa Suq Al-Sila' Islamic Services Receipt and optionally upload the PDF.</p>
                <div className="form-grid">
                  <label className="span-2">
                    Certificate number
                    <input
                      value={certNumber}
                      onChange={(e) => setCertNumber(e.target.value)}
                      placeholder="CPO28AUG26-0009491-000"
                      required
                    />
                  </label>
                  <label className="span-2">
                    Issuer
                    <input value={issuer} onChange={(e) => setIssuer(e.target.value)} />
                  </label>
                  <label>
                    Seller
                    <input value={seller} onChange={(e) => setSeller(e.target.value)} placeholder="Hidaya Said ( 000 )" />
                  </label>
                  <label>
                    Buyer
                    <input value={buyer} onChange={(e) => setBuyer(e.target.value)} />
                  </label>
                  <label>
                    Bid no
                    <input value={bidNo} onChange={(e) => setBidNo(e.target.value)} />
                  </label>
                  <label>
                    Selling time
                    <input value={sellingTime} onChange={(e) => setSellingTime(e.target.value)} placeholder="19:00:50.857" />
                  </label>
                  <label>
                    Selling date
                    <input value={sellingDate} onChange={(e) => setSellingDate(e.target.value)} placeholder="28 AUGUST 2026" />
                  </label>
                  <label>
                    Value date
                    <input value={valueDate} onChange={(e) => setValueDate(e.target.value)} placeholder="28 AUGUST 2026" />
                  </label>
                  <label>
                    Product code
                    <input value={productCode} onChange={(e) => setProductCode(e.target.value)} />
                  </label>
                  <label>
                    Product description
                    <input value={productDescription} onChange={(e) => setProductDescription(e.target.value)} />
                  </label>
                  <label>
                    Unit
                    <input value={unit} onChange={(e) => setUnit(e.target.value)} />
                  </label>
                  <label>
                    Volume
                    <input value={volume} onChange={(e) => setVolume(e.target.value)} placeholder=".32293179" />
                  </label>
                  <label>
                    Currency
                    <input value={certCurrency} onChange={(e) => setCertCurrency(e.target.value)} />
                  </label>
                  <label>
                    Price
                    <input value={price} onChange={(e) => setPrice(e.target.value)} placeholder="154831.46067416" />
                  </label>
                  <label>
                    Price (MYR equivalent)
                    <input value={priceMyr} onChange={(e) => setPriceMyr(e.target.value)} placeholder="4823.00" />
                  </label>
                  <label>
                    Value
                    <input value={valueAmount} onChange={(e) => setValueAmount(e.target.value)} placeholder="50000.00" />
                  </label>
                  <label>
                    Transaction type
                    <input value={transactionType} onChange={(e) => setTransactionType(e.target.value)} />
                  </label>
                  <label className="span-2">
                    E-cert PDF (optional)
                    <input
                      type="file"
                      accept="application/pdf,.pdf"
                      onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
                    />
                  </label>
                </div>
                {pdfFile ? <p className="meta">Selected: {pdfFile.name}</p> : null}
                <div className="actions">
                  <button className="btn btn-primary" type="submit" disabled={busy}>
                    Confirm e-certificate
                  </button>
                  <Link className="btn btn-secondary" to={`/transactions/${selected.transaction_id}`}>
                    View transaction
                  </Link>
                </div>
              </form>
            </>
          )}
        </section>

        {transaction && (
          <section className="panel span-2">
            <div className="panel-header">
              <div>
                <h2>Transaction {transaction.id.slice(0, 8)}…</h2>
                <p className="muted">
                  Mode: {transaction.mode} · Status: {transaction.status}. Leg 1 buy, Leg 2 customer
                  title, Leg 3 independent sale. Disburse only after Leg 3.
                </p>
              </div>
              <span className={statusBadgeClass(transaction.status)}>{transaction.status}</span>
            </div>
            {transaction.status === "completed" ? (
              <MalaysiaSettlementTape
                currency={activeDeal.currency}
                bid={activeDeal.bid}
                profit={activeDeal.profit}
                total={activeDeal.total}
                termMonths={activeDeal.termMonths}
              />
            ) : (
              <MalaysiaLegTape
                currency={activeDeal.currency}
                bid={String(activeDeal.bid ?? "0")}
                profit={String(activeDeal.profit ?? "0")}
                total={String(activeDeal.total ?? "0")}
                legNumber={String(activeDeal.legNumber ?? "1")}
              />
            )}

            {/* ── 3-step progress timeline ── */}
            <div className="bsas-timeline">
              {(["1", "2", "3"] as const).map((num, i) => {
                const leg = transaction.legs.find((l: Leg) => l.leg_number === num);
                const labels: Record<string, string> = { "1": "Spot Purchase", "2": "Murabaha Sale", "3": "Liquidation" };
                const done = leg?.status === "confirmed";
                const active = !done && leg?.status === "awaiting_confirmation";
                return (
                  <div key={num} className={`bsas-tl-step${done ? " done" : active ? " active" : ""}`}>
                    <div className="bsas-tl-dot">{done ? "✓" : num}</div>
                    <div className="bsas-tl-info">
                      <div className="bsas-tl-label">{labels[num]}</div>
                      {leg?.executed_at && (
                        <div className="bsas-tl-time">
                          {new Date(leg.executed_at).toLocaleString("en-KE", { dateStyle: "short", timeStyle: "medium" })}
                        </div>
                      )}
                      {leg?.certificate?.certificate_number && (
                        <div className="bsas-tl-cert">{leg.certificate.certificate_number}</div>
                      )}
                    </div>
                    {i < 2 && <div className="bsas-tl-connector" />}
                  </div>
                );
              })}
            </div>

            <div className="legs-grid">
              {transaction.legs.map((leg) => (
                <article key={leg.id} className="leg-card">
                  <div className="leg-header">
                    <strong>{LEG_ACTION[leg.leg_number] ?? leg.leg_number}</strong>
                    <span className={statusBadgeClass(leg.status)}>{leg.status}</span>
                  </div>
                  {leg.external_ref && <p className="meta">Ref: {leg.external_ref}</p>}
                  {leg.certificate && (
                    <>
                      <p className="meta">Cert: {leg.certificate.certificate_number}</p>
                      {leg.certificate.seller ? <p className="meta">Seller: {leg.certificate.seller}</p> : null}
                      {leg.certificate.product_code ? (
                        <p className="meta">
                          {leg.certificate.product_code}
                          {leg.certificate.value_amount
                            ? ` · ${leg.certificate.currency || ""} ${leg.certificate.value_amount}`
                            : ""}
                        </p>
                      ) : null}
                      {leg.certificate.pdf_filename ? (
                        <p className="meta">PDF: {leg.certificate.pdf_filename}</p>
                      ) : null}
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        style={{ marginTop: "0.5rem" }}
                        onClick={() => { setViewCert(leg.certificate!); setViewCertLeg(leg.leg_number); }}
                      >
                        View receipt
                      </button>
                    </>
                  )}
                </article>
              ))}
            </div>
            {transaction.status === "completed" && (
              <div className="actions" style={{ marginTop: "1rem" }}>
                <button type="button" className="btn btn-primary" onClick={disburse} disabled={busy}>
                  Disburse funds
                </button>
              </div>
            )}
          </section>
        )}

        {log.length > 0 && (
          <section className="panel span-2">
            <h2>Activity log</h2>
            <ul className="log-list">
              {log.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ul>
          </section>
        )}
      </div>

      {/* BSAS Certificate Modal */}
      {viewCert && (
        <BsasCertificateModal
          certificate={viewCert}
          legLabel={viewCertLeg}
          onClose={() => setViewCert(null)}
        />
      )}
    </PageShell>
  );
}
