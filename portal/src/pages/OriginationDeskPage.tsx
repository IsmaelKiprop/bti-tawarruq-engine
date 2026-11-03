import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type DeskApprover, type DeskCase } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import { deskPayload, deskStatusLabel } from "../config/fiDesk";

const fieldClass = "rounded-sm border border-border bg-surface-elevated px-2.5 py-1.5 text-sm text-foreground";
const labelClass = "flex min-w-0 flex-col gap-1 text-xs uppercase tracking-wide text-muted";

const COMMODITIES = ["Airtime", "Palm Oil", "Other"] as const;
const OFFER_MODES = [
  { value: "automated", label: "Automated (email customer)" },
  { value: "physical", label: "Physical (skip email accept)" },
  { value: "both", label: "Both" },
] as const;

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

type WorkflowRow = { at?: string; title?: string; detail?: string; certificates?: string[] };

const HIDDEN_WORKFLOW = /offer letter|agency|resale agent|resale proceeds|clearing/i;

const CERT_LABELS: Record<string, string> = {
  sedania_to_fi: "Sedania→FI",
  fi_to_customer: "FI→Customer",
  customer_to_sedania: "Customer→Sedania",
  purchase: "Sedania→FI",
  murabahah: "FI→Customer",
  murabaha: "FI→Customer",
  complete: "Customer→Sedania",
};

const ALL_CERT_KINDS = ["sedania_to_fi", "fi_to_customer", "customer_to_sedania"] as const;

function certLabel(kind: string) {
  return CERT_LABELS[kind] || kind;
}

function workflowFrom(record: DeskCase | null): WorkflowRow[] {
  const raw = record?.payload?.workflow;
  if (!Array.isArray(raw)) return [];
  return (raw.filter((row) => row && typeof row === "object") as WorkflowRow[]).filter((row) => {
    const title = String(row.title || "");
    return !HIDDEN_WORKFLOW.test(title);
  });
}

function journeyFrom(
  record: DeskCase | null,
): { ref: string; url: string; accepted: boolean; method: string } | null {
  const raw = record?.payload?.journey;
  if (!raw || typeof raw !== "object") return null;
  const ref = String((raw as { customer_ref?: string }).customer_ref || "").trim();
  if (!ref) return null;
  const method = String((raw as { acceptance_method?: string }).acceptance_method || "").trim();
  return {
    ref,
    url: `${window.location.origin}/customer/${encodeURIComponent(ref)}`,
    accepted: Boolean((raw as { offer_accepted?: boolean }).offer_accepted),
    method,
  };
}

function workflowHasCerts(rows: WorkflowRow[]) {
  return rows.some((row) => (row.certificates?.length || 0) > 0);
}

export function OriginationDeskPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const caseFromUrl = searchParams.get("case") || "";
  const isApprover = user?.role === "fi_approver";
  const canWrite = Boolean(user?.permissions.includes("write_ops"));
  const [cases, setCases] = useState<DeskCase[]>([]);
  const [approvers, setApprovers] = useState<DeskApprover[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [record, setRecord] = useState<DeskCase | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [comments, setComments] = useState("");
  const [form, setForm] = useState({
    customer_name: "",
    customer_email: "",
    customer_phone: "",
    approved_facility_amount: "",
    assigned_approver_id: "",
    profit: "",
    facility_product_type: "Airtime",
    term_months: "12",
    offer_letter_mode: "automated",
  });

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
    const orig = deskPayload(next, "origination");
    setForm((current) => ({
      ...current,
      customer_name: orig.customer_name || current.customer_name,
      customer_email: orig.customer_email || current.customer_email,
      customer_phone: orig.customer_phone || current.customer_phone,
      approved_facility_amount: orig.approved_facility_amount || current.approved_facility_amount,
      profit: orig.profit || current.profit,
      facility_product_type: orig.facility_product_type || current.facility_product_type || "Airtime",
      term_months: orig.term_months || current.term_months || "12",
      offer_letter_mode: orig.offer_letter_mode || current.offer_letter_mode || "automated",
      assigned_approver_id: next.assigned_approver_id || current.assigned_approver_id,
    }));
    setComments(next.approval_comments || "");
  }

  useEffect(() => {
    setLoading(true);
    loadList()
      .then(() => (caseFromUrl ? openCase(caseFromUrl) : undefined))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load origination desk"))
      .finally(() => setLoading(false));
  }, [user?.institution_id, caseFromUrl]);

  const journey = journeyFrom(record);
  const workflow = useMemo(() => workflowFrom(record), [record]);
  const waitingForCustomer = Boolean(
    record && record.status !== "complete" && record.status !== "returned" && record.status !== "pending_approval" && !journey?.accepted,
  );

  useEffect(() => {
    if (!selectedId || !waitingForCustomer) return;
    const timer = window.setInterval(() => {
      void api.getDeskCase(selectedId).then(setRecord).catch(() => undefined);
    }, 8000);
    return () => window.clearInterval(timer);
  }, [selectedId, waitingForCustomer]);

  async function run(label: string, work: () => Promise<DeskCase | void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const next = await work();
      if (next) {
        setRecord(next);
        setSelectedId(next.id);
      }
      await loadList();
      setMessage(label);
    } catch (err) {
      setError(err instanceof Error ? err.message : label);
    } finally {
      setBusy(false);
    }
  }

  const originationLocked = record != null && record.status !== "returned";
  const showWizard = Boolean(record && record.status !== "pending_approval" && workflow.length);

  function statusCopy() {
    if (!record) return "";
    if (record.status === "pending_approval") return "Waiting for FI Approver.";
    if (record.status === "returned") return "Returned. Read the comments, edit, and send again.";
    if (record.status === "complete") return "Workflow complete. Download or resend certificates below.";
    if (journey?.accepted) return "Customer accepted. Completing Murabaha and commodity sale legs.";
    const mode = form.offer_letter_mode;
    if (mode === "physical") return "Physical mode — trade continues without email accept.";
    return "Customer emailed. Trade continues after they accept in the journey.";
  }

  return (
    <PageShell wide>
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="m-0 text-lg font-semibold">Origination</h2>
        </div>
        {canWrite ? (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setRecord(null);
              setSelectedId("");
              setComments("");
            }}
          >
            New case
          </button>
        ) : null}
      </header>

      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}
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
                {asRecord(item.payload.origination).customer_name || item.id.slice(0, 8)} · {item.status}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {!loading && !cases.length && isApprover ? (
        <EmptyState title="No assigned requests" description="FI Ops must submit an origination case to you first." />
      ) : null}

      <section className="rounded-sm border border-border bg-surface p-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Customer name">
            <input className={fieldClass} value={form.customer_name} disabled={originationLocked} onChange={(e) => setForm({ ...form, customer_name: e.target.value })} />
          </Field>
          <Field label="Customer email">
            <input className={fieldClass} type="email" value={form.customer_email} disabled={originationLocked} onChange={(e) => setForm({ ...form, customer_email: e.target.value })} />
          </Field>
          <Field label="Customer phone">
            <input className={fieldClass} type="tel" value={form.customer_phone} disabled={originationLocked} onChange={(e) => setForm({ ...form, customer_phone: e.target.value })} />
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
          <Field label="Commodity">
            <select
              className={fieldClass}
              value={form.facility_product_type}
              disabled={originationLocked}
              onChange={(e) => setForm({ ...form, facility_product_type: e.target.value })}
            >
              {COMMODITIES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Profit">
            <input className={fieldClass} value={form.profit} disabled={originationLocked} onChange={(e) => setForm({ ...form, profit: e.target.value })} />
          </Field>
          <Field label="Repayment period (months)">
            <input
              className={fieldClass}
              type="number"
              min="1"
              step="1"
              value={form.term_months}
              disabled={originationLocked}
              onChange={(e) => setForm({ ...form, term_months: e.target.value })}
            />
          </Field>
          {record && deskPayload(record, "origination").contract_price ? (
            <>
              <ReadRow label="Contract price" value={`KES ${deskPayload(record, "origination").contract_price}`} />
              <ReadRow
                label="Monthly installment"
                value={`KES ${deskPayload(record, "origination").monthly_installment || "—"}`}
              />
            </>
          ) : null}
          <Field label="Offer letter">
            <select
              className={fieldClass}
              value={form.offer_letter_mode}
              disabled={originationLocked}
              onChange={(e) => setForm({ ...form, offer_letter_mode: e.target.value })}
            >
              {OFFER_MODES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
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
          {record ? (
            <>
              <ReadRow label="Status" value={deskStatusLabel(record.status)} />
              <ReadRow label="Request id" value={record.id} />
            </>
          ) : null}
          {journey && form.offer_letter_mode !== "physical" ? (
            <div className="rounded-sm border border-border bg-surface-elevated px-3 py-2">
              <dt className="text-[0.7rem] uppercase tracking-wide text-muted">Customer journey</dt>
              <dd className="m-0 text-sm">
                <a className="text-primary" href={journey.url} target="_blank" rel="noreferrer">
                  {journey.url}
                </a>
              </dd>
            </div>
          ) : null}
          {record?.status === "returned" && (record.approval_comments || comments) ? (
            <div className="sm:col-span-2 rounded-sm border border-border bg-surface-elevated px-3 py-2">
              <dt className="text-[0.7rem] uppercase tracking-wide text-muted">Return comments</dt>
              <dd className="m-0 whitespace-pre-wrap text-sm">{record.approval_comments || comments}</dd>
            </div>
          ) : null}
          {record ? <p className="muted sm:col-span-2 m-0 text-sm">{statusCopy()}</p> : null}
          {record?.status === "pending_approval" && isApprover ? (
            <>
              <ReadRow label="Requester" value={record.requested_by_name} />
              <ReadRow label="Approver" value={record.assigned_approver_name} />
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
                      customer_name: form.customer_name,
                      customer_email: form.customer_email,
                      customer_phone: form.customer_phone,
                      approved_facility_amount: form.approved_facility_amount,
                      facility_product_type: form.facility_product_type,
                      term_months: form.term_months,
                      offer_letter_mode: form.offer_letter_mode,
                      assigned_approver_id: form.assigned_approver_id,
                      profit: form.profit,
                    }),
                  );
                }}
              >
                {busy ? "Sending…" : "Send to FI Approver"}
              </button>
            </div>
          ) : null}
        </div>
      </section>

      {showWizard ? (
        <section className="rounded-sm border border-border bg-surface p-3">
          <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <h3 className="m-0 text-base font-semibold">Workflow</h3>
            {record && workflowHasCerts(workflow) ? (
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={busy}
                  onClick={() =>
                    void run("Downloaded all certificates", async () => {
                      for (const kind of ALL_CERT_KINDS) {
                        await api.downloadDeskCertificate(record.id, kind);
                      }
                    })
                  }
                >
                  Download all certificates
                </button>
                {canWrite ? (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={busy}
                    onClick={() =>
                      void run("All certificates resent", async () => {
                        await api.resendDeskCertificates(record.id);
                        return api.getDeskCase(record.id);
                      })
                    }
                  >
                    Resend all certificates
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
          <ol className="m-0 flex list-none flex-col gap-0 p-0">
            {workflow.map((step, index) => (
              <li key={`${step.at}-${index}`} className="relative border-l border-border pl-4 pb-4 last:pb-0">
                <span className="absolute -left-1.5 top-1.5 h-3 w-3 rounded-full border border-border bg-surface-elevated" />
                <p className="m-0 text-[0.7rem] uppercase tracking-wide text-muted">
                  {step.at ? step.at.slice(0, 19).replace("T", " ") : "—"}
                </p>
                <p className="m-0 mt-1 text-sm font-medium">{step.title || `Step ${index + 1}`}</p>
                {step.detail ? <p className="muted m-0 mt-1 text-sm">{step.detail}</p> : null}
                {step.certificates?.length && record ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {step.certificates.map((kind) => (
                      <span key={kind} className="inline-flex flex-wrap gap-1">
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          disabled={busy}
                          onClick={() =>
                            void run(`Downloaded ${certLabel(kind)}`, async () => {
                              await api.downloadDeskCertificate(record.id, kind);
                            })
                          }
                        >
                          Download {certLabel(kind)}
                        </button>
                        {canWrite ? (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            disabled={busy}
                            onClick={() =>
                              void run(`Resent ${certLabel(kind)}`, async () => {
                                await api.resendDeskCertificates(record.id, kind);
                                return api.getDeskCase(record.id);
                              })
                            }
                          >
                            Resend {certLabel(kind)}
                          </button>
                        ) : null}
                      </span>
                    ))}
                  </div>
                ) : null}
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </PageShell>
  );
}
