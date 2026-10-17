import { FormEvent, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { CustomerPicker, type CustomerPickerHandle } from "../components/CustomerPicker";
import { DealTape } from "../components/DealTape";
import { HowItWorks, PageExplain } from "../components/PageExplain";
import { Alert, PageShell } from "../components/PageShell";
import { DEFAULT_PROFIT_RATE_PCT } from "../config/kenyaOps";
import { HOW_IT_WORKS, PAGE_EXPLAINS } from "../config/pageExplainers";
import "../components/ui.css";

export function NewApplicationPage() {
  const navigate = useNavigate();
  const customerPickerRef = useRef<CustomerPickerHandle>(null);
  const [amount, setAmount] = useState("");
  const [termMonths, setTermMonths] = useState(6);
  const [purpose, setPurpose] = useState("Working capital");
  const [profitRatePct, setProfitRatePct] = useState(DEFAULT_PROFIT_RATE_PCT);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const customer = await customerPickerRef.current?.ensureCustomer();
      if (!customer) throw new Error("Select or register a customer first.");
      const created = await api.createApplication({
        customer_id: customer.id,
        customer_name: customer.full_name,
        amount_requested: amount,
        term_months: termMonths,
        purpose,
      });
      navigate(`/applications/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create application");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell wide>
      <PageExplain content={PAGE_EXPLAINS["/applications/new"] || PAGE_EXPLAINS["/applications"]} />
      <HowItWorks content={HOW_IT_WORKS["/applications/new"] || HOW_IT_WORKS["/applications"]} />
      {error ? <Alert tone="error">{error}</Alert> : null}
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>New application</h2>
            <p className="muted">Pick an existing customer, then lock cost and term.</p>
          </div>
          <Link className="btn btn-secondary btn-sm" to="/customers">
            Customers
          </Link>
        </div>
        <form className="grid-2" onSubmit={onSubmit}>
          <div className="span-2">
            <CustomerPicker ref={customerPickerRef} />
          </div>
          <label>
            Purpose
            <input value={purpose} onChange={(e) => setPurpose(e.target.value)} required />
          </label>
          <label>
            Amount (commodity cost)
            <input value={amount} onChange={(e) => setAmount(e.target.value)} required />
          </label>
          <label>
            Term (months)
            <input
              type="number"
              min={1}
              value={termMonths}
              onChange={(e) => setTermMonths(Number(e.target.value))}
              required
            />
          </label>
          <div className="span-2">
            <DealTape
              amount={amount || 0}
              termMonths={termMonths}
              profitRatePct={profitRatePct}
              onProfitRateChange={setProfitRatePct}
            />
          </div>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? "Creating…" : "Create application"}
          </button>
        </form>
      </section>
    </PageShell>
  );
}
