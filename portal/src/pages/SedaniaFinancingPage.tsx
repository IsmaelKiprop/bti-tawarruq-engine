import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { CustomerPicker, type CustomerPickerHandle } from "../components/CustomerPicker";
import { HowItWorks, PageExplain } from "../components/PageExplain";
import { Alert, EmptyState, LoadingPanel, PageShell, statusBadgeClass } from "../components/PageShell";
import { api, type SedaniaFinancing } from "../api/client";
import { HOW_IT_WORKS, PAGE_EXPLAINS } from "../config/pageExplainers";
import "../components/ui.css";

const DOC_BUTTONS = [
  { kind: "purchase_order", label: "Purchase Order" },
  { kind: "commodity_invoice", label: "Commodity Invoice" },
  { kind: "delivery_order", label: "Delivery Order" },
  { kind: "trading_ecert", label: "Trading e-Cert" },
  { kind: "muqassah", label: "Muqassah" },
  { kind: "casa_advice", label: "CASA advice" },
  { kind: "physical_delivery", label: "Physical delivery" },
];

export function SedaniaFinancingPage() {
  const pickerRef = useRef<CustomerPickerHandle>(null);
  const [runs, setRuns] = useState<SedaniaFinancing[]>([]);
  const [selected, setSelected] = useState<SedaniaFinancing | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [amount, setAmount] = useState("10000.00");
  const [currency, setCurrency] = useState("MYR");
  const [tenor, setTenor] = useState(12);
  const [flowVariant, setFlowVariant] = useState<"approved_wakeel" | "aaoifi_rasul">("approved_wakeel");
  const [deliveryMode, setDeliveryMode] = useState<"constructive" | "physical">("constructive");
  const [casaAccount, setCasaAccount] = useState("CASA-DIB-0001");
  const [appointSasc, setAppointSasc] = useState(true);

  const loadRuns = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const rows = await api.listSedaniaFinancing();
      setRuns(rows);
      if (rows[0] && !selected) setSelected(rows[0]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load Sedania financing runs");
    } finally {
      setLoading(false);
    }
  }, [selected]);

  useEffect(() => {
    void loadRuns();
  }, [loadRuns]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const customer = await pickerRef.current?.ensureCustomer();
      if (!customer) throw new Error("Select or register a customer first.");
      const run = await api.createSedaniaFinancing({
        customer_id: customer.id,
        amount,
        tenor,
        currency,
        flow_variant: flowVariant,
        delivery_mode: deliveryMode,
        appoint_sasc: appointSasc,
        casa_account: casaAccount || undefined,
        institution_id: customer.institution_id,
        client_request_id: `SED-${Date.now()}`,
      });
      setSelected(run);
      setRuns((current) => [run, ...current.filter((row) => row.execution_id !== run.execution_id)]);
      setMessage(
        run.delivery_mode === "physical"
          ? "CMP and AS SIDQ legs completed. Mark settlement, then arrange physical delivery."
          : "Financing completed through AS SIDQ. Review the trade pack, muqassah, and CASA advice.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sedania financing failed");
    } finally {
      setBusy(false);
    }
  }

  async function onPhysicalDelivery() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const run = await api.arrangeSedaniaPhysicalDelivery(selected.execution_id, true);
      setSelected(run);
      setRuns((current) => current.map((row) => (row.execution_id === run.execution_id ? run : row)));
      setMessage("SEDANIA As Salam Capital has been notified to arrange physical delivery with the supplier.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Physical delivery failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell wide>
      <PageExplain content={PAGE_EXPLAINS["/sedania"]} />
      <HowItWorks content={HOW_IT_WORKS["/sedania"]} />
      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}

      <div className="page-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>New AS SIDQ facility</h2>
              <p className="muted">Runs the deck from application through CASA credit, or physical delivery.</p>
            </div>
          </div>
          <form className="stack gap-md" onSubmit={onSubmit}>
            <CustomerPicker ref={pickerRef} />
            <label>
              Amount
              <input value={amount} onChange={(event) => setAmount(event.target.value)} required />
            </label>
            <label>
              Currency
              <select value={currency} onChange={(event) => setCurrency(event.target.value)}>
                <option value="MYR">MYR</option>
                <option value="USD">USD</option>
                <option value="KES">KES</option>
              </select>
            </label>
            <label>
              Tenor (months)
              <input
                type="number"
                min={1}
                max={120}
                value={tenor}
                onChange={(event) => setTenor(Number(event.target.value))}
              />
            </label>
            <label>
              Flow
              <select
                value={flowVariant}
                onChange={(event) => setFlowVariant(event.target.value as "approved_wakeel" | "aaoifi_rasul")}
              >
                <option value="approved_wakeel">Approved: SASC as wakeel + muqassah</option>
                <option value="aaoifi_rasul">AAOIFI: SASC as Rasul</option>
              </select>
            </label>
            <label>
              Delivery
              <select
                value={deliveryMode}
                onChange={(event) => setDeliveryMode(event.target.value as "constructive" | "physical")}
              >
                <option value="constructive">Constructive possession, then independent sale</option>
                <option value="physical">Keep commodity (qabd hakiki)</option>
              </select>
            </label>
            <label>
              CASA account
              <input value={casaAccount} onChange={(event) => setCasaAccount(event.target.value)} />
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={appointSasc}
                onChange={(event) => setAppointSasc(event.target.checked)}
              />
              Appoint SEDANIA As Salam Capital independently
            </label>
            <button className="btn btn-primary" type="submit" disabled={busy}>
              {busy ? "Running…" : "Run financing"}
            </button>
          </form>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Current run</h2>
              <p className="muted">Steps, SASC role, and the four AS SIDQ documents.</p>
            </div>
            {selected ? <span className={statusBadgeClass(selected.status)}>{selected.status}</span> : null}
          </div>
          {selected ? (
            <>
              <div className="info-grid">
                <div className="info-item">
                  <span>Amount</span>
                  <strong>
                    {selected.currency} {selected.amount}
                  </strong>
                </div>
                <div className="info-item">
                  <span>Deferred</span>
                  <strong>
                    {selected.currency} {selected.deferred_price}
                  </strong>
                </div>
                <div className="info-item">
                  <span>SASC role</span>
                  <strong>{selected.agency_role}</strong>
                </div>
                <div className="info-item">
                  <span>CASA</span>
                  <strong>{selected.casa_account || "—"}</strong>
                </div>
              </div>
              <ol className="step-list">
                {selected.steps.map((step) => (
                  <li key={step.id}>
                    <div>
                      <strong>
                        {step.n}. {step.title}
                      </strong>
                      <p className="muted">{step.detail}</p>
                    </div>
                    <span className={statusBadgeClass(step.status)}>{step.status}</span>
                  </li>
                ))}
              </ol>
              <div className="actions-row wrap">
                {DOC_BUTTONS.map((doc) => {
                  const available = Boolean(selected.certificates[doc.kind]);
                  return (
                    <button
                      key={doc.kind}
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={!available || busy}
                      onClick={() => api.downloadSedaniaDocument(selected.execution_id, doc.kind)}
                    >
                      {doc.label}
                    </button>
                  );
                })}
                {selected.delivery_mode === "physical" ? (
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    disabled={busy || selected.status === "completed"}
                    onClick={() => void onPhysicalDelivery()}
                  >
                    Settle and arrange delivery
                  </button>
                ) : null}
              </div>
              <p className="meta">
                PO {selected.purchase_order_ref || "—"} · Invoice {selected.commodity_invoice_ref || "—"} · DO{" "}
                {selected.delivery_order_ref || "—"} · e-Cert {selected.trading_ecert_ref || "—"}
              </p>
            </>
          ) : (
            <EmptyState
              title="No Sedania facility yet"
              description="Run the approved wakeel flow or the AAOIFI Rasul flow from the form."
            />
          )}
        </section>
      </div>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Recent facilities</h2>
            <p className="muted">Bank CMP runs only. SACCO execute stays on Webhooks and Keys.</p>
          </div>
        </div>
        {loading ? (
          <LoadingPanel rows={3} />
        ) : runs.length === 0 ? (
          <EmptyState title="None yet" description="The first run will appear here with CASA and document refs." />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Created</th>
                  <th>Flow</th>
                  <th>Amount</th>
                  <th>Status</th>
                  <th>CASA</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((row) => (
                  <tr key={row.execution_id}>
                    <td>
                      <button type="button" className="btn btn-secondary btn-sm" onClick={() => setSelected(row)}>
                        {row.created_at.slice(0, 19).replace("T", " ")}
                      </button>
                    </td>
                    <td>
                      {row.flow_variant} / {row.delivery_mode}
                    </td>
                    <td>
                      {row.currency} {row.amount}
                    </td>
                    <td>
                      <span className={statusBadgeClass(row.status)}>{row.status}</span>
                    </td>
                    <td className="mono">{row.casa_ref || "—"}</td>
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
