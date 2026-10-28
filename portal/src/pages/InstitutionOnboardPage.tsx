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
  isStepComplete,
  maxReachableStep,
  payloadFromForm,
  stepErrors,
  wizardGated,
  type FiKycForm,
  type KycPerson,
} from "../config/fiKyc";

const fieldClass =
  "rounded-sm border border-border bg-surface-elevated px-2.5 py-1.5 text-sm text-foreground";
const labelClass = "flex min-w-0 flex-col gap-1 text-xs uppercase tracking-wide text-muted";

function Field({
  label,
  required,
  error,
  children,
}: {
  label: string;
  required?: boolean;
  error?: string;
  children: ReactNode;
}) {
  return (
    <label className={`${labelClass}${error ? " [&_input]:border-destructive [&_select]:border-destructive [&_textarea]:border-destructive" : ""}`}>
      <span>
        {label}
        {required ? <span className="text-destructive"> *</span> : null}
      </span>
      {children}
      {error ? <span className="normal-case tracking-normal text-destructive">{error}</span> : null}
    </label>
  );
}

function PeopleEditor({
  rows,
  onChange,
  nameLabel,
  error,
}: {
  rows: KycPerson[];
  onChange: (rows: KycPerson[]) => void;
  nameLabel: string;
  error?: string;
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
      {error ? <p className="m-0 text-xs normal-case text-destructive">{error}</p> : null}
    </div>
  );
}

export function InstitutionOnboardPage() {
  const { institutionId } = useParams();
  const { user } = useAuth();
  const isSuperAdmin = user?.role === "platform_admin";
  const canInviteFiAdmin = isSuperAdmin || user?.role === "bti_ops";
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FiKycForm>(emptyFiKyc);
  const [record, setRecord] = useState<InstitutionOnboarding | null>(null);
  const [loading, setLoading] = useState(Boolean(institutionId));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [showErrors, setShowErrors] = useState(false);

  const set = (patch: Partial<FiKycForm>) => setForm((prev) => ({ ...prev, ...patch }));
  const gating = wizardGated(record?.lifecycle_status);
  const reachable = gating ? maxReachableStep(form) : WIZARD_STEPS.length - 1;

  useEffect(() => {
    if (!institutionId) return;
    let alive = true;
    api
      .getInstitutionOnboarding(institutionId)
      .then((data) => {
        if (!alive) return;
        setRecord(data);
        const loaded = formFromOnboarding(data as unknown as Record<string, unknown>);
        setForm(loaded);
        setStep(wizardGated(data.lifecycle_status) ? maxReachableStep(loaded) : WIZARD_STEPS.length - 1);
        setShowErrors(false);
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

  function goToStep(index: number) {
    if (index < 0 || index >= WIZARD_STEPS.length) return;
    if (index > reachable) {
      setShowErrors(true);
      setError("Complete this page before moving ahead.");
      return;
    }
    setShowErrors(false);
    setError("");
    setStep(index);
  }

  async function onSaveDraft() {
    setBusy(true);
    setError("");
    try {
      await persist();
      setMessage("Draft saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save draft");
    } finally {
      setBusy(false);
    }
  }

  async function onNext() {
    const currentId = WIZARD_STEPS[step].id;
    if (gating && !isStepComplete(currentId, form)) {
      setShowErrors(true);
      setError("Complete the required fields on this page before continuing.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await persist();
      setShowErrors(false);
      setStep((n) => Math.min(n + 1, WIZARD_STEPS.length - 1));
      setMessage("Draft saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save draft");
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit() {
    const missing = WIZARD_STEPS.find((item) => item.id !== "review" && !isStepComplete(item.id, form));
    if (missing) {
      setStep(WIZARD_STEPS.findIndex((item) => item.id === missing.id));
      setShowErrors(true);
      setError("Complete the required fields before submitting.");
      return;
    }
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
  const errors = useMemo(() => (showErrors ? stepErrors(stepId, form) : {}), [showErrors, stepId, form]);
  const currentComplete = isStepComplete(stepId, form);

  const reviewRows = useMemo(
    () => [
      ["Legal name", form.legal_registered_name],
      ["Type", form.institution_type],
      ["Regulator", form.primary_regulator],
      ["Licence", form.licence_number],
      ["Primary contact", form.primary_contact_full_name],
      ["Settlement bank", form.settlement_bank_name],
      ["Go-live", form.target_go_live_date],
      ["BTI % Charge", form.bti_charge_pct],
    ],
    [form],
  );

  return (
    <PageShell wide>
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="m-0 text-lg font-semibold">Onboard financial institution</h2>
          <p className="muted m-0 mt-1 text-sm">
            Complete each page before Next. You cannot skip ahead. Save draft keeps incomplete work.
          </p>
        </div>
        <Link className="btn btn-secondary btn-sm" to="/institutions">
          Directory
        </Link>
      </header>

      <ol className="m-0 flex list-none items-start p-0">
        {WIZARD_STEPS.map((item, index) => {
          const done = index < reachable && isStepComplete(item.id, form);
          const current = index === step;
          const locked = index > reachable;
          const state = current ? "current" : done ? "done" : locked ? "locked" : "open";
          return (
            <li key={item.id} className="flex min-w-0 flex-1 flex-col gap-1">
              <div className="flex items-center">
                <button
                  type="button"
                  className={`grid size-7 shrink-0 place-items-center rounded-full border text-xs ${
                    current || done
                      ? "border-primary bg-primary text-primary-foreground"
                      : locked
                        ? "border-border text-muted"
                        : "border-primary bg-surface text-primary"
                  }`}
                  data-state={state}
                  aria-current={current ? "step" : undefined}
                  disabled={locked}
                  title={locked ? "Complete earlier pages first" : item.title}
                  onClick={() => goToStep(index)}
                >
                  {done && !current ? "✓" : index + 1}
                </button>
                {index < WIZARD_STEPS.length - 1 ? (
                  <span className={`mx-1 h-px min-w-2 flex-1 ${index < reachable ? "bg-primary" : "bg-border"}`} />
                ) : null}
              </div>
              <span className={`hidden pr-2 text-[0.65rem] uppercase tracking-wide sm:block ${current ? "text-foreground" : "text-muted"}`}>
                {item.title}
              </span>
            </li>
          );
        })}
      </ol>

      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}
      {loading ? <LoadingPanel rows={6} /> : null}

      {!loading ? (
        <section className="rounded-sm border border-border bg-surface p-3">
          <h3 className="m-0 mb-3 text-base font-semibold">{WIZARD_STEPS[step].title}</h3>
          {stepId === "identity" ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Legal registered name" required error={errors.legal_registered_name}>
                <input className={fieldClass} value={form.legal_registered_name} onChange={(e) => set({ legal_registered_name: e.target.value })} />
              </Field>
              <Field label="Institution code">
                <input className={fieldClass} value={form.code} onChange={(e) => set({ code: e.target.value.toUpperCase() })} placeholder="Auto from name if blank" />
              </Field>
              <Field label="Trading name">
                <input className={fieldClass} value={form.trading_name} onChange={(e) => set({ trading_name: e.target.value })} />
              </Field>
              <Field label="Institution type" required error={errors.institution_type}>
                <select className={fieldClass} value={form.institution_type} onChange={(e) => set({ institution_type: e.target.value })}>
                  {INSTITUTION_TYPES.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </Field>
              {form.institution_type === "OTHER" ? (
                <Field label="Other type" required error={errors.other_institution_type}>
                  <input className={fieldClass} value={form.other_institution_type} onChange={(e) => set({ other_institution_type: e.target.value })} />
                </Field>
              ) : null}
              <Field label="Registration number" error={errors.registration_number}>
                <input className={fieldClass} value={form.registration_number} onChange={(e) => set({ registration_number: e.target.value })} />
              </Field>
              <Field label="Incorporation date">
                <input className={fieldClass} type="date" value={form.incorporation_date} onChange={(e) => set({ incorporation_date: e.target.value })} />
              </Field>
              <Field label="Incorporation country" error={errors.incorporation_country}>
                <input className={fieldClass} value={form.incorporation_country} maxLength={2} onChange={(e) => set({ incorporation_country: e.target.value.toUpperCase() })} />
              </Field>
              <Field label="KRA PIN" error={errors.kra_pin}>
                <input className={fieldClass} value={form.kra_pin} onChange={(e) => set({ kra_pin: e.target.value.toUpperCase() })} placeholder="A123456789Z" />
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
              <Field label="Website" error={errors.website_url}>
                <input className={fieldClass} value={form.website_url} onChange={(e) => set({ website_url: e.target.value })} placeholder="https://" />
              </Field>
              <Field label="Support email" required error={errors.support_email}>
                <input className={fieldClass} type="email" value={form.support_email} onChange={(e) => set({ support_email: e.target.value })} />
              </Field>
              <Field label="Main telephone" required error={errors.main_telephone}>
                <input className={fieldClass} value={form.main_telephone} onChange={(e) => set({ main_telephone: e.target.value })} placeholder="+2547..." />
              </Field>
              <label className={`${labelClass} sm:col-span-2`}>
                Business description
                <textarea className={fieldClass} rows={3} value={form.business_description} onChange={(e) => set({ business_description: e.target.value })} />
              </label>
            </div>
          ) : null}

          {stepId === "regulatory" ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Primary regulator" required error={errors.primary_regulator}>
                <select className={fieldClass} value={form.primary_regulator} onChange={(e) => set({ primary_regulator: e.target.value })}>
                  {REGULATORS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </Field>
              {form.primary_regulator === "OTHER" ? (
                <Field label="Regulator name" required error={errors.regulator_other_name}>
                  <input className={fieldClass} value={form.regulator_other_name} onChange={(e) => set({ regulator_other_name: e.target.value })} />
                </Field>
              ) : null}
              <Field label="Licence number" required error={errors.licence_number}>
                <input className={fieldClass} value={form.licence_number} onChange={(e) => set({ licence_number: e.target.value })} />
              </Field>
              <Field label="Licence issue date" required error={errors.licence_issue_date}>
                <input className={fieldClass} type="date" value={form.licence_issue_date} onChange={(e) => set({ licence_issue_date: e.target.value })} />
              </Field>
              <Field label="Licence expiry date">
                <input className={fieldClass} type="date" value={form.licence_expiry_date} onChange={(e) => set({ licence_expiry_date: e.target.value })} />
              </Field>
              <Field label="Licence status" required error={errors.licence_status}>
                <select className={fieldClass} value={form.licence_status} onChange={(e) => set({ licence_status: e.target.value })}>
                  {LICENCE_STATUSES.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Regulator register URL" error={errors.regulator_register_url}>
                <input className={fieldClass} value={form.regulator_register_url} onChange={(e) => set({ regulator_register_url: e.target.value })} placeholder="https://" />
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
                <Field label="Ownership percentage" error={errors.ownership_percentage}>
                  <input className={fieldClass} value={form.ownership_percentage} onChange={(e) => set({ ownership_percentage: e.target.value })} />
                </Field>
                <Field label="CEO / managing director" required error={errors.ceo_managing_director_name}>
                  <input className={fieldClass} value={form.ceo_managing_director_name} onChange={(e) => set({ ceo_managing_director_name: e.target.value })} />
                </Field>
              </div>
              <div>
                <p className="m-0 mb-2 text-xs uppercase tracking-wide text-muted">Shareholders *</p>
                <PeopleEditor rows={form.owners_and_shareholders} onChange={(rows) => set({ owners_and_shareholders: rows })} nameLabel="Shareholder" error={errors.owners_and_shareholders} />
              </div>
              <div>
                <p className="m-0 mb-2 text-xs uppercase tracking-wide text-muted">Ultimate beneficial owners *</p>
                <PeopleEditor rows={form.ubo_details} onChange={(rows) => set({ ubo_details: rows })} nameLabel="UBO" error={errors.ubo_details} />
              </div>
              <div>
                <p className="m-0 mb-2 text-xs uppercase tracking-wide text-muted">Board *</p>
                <PeopleEditor rows={form.directors_board_members} onChange={(rows) => set({ directors_board_members: rows })} nameLabel="Director" error={errors.directors_board_members} />
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
                <Field label="Primary contact name" required error={errors.primary_contact_full_name}>
                  <input className={fieldClass} value={form.primary_contact_full_name} onChange={(e) => set({ primary_contact_full_name: e.target.value })} />
                </Field>
                <Field label="Title" required error={errors.primary_contact_title}>
                  <input className={fieldClass} value={form.primary_contact_title} onChange={(e) => set({ primary_contact_title: e.target.value })} />
                </Field>
                <Field label="Work email" required error={errors.primary_contact_work_email}>
                  <input className={fieldClass} type="email" value={form.primary_contact_work_email} onChange={(e) => set({ primary_contact_work_email: e.target.value })} />
                </Field>
                <Field label="Phone" required error={errors.primary_contact_phone}>
                  <input className={fieldClass} value={form.primary_contact_phone} onChange={(e) => set({ primary_contact_phone: e.target.value })} placeholder="+2547..." />
                </Field>
                <Field label="Compliance officer">
                  <input className={fieldClass} value={form.compliance_officer_name} onChange={(e) => set({ compliance_officer_name: e.target.value })} />
                </Field>
                <Field label="Compliance email" error={errors.compliance_officer_email}>
                  <input className={fieldClass} type="email" value={form.compliance_officer_email} onChange={(e) => set({ compliance_officer_email: e.target.value })} />
                </Field>
                <Field label="ID type" required error={errors.representative_id_type}>
                  <select className={fieldClass} value={form.representative_id_type} onChange={(e) => set({ representative_id_type: e.target.value })}>
                    {ID_TYPES.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="ID number" required error={errors.representative_id_number}>
                  <input className={fieldClass} value={form.representative_id_number} onChange={(e) => set({ representative_id_number: e.target.value })} />
                </Field>
                <Field label="Identity verification" required error={errors.representative_identity_verification_status}>
                  <select className={fieldClass} value={form.representative_identity_verification_status} onChange={(e) => set({ representative_identity_verification_status: e.target.value })}>
                    {VERIFY_STATUSES.map((opt) => (
                      <option key={opt} value={opt}>
                        {opt.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Authority to act (document reference)" required error={errors.authority_to_act_document_id}>
                  <input className={fieldClass} value={form.authority_to_act_document_id} onChange={(e) => set({ authority_to_act_document_id: e.target.value })} />
                </Field>
              </div>
              <div>
                <p className="m-0 mb-2 text-xs uppercase tracking-wide text-muted">Authorized signatories *</p>
                <PeopleEditor rows={form.authorized_signatories} onChange={(rows) => set({ authorized_signatories: rows })} nameLabel="Signatory" error={errors.authorized_signatories} />
              </div>
            </div>
          ) : null}

          {stepId === "settlement" ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Settlement bank" required error={errors.settlement_bank_name}>
                <input className={fieldClass} value={form.settlement_bank_name} onChange={(e) => set({ settlement_bank_name: e.target.value })} />
              </Field>
              <Field label="Account name" required error={errors.settlement_account_name}>
                <input className={fieldClass} value={form.settlement_account_name} onChange={(e) => set({ settlement_account_name: e.target.value })} />
              </Field>
              <Field label="Branch">
                <input className={fieldClass} value={form.settlement_branch} onChange={(e) => set({ settlement_branch: e.target.value })} />
              </Field>
              <Field label="Account number" required error={errors.settlement_account_number}>
                <input className={fieldClass} value={form.settlement_account_number} onChange={(e) => set({ settlement_account_number: e.target.value })} />
              </Field>
              <Field label="Currency" required error={errors.settlement_currency}>
                <input className={fieldClass} value={form.settlement_currency} maxLength={3} onChange={(e) => set({ settlement_currency: e.target.value.toUpperCase() })} />
              </Field>
              <Field label="Verification status" required error={errors.settlement_account_verification_status}>
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
              <Field label="Expected monthly count" required error={errors.expected_monthly_transaction_count}>
                <input className={fieldClass} value={form.expected_monthly_transaction_count} onChange={(e) => set({ expected_monthly_transaction_count: e.target.value })} />
              </Field>
              <Field label="Expected monthly value" required error={errors.expected_monthly_transaction_value}>
                <input className={fieldClass} value={form.expected_monthly_transaction_value} onChange={(e) => set({ expected_monthly_transaction_value: e.target.value })} />
              </Field>
              <Field label="Typical transaction amount" required error={errors.typical_transaction_amount}>
                <input className={fieldClass} value={form.typical_transaction_amount} onChange={(e) => set({ typical_transaction_amount: e.target.value })} />
              </Field>
              <Field label="Maximum transaction amount" required error={errors.maximum_transaction_amount}>
                <input className={fieldClass} value={form.maximum_transaction_amount} onChange={(e) => set({ maximum_transaction_amount: e.target.value })} />
              </Field>
              <Field label="Target go-live" required error={errors.target_go_live_date}>
                <input className={fieldClass} type="date" value={form.target_go_live_date} onChange={(e) => set({ target_go_live_date: e.target.value })} />
              </Field>
              <Field label="BTI % Charge" required error={errors.bti_charge_pct}>
                <input
                  className={fieldClass}
                  type="number"
                  min={0}
                  max={100}
                  step="0.0001"
                  value={form.bti_charge_pct}
                  onChange={(e) => set({ bti_charge_pct: e.target.value })}
                />
                <p className="meta" style={{ margin: "0.35rem 0 0" }}>
                  Unique for this FI. Default 0.004%. Super Admin can change later on Settings with password and OTP.
                </p>
              </Field>
              <Field label="Commercial agreement" required error={errors.commercial_agreement_status}>
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
              <Field label="Dispute contact email" error={errors.dispute_contact_email}>
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

          <div className="mt-4 flex flex-col gap-2 border-t border-border pt-4">
            {gating && step < WIZARD_STEPS.length - 1 && !currentComplete ? (
              <p className="m-0 text-sm text-muted">Fill required fields marked * to continue.</p>
            ) : null}
            <div className="flex flex-wrap items-center justify-end gap-2">
            <button type="button" className="btn btn-secondary" disabled={step === 0 || busy} onClick={() => goToStep(step - 1)}>
              Previous
            </button>
            {gating ? (
              <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void onSaveDraft()}>
                {busy ? "Saving…" : "Save draft"}
              </button>
            ) : null}
            {step < WIZARD_STEPS.length - 1 ? (
              <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void onNext()}>
                {busy ? "Saving…" : "Next"}
              </button>
            ) : record?.lifecycle_status === "pending_approval" && isSuperAdmin ? (
              <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void onDecide("approve")}>
                {busy ? "Approving…" : "Approve and activate"}
              </button>
            ) : record?.lifecycle_status === "active" && canInviteFiAdmin ? (
              <Link className="btn btn-primary" to="/users">
                Invite FI Admin
              </Link>
            ) : record?.lifecycle_status === "active" ? (
              <p className="m-0 self-center text-sm text-muted">
                This institution is already active. Super Admin or BTI Ops invites FI Admin from Users.
              </p>
            ) : (
              <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void onSubmit()}>
                {busy ? "Submitting…" : submitLabel}
              </button>
            )}
            </div>
          </div>
        </section>
      ) : null}
    </PageShell>
  );
}
