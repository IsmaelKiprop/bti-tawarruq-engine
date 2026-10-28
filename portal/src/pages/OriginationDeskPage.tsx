import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api, type DeskApprover, type DeskCase } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import { DESK_STEPS, DOCUMENT_TYPES, PRODUCT_TYPES, deskPayload, deskTimestamps, maxDeskStep } from "../config/fiDesk";

const fieldClass = "rounded-sm border border-border bg-surface-elevated px-2.5 py-1.5 text-sm text-foreground";
const labelClass = "flex min-w-0 flex-col gap-1 text-xs uppercase tracking-wide text-muted";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className={labelClass}>
      <span>{label}</span>
      {children}
    </label>
  );
}

function ReadRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-sm border border-border bg-surface-elevated px-3 py-2">
      <dt className="text-[0.7rem] uppercase tracking-wide text-muted">{label}</dt>
      <dd className="m-0 text-sm">{value || "—"}</dd>
    </div>
  );
}

function asRecord(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object") return {};
  return Object.fromEntries(Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, item == null ? "" : String(item)]));
}

export function OriginationDeskPage() {
  const { user } = useAuth();
  const isApprover = user?.role === "fi_approver";
  const canWrite = Boolean(user?.permissions.includes("write_ops"));
  const [cases, setCases] = useState<DeskCase[]>([]);
  const [approvers, setApprovers] = useState<DeskApprover[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [record, setRecord] = useState<DeskCase | null>(null);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [devCode, setDevCode] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [comments, setComments] = useState("");
  const [form, setForm] = useState({
    customer_id: "",
    document_type: "National ID",
    customer_name: "",
    customer_phone: "",
    customer_email: "",
    approved_facility_amount: "",
    facility_product_type: "Airtime",
    assigned_approver_id: "",
    profit: "",
    purchase_complete: "Yes",
    offer_reference: "",
    contract_reference: "",
    settlement_ref: "",
    customer_account_number: "",
    customer_branch: "",
    facility_account: "",
    repayment_installments: "",
    first_installment_due_date: "",
    last_installment_due_date: "",
  });

  const reachable = record ? maxDeskStep(record.current_step, record.status) : 1;

  async function loadList() {
    const [rows, desks] = await Promise.all([
      api.listDeskCases(user?.institution_id || undefined),
      canWrite ? api.listDeskApprovers(user?.institution_id || undefined).catch(() => [] as DeskApprover[]) : Promise.resolve([] as DeskApprover[]),
    ]);
    setCases(rows);
    setApprovers(desks);
    if (desks[0] && !form.assigned_approver_id) {
      setForm((current) => ({ ...current, assigned_approver_id: current.assigned_approver_id || desks[0].id }));
    }
  }

  async function openCase(id: string) {
    const next = await api.getDeskCase(id);
    setRecord(next);
    setSelectedId(id);
    setStep(Math.max(0, Math.min(7, next.current_step - 1)));
    const orig = deskPayload(next, "origination");
    setForm((current) => ({
      ...current,
      ...orig,
      assigned_approver_id: next.assigned_approver_id || current.assigned_approver_id,
      profit: deskPayload(next, "murabaha").profit || current.profit,
      offer_reference: deskPayload(next, "murabaha").offer_reference || current.offer_reference,
      contract_reference: deskPayload(next, "murabaha").contract_reference || current.contract_reference,
      settlement_ref: deskPayload(next, "clearing").settlement_ref || current.settlement_ref,
      customer_account_number: deskPayload(next, "proceeds").customer_account_number || current.customer_account_number,
      customer_branch: deskPayload(next, "proceeds").customer_branch || current.customer_branch,
      facility_account: deskPayload(next, "murabaha").facility_account || current.facility_account,
      repayment_installments: deskPayload(next, "murabaha").repayment_installments || current.repayment_installments,
      first_installment_due_date: deskPayload(next, "murabaha").first_installment_due_date || current.first_installment_due_date,
      last_installment_due_date: deskPayload(next, "murabaha").last_installment_due_date || current.last_installment_due_date,
    }));
    setComments(next.approval_comments || "");
  }

  useEffect(() => {
    setLoading(true);
    loadList()
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load origination desk"))
      .finally(() => setLoading(false));
  }, [user?.institution_id]);

  async function run(label: string, work: () => Promise<DeskCase | void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const next = await work();
      if (next) {
        setRecord(next);
        setSelectedId(next.id);
        setStep(Math.max(0, Math.min(7, next.current_step - 1)));
      }
      await loadList();
      setMessage(label);
    } catch (err) {
      setError(err instanceof Error ? err.message : label);
    } finally {
      setBusy(false);
    }
  }

  const orig = deskPayload(record, "origination");
  const initiate = deskPayload(record, "initiate");
  const murabaha = deskPayload(record, "murabaha");
  const resale = deskPayload(record, "resale");
  const proceeds = deskPayload(record, "proceeds");
  const clearing = deskPayload(record, "clearing");
  const stamps = deskTimestamps(record);
  const institutionName = record?.institution_name || user?.institution_name || "Financial institution";
  const originationLocked = record != null && record.status !== "returned";
  const initiateLocked = Boolean(record && record.current_step > 3);
  const murabahaLocked = Boolean(record && record.current_step > 4);

  const deferred = useMemo(() => {
    const cost = Number(initiate.commodity_quantity || orig.approved_facility_amount || 0);
    const profit = Number(form.profit || murabaha.profit || 0);
    if (!cost && !profit) return "—";
    return String(cost + profit);
  }, [form.profit, initiate.commodity_quantity, murabaha.profit, orig.approved_facility_amount]);

  function goToStep(index: number) {
    if (index + 1 > reachable) return;
    setStep(index);
  }

  return (
    <PageShell wide>
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="m-0 text-lg font-semibold">Origination</h2>
          <p className="muted m-0 mt-1 text-sm">
            {isApprover ? "Approve assigned facility requests." : "Eight-step FI Ops desk. Later steps stay locked until the current one is done."}
          </p>
        </div>
        {canWrite ? (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setRecord(null);
              setSelectedId("");
              setStep(0);
              setDevCode("");
              setOtpCode("");
            }}
          >
            New case
          </button>
        ) : null}
      </header>

      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}
      {devCode ? <Alert tone="info">Tester OTP: {devCode}</Alert> : null}

      {loading ? <LoadingPanel rows={4} /> : null}

      {!loading && cases.length ? (
        <label className={labelClass}>
          Open case
          <select
            className={fieldClass}
            value={selectedId}
            onChange={(event) => {
              if (event.target.value) void openCase(event.target.value);
            }}
          >
            <option value="">Select a case…</option>
            {cases.map((item) => (
              <option key={item.id} value={item.id}>
                {asRecord(item.payload.origination).customer_name || item.id.slice(0, 8)} · {item.status} · step {item.current_step}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {!loading && !cases.length && isApprover ? (
        <EmptyState title="No assigned requests" description="FI Ops must submit an origination case to you first." />
      ) : null}

      <ol className="m-0 flex list-none items-start p-0">
        {DESK_STEPS.map((item, index) => {
          const current = index === step;
          const locked = index + 1 > reachable;
          const done = index + 1 < reachable;
          return (
            <li key={item.id} className="flex min-w-0 flex-1 flex-col gap-1">
              <div className="flex items-center">
                <button
                  type="button"
                  className={`grid size-7 shrink-0 place-items-center rounded-full border text-xs ${
                    current || done ? "border-primary bg-primary text-primary-foreground" : locked ? "border-border text-muted" : "border-primary bg-surface text-primary"
                  }`}
                  disabled={locked}
                  onClick={() => goToStep(index)}
                >
                  {done && !current ? "✓" : item.n}
                </button>
                {index < DESK_STEPS.length - 1 ? <span className={`mx-1 h-px min-w-2 flex-1 ${index + 1 < reachable ? "bg-primary" : "bg-border"}`} /> : null}
              </div>
              <span className={`hidden pr-2 text-[0.65rem] uppercase tracking-wide sm:block ${current ? "text-foreground" : "text-muted"}`}>{item.title}</span>
            </li>
          );
        })}
      </ol>

      <section className="rounded-sm border border-border bg-surface p-3">
        {step === 0 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Document type">
              <select className={fieldClass} value={form.document_type} disabled={originationLocked} onChange={(e) => setForm({ ...form, document_type: e.target.value })}>
                {DOCUMENT_TYPES.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </Field>
            <Field label="ID">
              <input className={fieldClass} value={form.customer_id} disabled={originationLocked} onChange={(e) => setForm({ ...form, customer_id: e.target.value })} />
            </Field>
            <Field label="Customer name">
              <input className={fieldClass} value={form.customer_name} disabled={originationLocked} onChange={(e) => setForm({ ...form, customer_name: e.target.value })} />
            </Field>
            <Field label="Customer phone">
              <input className={fieldClass} value={form.customer_phone} disabled={originationLocked} onChange={(e) => setForm({ ...form, customer_phone: e.target.value })} />
            </Field>
            <Field label="Customer email">
              <input className={fieldClass} type="email" value={form.customer_email} disabled={originationLocked} onChange={(e) => setForm({ ...form, customer_email: e.target.value })} />
            </Field>
            <Field label="Approved facility amount">
              <input
                className={fieldClass}
                type="number"
                min="0"
                step="0.01"
                value={form.approved_facility_amount}
                disabled={originationLocked}
                onChange={(e) => setForm({ ...form, approved_facility_amount: e.target.value })}
              />
            </Field>
            <Field label="Commodity type">
              <select className={fieldClass} value={form.facility_product_type} disabled={originationLocked} onChange={(e) => setForm({ ...form, facility_product_type: e.target.value })}>
                {Array.from(new Set<string>([...PRODUCT_TYPES, form.facility_product_type])).filter(Boolean).map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </Field>
            <Field label="FI Approver">
              <select className={fieldClass} value={form.assigned_approver_id} disabled={originationLocked} onChange={(e) => setForm({ ...form, assigned_approver_id: e.target.value })}>
                {approvers.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.full_name}
                  </option>
                ))}
              </select>
            </Field>
            {canWrite && (!record || record.status === "returned") ? (
              <div className="sm:col-span-2">
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={busy}
                  onClick={() => {
                    if (Number(form.approved_facility_amount) < 0) {
                      setError("Approved facility amount cannot be negative");
                      return;
                    }
                    void run("Submitted to FI Approver", () =>
                      api.createDeskCase({
                        customer_id: form.customer_id,
                        document_type: form.document_type,
                        customer_name: form.customer_name,
                        customer_phone: form.customer_phone,
                        customer_email: form.customer_email,
                        approved_facility_amount: form.approved_facility_amount,
                        facility_product_type: form.facility_product_type,
                        assigned_approver_id: form.assigned_approver_id,
                      }),
                    );
                  }}
                >
                  {busy ? "Sending…" : "Send to FI Approver"}
                </button>
              </div>
            ) : null}
          </div>
        ) : null}

        {step === 1 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <ReadRow label="Request id" value={record?.id} />
            <ReadRow label="Amount" value={orig.approved_facility_amount} />
            <ReadRow label="Requester" value={record?.requested_by_name} />
            <ReadRow label="Approver" value={record?.assigned_approver_name} />
            <ReadRow label="Status" value={record?.status} />
            <ReadRow label="Comments" value={record?.approval_comments} />
            {isApprover && record?.status === "pending_approval" ? (
              <>
                <Field label="Approval comments">
                  <textarea className={fieldClass} value={comments} onChange={(e) => setComments(e.target.value)} />
                </Field>
                <div className="flex flex-wrap gap-2 self-end">
                  <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void run("Approved", () => api.decideDeskCase(record.id, "approve", comments))}>
                    Approve
                  </button>
                  <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void run("Returned", () => api.decideDeskCase(record.id, "return", comments))}>
                    Return
                  </button>
                </div>
              </>
            ) : null}
          </div>
        ) : null}

        {step === 2 && record ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <ReadRow label="Commodity purchased" value={initiate.commodity || "Airtime"} />
            <ReadRow label="Commodity quantity" value={initiate.commodity_quantity || orig.approved_facility_amount} />
            <ReadRow label="Purchase timestamp" value={initiate.purchase_timestamp || stamps.purchase} />
            <ReadRow label="Commodity seller" value={initiate.commodity_seller || "Safaricom"} />
            <ReadRow label="Commodity buyer" value={initiate.commodity_buyer || institutionName} />
            <ReadRow label="Commodity agent" value={initiate.commodity_agent || "Buruuj Fintech"} />
            <ReadRow label="Payment reference" value={initiate.payment_reference} />
            {initiateLocked ? (
              <ReadRow label="Purchase complete" value={initiate.purchase_complete || "Yes"} />
            ) : (
              <Field label="Purchase complete">
                <select className={fieldClass} value={form.purchase_complete} onChange={(e) => setForm({ ...form, purchase_complete: e.target.value })}>
                  <option>Yes</option>
                  <option>No</option>
                </select>
              </Field>
            )}
            {canWrite && record.current_step === 3 ? (
              <div className="sm:col-span-2">
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={busy}
                  onClick={() => void run("Tawarruq initiated", () => api.completeDeskStep(record.id, 3, { purchase_complete: form.purchase_complete }))}
                >
                  Confirm purchase
                </button>
              </div>
            ) : null}
          </div>
        ) : null}

        {step === 3 && record ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <ReadRow label="Buyer" value={orig.customer_name} />
            <ReadRow label="Buyer email" value={orig.customer_email} />
            <ReadRow label="Buyer phone" value={orig.customer_phone} />
            <ReadRow label="Seller" value={institutionName} />
            {murabahaLocked ? (
              <>
                <ReadRow label="Facility account" value={murabaha.facility_account} />
                <ReadRow label="Repayment installments" value={murabaha.repayment_installments} />
                <ReadRow label="First installment due date" value={murabaha.first_installment_due_date} />
                <ReadRow label="Last installment due date" value={murabaha.last_installment_due_date} />
              </>
            ) : (
              <>
                <Field label="Facility account">
                  <input className={fieldClass} value={form.facility_account} onChange={(e) => setForm({ ...form, facility_account: e.target.value })} />
                </Field>
                <Field label="Repayment installments">
                  <input
                    className={fieldClass}
                    type="number"
                    min="1"
                    step="1"
                    value={form.repayment_installments}
                    onChange={(e) => setForm({ ...form, repayment_installments: e.target.value })}
                  />
                </Field>
                <Field label="First installment due date">
                  <input
                    className={fieldClass}
                    type="date"
                    value={form.first_installment_due_date}
                    onChange={(e) => setForm({ ...form, first_installment_due_date: e.target.value })}
                  />
                </Field>
                <Field label="Last installment due date">
                  <input
                    className={fieldClass}
                    type="date"
                    value={form.last_installment_due_date}
                    onChange={(e) => setForm({ ...form, last_installment_due_date: e.target.value })}
                  />
                </Field>
              </>
            )}
            <ReadRow label="Cost price" value={initiate.commodity_quantity || orig.approved_facility_amount} />
            <Field label="Profit">
              <input className={fieldClass} value={form.profit} disabled={murabahaLocked} onChange={(e) => setForm({ ...form, profit: e.target.value })} />
            </Field>
            <ReadRow label="Deferred sale price" value={murabaha.deferred_sale_price || deferred} />
            <Field label="Customer offer reference">
              <input className={fieldClass} value={form.offer_reference} disabled={murabahaLocked} onChange={(e) => setForm({ ...form, offer_reference: e.target.value })} />
            </Field>
            <Field label="Contract reference">
              <input className={fieldClass} value={form.contract_reference} disabled={murabahaLocked} onChange={(e) => setForm({ ...form, contract_reference: e.target.value })} />
            </Field>
            <ReadRow label="Sale status" value={murabaha.sale_status || "Pending"} />
            <ReadRow label="Sale timestamp" value={murabaha.sale_timestamp} />
            {canWrite && record.current_step === 4 ? (
              <div className="sm:col-span-2 flex flex-wrap items-end gap-2">
                <Field label="Customer OTP">
                  <input className={fieldClass} value={otpCode} onChange={(e) => setOtpCode(e.target.value)} />
                </Field>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={busy}
                  onClick={() =>
                    void run("OTP sent", async () => {
                      const sent = await api.sendDeskOtp(record.id, "murabaha");
                      setDevCode(sent.dev_code || "");
                    })
                  }
                >
                  Send OTP
                </button>
                <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void run("OTP accepted", () => api.verifyDeskOtp(record.id, "murabaha", otpCode))}>
                  Verify OTP
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={busy}
                  onClick={() =>
                    void run("Murabaha recorded", () =>
                      api.completeDeskStep(record.id, 4, {
                        profit: form.profit,
                        offer_reference: form.offer_reference,
                        contract_reference: form.contract_reference,
                        facility_account: form.facility_account,
                        repayment_installments: form.repayment_installments,
                        first_installment_due_date: form.first_installment_due_date,
                        last_installment_due_date: form.last_installment_due_date,
                        seller_name: institutionName,
                      }),
                    )
                  }
                >
                  Complete Murabaha
                </button>
              </div>
            ) : null}
          </div>
        ) : null}

        {step === 4 && record ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <ReadRow label="Current commodity owner" value={resale.current_owner_name || orig.customer_name} />
            <ReadRow label="Current commodity owner email" value={resale.current_owner_email || orig.customer_email} />
            <ReadRow label="Current commodity owner phone" value={resale.current_owner_phone || orig.customer_phone} />
            <ReadRow label="Owner id" value={resale.current_owner_id || orig.customer_id} />
            <ReadRow label="Agent" value={resale.agent_name || "Soqo Capital"} />
            <ReadRow label="Appointment status" value={resale.agent_appointment_status} />
            <ReadRow label="Appointment timestamp" value={resale.agent_appointment_timestamp} />
            <ReadRow label="Resale start" value={resale.resale_start_timestamp} />
            <ReadRow label="Resale end" value={resale.resale_end_timestamp} />
            <ReadRow label="Confirmation" value={resale.resale_confirmation_status || "—"} />
            {canWrite && record.current_step === 5 ? (
              <div className="sm:col-span-2 flex flex-wrap items-end gap-2">
                <Field label="Customer OTP">
                  <input className={fieldClass} value={otpCode} onChange={(e) => setOtpCode(e.target.value)} />
                </Field>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={busy}
                  onClick={() =>
                    void run("OTP sent", async () => {
                      const sent = await api.sendDeskOtp(record.id, "agent");
                      setDevCode(sent.dev_code || "");
                    })
                  }
                >
                  Send OTP
                </button>
                <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void run("Agent appointed", () => api.verifyDeskOtp(record.id, "agent", otpCode))}>
                  Verify OTP
                </button>
                <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void run("Resale recorded", () => api.completeDeskStep(record.id, 5, {}))}>
                  Complete resale
                </button>
              </div>
            ) : null}
          </div>
        ) : null}

        {step === 5 && record ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <ReadRow label="Commodity" value={proceeds.commodity || "Airtime"} />
            <ReadRow label="Quantity" value={proceeds.commodity_quantity || orig.approved_facility_amount} />
            <ReadRow label="Resale cost" value={proceeds.resale_cost || orig.approved_facility_amount} />
            <ReadRow label="Proceeds owner" value={proceeds.owner_name || orig.customer_name} />
            <ReadRow label="Id / email / phone" value={`${orig.customer_id} / ${orig.customer_email} / ${orig.customer_phone}`} />
            <ReadRow label="Deposit ref" value={proceeds.deposit_txn_ref} />
            <ReadRow label="Final status" value={proceeds.final_status} />
            {canWrite && record.current_step === 6 ? (
              <>
                <Field label="Customer CASA account">
                  <input
                    className={fieldClass}
                    value={form.customer_account_number}
                    onChange={(e) => setForm({ ...form, customer_account_number: e.target.value })}
                    required
                  />
                </Field>
                <Field label="Branch">
                  <input className={fieldClass} value={form.customer_branch} onChange={(e) => setForm({ ...form, customer_branch: e.target.value })} required />
                </Field>
                <div className="sm:col-span-2 flex flex-wrap items-end gap-2">
                  <Field label="Customer OTP">
                    <input className={fieldClass} value={otpCode} onChange={(e) => setOtpCode(e.target.value)} />
                  </Field>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={busy}
                    onClick={() =>
                      void run("OTP sent", async () => {
                        const sent = await api.sendDeskOtp(record.id, "casa");
                        setDevCode(sent.dev_code || "");
                      })
                    }
                  >
                    Send OTP
                  </button>
                  <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void run("CASA approved", () => api.verifyDeskOtp(record.id, "casa", otpCode))}>
                    Verify OTP
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={busy}
                    onClick={() =>
                      void run("Proceeds recorded", () =>
                        api.completeDeskStep(record.id, 6, {
                          customer_account_number: form.customer_account_number,
                          customer_branch: form.customer_branch,
                        }),
                      )
                    }
                  >
                    Complete proceeds
                  </button>
                </div>
              </>
            ) : (
              <>
                <ReadRow label="Customer CASA account" value={proceeds.customer_account_number} />
                <ReadRow label="Branch" value={proceeds.customer_branch} />
              </>
            )}
          </div>
        ) : null}

        {step === 6 && record ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Settlement reference">
              <input className={fieldClass} value={form.settlement_ref} onChange={(e) => setForm({ ...form, settlement_ref: e.target.value })} />
            </Field>
            <ReadRow label="Settlement timestamp" value={clearing.settlement_timestamp || stamps.clearing} />
            {canWrite && record.current_step === 7 ? (
              <div className="sm:col-span-2">
                <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void run("Cleared", () => api.completeDeskStep(record.id, 7, { settlement_ref: form.settlement_ref }))}>
                  Complete clearing
                </button>
              </div>
            ) : null}
          </div>
        ) : null}

        {step === 7 && record ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <ReadRow label="Final status" value={record.status} />
            {Object.entries(stamps).map(([key, value]) => (
              <ReadRow key={key} label={key.replace(/_/g, " ")} value={value} />
            ))}
            {canWrite && record.current_step === 8 && record.status !== "complete" ? (
              <div className="sm:col-span-2">
                <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void run("Case complete", () => api.completeDeskStep(record.id, 8, {}))}>
                  Mark complete
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>
    </PageShell>
  );
}
