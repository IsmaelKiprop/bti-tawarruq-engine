import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type InstitutionOnboarding } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, LoadingPanel, PageShell } from "../components/PageShell";
import {
  AGREEMENT_STATUSES,
  ID_TYPES,
  INSTITUTION_TYPES,
  LICENCE_STATUSES,
  REGULATORS,
  SCREEN_STATUSES,
  SETTLEMENT_VERIFY,
  VERIFY_STATUSES,
  WIZARD_STEPS,
  emptyFiKyc,
  formFromOnboarding,
  payloadFromForm,
  type FiKycForm,
  type KycPerson,
} from "../config/fiKyc";

const fieldClass =
  "rounded-sm border border-border bg-surface-elevated px-2.5 py-1.5 text-sm text-foreground";
const labelClass = "flex min-w-0 flex-col gap-1 text-xs uppercase tracking-wide text-muted";

function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className={labelClass}>
      {label}
      {children}
    </label>
  );
}

function PeopleEditor({
  rows,
  onChange,
  nameLabel,
}: {
  rows: KycPerson[];
  onChange: (rows: KycPerson[]) => void;
  nameLabel: string;
}) {
  return (
    <div className="grid gap-2">
      {rows.map((row, index) => (
        <div key={`${nameLabel}-${index}`} className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
          <input
            className={fieldClass}
            placeholder={nameLabel}
            value={row.name}
            onChange={(e) => {
              const next = [...rows];
              next[index] = { ...row, name: e.target.value };
              onChange(next);
            }}
          />
          <input
            className={fieldClass}
            placeholder="Title"
            value={row.title || ""}
            onChange={(e) => {
              const next = [...rows];
              next[index] = { ...row, title: e.target.value };
              onChange(next);
            }}
          />
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => onChange(rows.filter((_, i) => i !== index))}
            disabled={rows.length === 1}
          >
            Remove
          </button>
        </div>
      ))}
      <button type="button" className="btn btn-secondary btn-sm w-fit" onClick={() => onChange([...rows, { name: "", title: "" }])}>
        Add
      </button>
    </div>
  );
}

export function InstitutionOnboardPage() {
  const { institutionId } = useParams();
  const { user } = useAuth();
  const isSuperAdmin = user?.role === "platform_admin";
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FiKycForm>(emptyFiKyc);
  const [record, setRecord] = useState<InstitutionOnboarding | null>(null);
  const [loading, setLoading] = useState(Boolean(institutionId));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const set = (patch: Partial<FiKycForm>) => setForm((prev) => ({ ...prev, ...patch }));

  useEffect(() => {
    if (!institutionId) return;
    let alive = true;
    api
      .getInstitutionOnboarding(institutionId)
      .then((data) => {
        if (!alive) return;
        setRecord(data);
        setForm(formFromOnboarding(data as unknown as Record<string, unknown>));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load onboarding"))
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [institutionId]);

  async function persist(): Promise<InstitutionOnboarding> {
    const body = payloadFromForm(form);
    if (record?.id) {
      const saved = await api.saveInstitutionOnboarding(record.id, body);
      setRecord(saved);
      return saved;
    }
    const created = await api.startInstitutionOnboarding(body);
    setRecord(created);
    return created;
  }

  async function onNext() {
    setBusy(true);
    setError("");
    try {
      await persist();
      setStep((n) => Math.min(n + 1, WIZARD_STEPS.length - 1));
      setMessage("Draft saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save draft");
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const saved = await persist();
      const done = await api.submitInstitutionOnboarding(saved.id);
      setRecord(done);
      setForm(formFromOnboarding(done as unknown as Record<string, unknown>));
      setMessage(
        isSuperAdmin
          ? `${done.name} is active. You can invite its FI Admin from Users.`
          : `${done.name} is waiting for Super Admin approval.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setBusy(false);
    }
  }

  async function onDecide(decision: "approve" | "return") {
    if (!record?.id) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const done = await api.decideInstitutionOnboarding(record.id, { decision });
      setRecord(done);
      setForm(formFromOnboarding(done as unknown as Record<string, unknown>));
      setMessage(
        decision === "approve"
          ? `${done.name} is active. You can invite its FI Admin from Users.`
          : `${done.name} was returned to draft.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Decision failed");
    } finally {
      setBusy(false);
    }
  }

  const stepId = WIZARD_STEPS[step].id;
  const submitLabel = isSuperAdmin ? "Activate institution" : "Submit for Super Admin approval";

  const reviewRows = useMemo(
    () => [
      ["Legal name", form.legal_registered_name],
      ["Type", form.institution_type],
      ["Regulator", form.primary_regulator],
      ["Licence", form.licence_number],
      ["Primary contact", form.primary_contact_full_name],
      ["Settlement bank", form.settlement_bank_name],
      ["Go-live", form.target_go_live_date],
    ],
    [form],
  );

  return (
    <PageShell wide>
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="m-0 text-lg font-semibold">Onboard financial institution</h2>
          <p className="muted m-0 mt-1 text-sm">
            BTI customer KYC. Each category is one page. Drafts can be incomplete.
          </p>
        </div>
        <Link className="btn btn-secondary btn-sm" to="/institutions">
          Directory
        </Link>
      </header>

      <ol className="m-0 flex list-none flex-wrap gap-1.5 p-0">
        {WIZARD_STEPS.map((item, index) => (
          <li key={item.id}>
            <button
              type="button"
              className={`rounded-sm border px-2 py-1 text-xs ${
                index === step ? "border-foreground bg-surface-elevated text-foreground" : "border-border text-muted"
              }`}
              onClick={() => setStep(index)}
            >
              {index + 1}. {item.title}
            </button>
          </li>
        ))}
      </ol>

      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}
      {loading ? <LoadingPanel rows={6} /> : null}

      {!loading ? (
        <section className="rounded-sm border border-border bg-surface p-3">
          {stepId === "identity" ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Legal registered name">
                <input className={fieldClass} value={form.legal_registered_name} onChange={(e) => set({ legal_registered_name: e.target.value })} />
              </Field>
              <Field label="Institution code">
                <input className={fieldClass} value={form.code} onChange={(e) => set({ code: e.target.value.toUpperCase() })} placeholder="Auto from name if blank" />
              </Field>
              <Field label="Trading name">
                <input className={fieldClass} value={form.trading_name} onChange={(e) => set({ trading_name: e.target.value })} />
              </Field>
              <Field label="Institution type">
                <select className={fieldClass} value={form.institution_type} onChange={(e) => set({ institution_type: e.target.value })}>
                  {INSTITUTION_TYPES.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </Field>
              {form.institution_type === "OTHER" ? (
                <Field label="Other type">
                  <input className={fieldClass} value={form.other_institution_type} onChange={(e) => set({ other_institution_type: e.target.value })} />
                </Field>
              ) : null}
              <Field label="Registration number">
                <input className={fieldClass} value={form.registration_number} onChange={(e) => set({ registration_number: e.target.value })} />
              </Field>
              <Field label="Incorporation date">
                <input className={fieldClass} type="date" value={form.incorporation_date} onChange={(e) => set({ incorporation_date: e.target.value })} />
              </Field>
              <Field label="Incorporation country">
                <input className={fieldClass} value={form.incorporation_country} maxLength={2} onChange={(e) => set({ incorporation_country: e.target.value.toUpperCase() })} />
              </Field>
              <Field label="KRA PIN">
                <input className={fieldClass} value={form.kra_pin} onChange={(e) => set({ kra_pin: e.target.value.toUpperCase() })} />
              </Field>
              <Field label="Registered address">
                <input className={fieldClass} value={form.registered_address_line1} onChange={(e) => set({ registered_address_line1: e.target.value })} />
              </Field>
              <Field label="Address line 2">
                <input className={fieldClass} value={form.registered_address_line2} onChange={(e) => set({ registered_address_line2: e.target.value })} />
              </Field>
              <Field label="County">
                <input className={fieldClass} value={form.registered_county} onChange={(e) => set({ registered_county: e.target.value })} />
              </Field>
              <Field label="Postal code">
                <input className={fieldClass} value={form.registered_postal_code} onChange={(e) => set({ registered_postal_code: e.target.value })} />
              </Field>
              <Field label="Physical address">
                <input className={fieldClass} value={form.physical_address} onChange={(e) => set({ physical_address: e.target.value })} />
              </Field>
              <Field label="Website">
                <input className={fieldClass} value={form.website_url} onChange={(e) => set({ website_url: e.target.value })} />
              </Field>
              <Field label="Support email">
                <input className={fieldClass} type="email" value={form.support_email} onChange={(e) => set({ support_email: e.target.value })} />
              </Field>
              <Field label="Main telephone">
                <input className={fieldClass} value={form.main_telephone} onChange={(e) => set({ main_telephone: e.target.value })} />
              </Field>
              <label className={`${labelClass} sm:col-span-2`}>
                Business description
                <textarea className={fieldClass} rows={3} value={form.business_description} onChange={(e) => set({ business_description: e.target.value })} />
              </label>
            </div>
          ) : null}

          {stepId === "regulatory" ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Primary regulator">
                <select className={fieldClass} value={form.primary_regulator} onChange={(e) => set({ primary_regulator: e.target.value })}>
                  {REGULATORS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </Field>
              {form.primary_regulator === "OTHER" ? (
                <Field label="Regulator name">
                  <input className={fieldClass} value={form.regulator_other_name} onChange={(e) => set({ regulator_other_name: e.target.value })} />
                </Field>
              ) : null}
              <Field label="Licence number">
                <input className={fieldClass} value={form.licence_number} onChange={(e) => set({ licence_number: e.target.value })} />
              </Field>
              <Field label="Licence issue date">
                <input className={fieldClass} type="date" value={form.licence_issue_date} onChange={(e) => set({ licence_issue_date: e.target.value })} />
              </Field>
              <Field label="Licence expiry date">
                <input className={fieldClass} type="date" value={form.licence_expiry_date} onChange={(e) => set({ licence_expiry_date: e.target.value })} />
              </Field>
              <Field label="Licence status">
                <select className={fieldClass} value={form.licence_status} onChange={(e) => set({ licence_status: e.target.value })}>
                  {LICENCE_STATUSES.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Regulator register URL">
                <input className={fieldClass} value={form.regulator_register_url} onChange={(e) => set({ regulator_register_url: e.target.value })} />
              </Field>
            </div>
          ) : null}

          {stepId === "ownership" ? (
            <div className="grid gap-4">
              <Field label="Ownership summary">
                <textarea className={fieldClass} rows={3} value={form.ownership_structure_summary} onChange={(e) => set({ ownership_structure_summary: e.target.value })} />
              </Field>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Parent company">
                  <input className={fieldClass} value={form.parent_company_name} onChange={(e) => set({ parent_company_name: e.target.value })} />
                </Field>
                <Field label="Related entities">
                  <input className={fieldClass} value={form.related_entities} onChange={(e) => set({ related_entities: e.target.value })} placeholder="Comma separated" />
                </Field>
                <Field label="Ownership percentage">
                  <input className={fieldClass} value={form.ownership_percentage} onChange={(e) => set({ ownership_percentage: e.target.value })} />
                </Field>
                <Field label="CEO / managing director">
                  <input className={fieldClass} value={form.ceo_managing_director_name} onChange={(e) => set({ ceo_managing_director_name: e.target.value })} />
                </Field>
              </div>
              <div>
                <p className="m-0 mb-2 text-xs uppercase tracking-wide text-muted">Shareholders</p>
                <PeopleEditor rows={form.owners_and_shareholders} onChange={(rows) => set({ owners_and_shareholders: rows })} nameLabel="Shareholder" />
              </div>
              <div>
                <p className="m-0 mb-2 text-xs uppercase tracking-wide text-muted">Ultimate beneficial owners</p>
                <PeopleEditor rows={form.ubo_details} onChange={(rows) => set({ ubo_details: rows })} nameLabel="UBO" />
              </div>
              <div>
                <p className="m-0 mb-2 text-xs uppercase tracking-wide text-muted">Board</p>
                <PeopleEditor rows={form.directors_board_members} onChange={(rows) => set({ directors_board_members: rows })} nameLabel="Director" />
              </div>
              <div>
                <p className="m-0 mb-2 text-xs uppercase tracking-wide text-muted">Senior management</p>
                <PeopleEditor rows={form.senior_management_details} onChange={(rows) => set({ senior_management_details: rows })} nameLabel="Officer" />
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                {(["pep_screening_status", "sanctions_screening_status", "adverse_media_screening_status"] as const).map((key) => (
                  <Field key={key} label={key.replace(/_/g, " ")}>
                    <select className={fieldClass} value={form[key]} onChange={(e) => set({ [key]: e.target.value })}>
                      {SCREEN_STATUSES.map((opt) => (
                        <option key={opt} value={opt}>
                          {opt.replace(/_/g, " ")}
                        </option>
                      ))}
                    </select>
                  </Field>
                ))}
              </div>
            </div>
          ) : null}

          {stepId === "representatives" ? (
            <div className="grid gap-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Primary contact name">
                  <input className={fieldClass} value={form.primary_contact_full_name} onChange={(e) => set({ primary_contact_full_name: e.target.value })} />
                </Field>
                <Field label="Title">
                  <input className={fieldClass} value={form.primary_contact_title} onChange={(e) => set({ primary_contact_title: e.target.value })} />
                </Field>
                <Field label="Work email">
                  <input className={fieldClass} type="email" value={form.primary_contact_work_email} onChange={(e) => set({ primary_contact_work_email: e.target.value })} />
                </Field>
                <Field label="Phone">
                  <input className={fieldClass} value={form.primary_contact_phone} onChange={(e) => set({ primary_contact_phone: e.target.value })} />
                </Field>
                <Field label="Compliance officer">
                  <input className={fieldClass} value={form.compliance_officer_name} onChange={(e) => set({ compliance_officer_name: e.target.value })} />
                </Field>
                <Field label="Compliance email">
                  <input className={fieldClass} type="email" value={form.compliance_officer_email} onChange={(e) => set({ compliance_officer_email: e.target.value })} />
                </Field>
                <Field label="ID type">
                  <select className={fieldClass} value={form.representative_id_type} onChange={(e) => set({ representative_id_type: e.target.value })}>
                    {ID_TYPES.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="ID number">
                  <input className={fieldClass} value={form.representative_id_number} onChange={(e) => set({ representative_id_number: e.target.value })} />
                </Field>
                <Field label="Identity verification">
                  <select className={fieldClass} value={form.representative_identity_verification_status} onChange={(e) => set({ representative_identity_verification_status: e.target.value })}>
                    {VERIFY_STATUSES.map((opt) => (
                      <option key={opt} value={opt}>
                        {opt.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Authority to act (document reference)">
                  <input className={fieldClass} value={form.authority_to_act_document_id} onChange={(e) => set({ authority_to_act_document_id: e.target.value })} />
                </Field>
              </div>
              <div>
                <p className="m-0 mb-2 text-xs uppercase tracking-wide text-muted">Authorized signatories</p>
                <PeopleEditor rows={form.authorized_signatories} onChange={(rows) => set({ authorized_signatories: rows })} nameLabel="Signatory" />
              </div>
            </div>
          ) : null}

          {stepId === "settlement" ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Settlement bank">
                <input className={fieldClass} value={form.settlement_bank_name} onChange={(e) => set({ settlement_bank_name: e.target.value })} />
              </Field>
              <Field label="Account name">
                <input className={fieldClass} value={form.settlement_account_name} onChange={(e) => set({ settlement_account_name: e.target.value })} />
              </Field>
              <Field label="Branch">
                <input className={fieldClass} value={form.settlement_branch} onChange={(e) => set({ settlement_branch: e.target.value })} />
              </Field>
              <Field label="Account number">
                <input className={fieldClass} value={form.settlement_account_number} onChange={(e) => set({ settlement_account_number: e.target.value })} />
              </Field>
              <Field label="Currency">
                <input className={fieldClass} value={form.settlement_currency} maxLength={3} onChange={(e) => set({ settlement_currency: e.target.value.toUpperCase() })} />
              </Field>
              <Field label="Verification status">
                <select className={fieldClass} value={form.settlement_account_verification_status} onChange={(e) => set({ settlement_account_verification_status: e.target.value })}>
                  {SETTLEMENT_VERIFY.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Evidence document reference">
                <input className={fieldClass} value={form.settlement_account_evidence_document_id} onChange={(e) => set({ settlement_account_evidence_document_id: e.target.value })} />
              </Field>
            </div>
          ) : null}

          {stepId === "commercial" ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Expected monthly count">
                <input className={fieldClass} value={form.expected_monthly_transaction_count} onChange={(e) => set({ expected_monthly_transaction_count: e.target.value })} />
              </Field>
              <Field label="Expected monthly value">
                <input className={fieldClass} value={form.expected_monthly_transaction_value} onChange={(e) => set({ expected_monthly_transaction_value: e.target.value })} />
              </Field>
              <Field label="Typical transaction amount">
                <input className={fieldClass} value={form.typical_transaction_amount} onChange={(e) => set({ typical_transaction_amount: e.target.value })} />
              </Field>
              <Field label="Maximum transaction amount">
                <input className={fieldClass} value={form.maximum_transaction_amount} onChange={(e) => set({ maximum_transaction_amount: e.target.value })} />
              </Field>
              <Field label="Target go-live">
                <input className={fieldClass} type="date" value={form.target_go_live_date} onChange={(e) => set({ target_go_live_date: e.target.value })} />
              </Field>
              <Field label="Commercial agreement">
                <select className={fieldClass} value={form.commercial_agreement_status} onChange={(e) => set({ commercial_agreement_status: e.target.value })}>
                  {AGREEMENT_STATUSES.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Pricing schedule reference">
                <input className={fieldClass} value={form.pricing_schedule_reference} onChange={(e) => set({ pricing_schedule_reference: e.target.value })} />
              </Field>
              <Field label="Dispute contact email">
                <input className={fieldClass} type="email" value={form.dispute_contact_email} onChange={(e) => set({ dispute_contact_email: e.target.value })} />
              </Field>
            </div>
          ) : null}

          {stepId === "review" ? (
            <div className="grid gap-3">
              <dl className="m-0 grid gap-2 sm:grid-cols-2">
                {reviewRows.map(([label, value]) => (
                  <div key={label} className="rounded-sm border border-border bg-surface-elevated px-3 py-2">
                    <dt className="text-[0.7rem] uppercase tracking-wide text-muted">{label}</dt>
                    <dd className="m-0 text-sm">{value || "-"}</dd>
                  </div>
                ))}
              </dl>
              <p className="m-0 text-sm text-muted">
                {isSuperAdmin
                  ? "Super Admin activate is immediate. No maker-checker on this onboarding."
                  : "BTI Ops submit waits for Super Admin approval before the institution can be staffed."}
              </p>
              {isSuperAdmin && record?.lifecycle_status === "pending_approval" ? (
                <div className="flex flex-wrap gap-2">
                  <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void onDecide("approve")}>
                    Approve and activate
                  </button>
                  <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void onDecide("return")}>
                    Return to draft
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" className="btn btn-secondary" disabled={step === 0 || busy} onClick={() => setStep((n) => n - 1)}>
              Back
            </button>
            {step < WIZARD_STEPS.length - 1 ? (
              <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void onNext()}>
                {busy ? "Saving…" : "Save and continue"}
              </button>
            ) : record?.lifecycle_status === "pending_approval" && isSuperAdmin ? (
              <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void onDecide("approve")}>
                {busy ? "Approving…" : "Approve and activate"}
              </button>
            ) : record?.lifecycle_status === "active" ? (
              <Link className="btn btn-secondary" to="/users">
                Invite FI Admin
              </Link>
            ) : (
              <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void onSubmit()}>
                {busy ? "Submitting…" : submitLabel}
              </button>
            )}
          </div>
        </section>
      ) : null}
    </PageShell>
  );
}
