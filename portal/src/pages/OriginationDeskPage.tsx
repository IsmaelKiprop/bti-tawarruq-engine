import { useEffect, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type DeskApprover, type DeskCase } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import { deskPayload, deskStatusLabel } from "../config/fiDesk";

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

function journeyFrom(record: DeskCase | null): { ref: string; url: string; accepted: boolean } | null {
  const raw = record?.payload?.journey;
  if (!raw || typeof raw !== "object") return null;
  const ref = String((raw as { customer_ref?: string }).customer_ref || "").trim();
  if (!ref) return null;
  return {
    ref,
    url: `${window.location.origin}/customer/${encodeURIComponent(ref)}`,
    accepted: Boolean((raw as { offer_accepted?: boolean }).offer_accepted),
  };
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
  const waitingForCustomer = Boolean(record && record.status !== "complete" && record.status !== "returned" && record.status !== "pending_approval");

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

  function statusCopy() {
    if (!record) return "";
    if (record.status === "pending_approval") return "Waiting for FI Approver.";
    if (record.status === "returned") return "Returned. Edit and send again.";
    if (record.status === "complete") return "Customer accepted. Trade steps finished behind the scenes.";
    if (journey?.accepted) return "Customer accepted. Completing the trade automatically.";
    return "Customer emailed. Trade steps run automatically after they accept.";
  }

  return (
    <PageShell wide>
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="m-0 text-lg font-semibold">Origination</h2>
          <p className="muted m-0 mt-1 text-sm">
            {isApprover ? "Approve assigned facility requests." : "Name, email, phone, amount, profit, then FI Approver. The rest runs after the customer accepts."}
          </p>
        </div>
        {canWrite ? (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setRecord(null);
              setSelectedId("");
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
          <ReadRow label="Commodity type" value="Airtime" />
          <Field label="Profit">
            <input className={fieldClass} value={form.profit} disabled={originationLocked} onChange={(e) => setForm({ ...form, profit: e.target.value })} />
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
          {journey ? (
            <>
              <div className="rounded-sm border border-border bg-surface-elevated px-3 py-2">
                <dt className="text-[0.7rem] uppercase tracking-wide text-muted">Customer journey</dt>
                <dd className="m-0 text-sm">
                  <a className="text-primary" href={journey.url} target="_blank" rel="noreferrer">
                    {journey.url}
                  </a>
                </dd>
              </div>
              <ReadRow label="Customer accept" value={journey.accepted ? "Accepted" : "Waiting"} />
            </>
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
                      facility_product_type: "Airtime",
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
    </PageShell>
  );
}
