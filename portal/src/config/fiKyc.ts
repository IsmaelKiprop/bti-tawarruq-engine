export const INSTITUTION_TYPES = [
  { value: "BANK", label: "Bank" },
  { value: "SACCO", label: "SACCO" },
  { value: "MICROFINANCE_BANK", label: "Microfinance bank" },
  { value: "FINTECH", label: "Fintech" },
  { value: "PAYMENT_SERVICE_PROVIDER", label: "Payment service provider" },
  { value: "DIGITAL_LENDER", label: "Digital lender" },
  { value: "OTHER", label: "Other" },
] as const;

export const REGULATORS = [
  { value: "CBK", label: "CBK" },
  { value: "SASRA", label: "SASRA" },
  { value: "CMA", label: "CMA" },
  { value: "IRA", label: "IRA" },
  { value: "RBA", label: "RBA" },
  { value: "ODPC", label: "ODPC" },
  { value: "OTHER", label: "Other" },
  { value: "NOT_APPLICABLE", label: "Not applicable" },
] as const;

export const LICENCE_STATUSES = [
  "ACTIVE",
  "PENDING",
  "EXPIRED",
  "SUSPENDED",
  "REVOKED",
  "NOT_APPLICABLE",
  "UNDER_VERIFICATION",
] as const;

export const SCREEN_STATUSES = [
  "NOT_STARTED",
  "CLEAR",
  "POTENTIAL_MATCH",
  "CONFIRMED_MATCH",
  "REVIEW_REQUIRED",
  "NOT_APPLICABLE",
] as const;

export const ID_TYPES = [
  { value: "NATIONAL_ID", label: "National ID" },
  { value: "PASSPORT", label: "Passport" },
  { value: "ALIEN_ID", label: "Alien ID" },
  { value: "OTHER", label: "Other" },
] as const;

export const VERIFY_STATUSES = [
  "NOT_STARTED",
  "PENDING",
  "VERIFIED",
  "FAILED",
  "REVIEW_REQUIRED",
  "NOT_APPLICABLE",
] as const;

export const SETTLEMENT_VERIFY = ["NOT_STARTED", "PENDING", "VERIFIED", "FAILED", "REVIEW_REQUIRED"] as const;

export const AGREEMENT_STATUSES = [
  "NOT_STARTED",
  "DRAFT",
  "UNDER_REVIEW",
  "SIGNED",
  "REJECTED",
  "NOT_APPLICABLE",
] as const;

export const WIZARD_STEPS = [
  { id: "identity", title: "Identity" },
  { id: "regulatory", title: "Regulatory" },
  { id: "ownership", title: "Ownership" },
  { id: "representatives", title: "Representatives" },
  { id: "settlement", title: "Settlement" },
  { id: "commercial", title: "Commercial" },
  { id: "review", title: "Review" },
] as const;

export type WizardStepId = (typeof WIZARD_STEPS)[number]["id"];

const EMAIL = /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$/;
const PHONE = /^\+[1-9]\d{7,14}$/;
const NAME = /^[\p{L}\p{N}_][\p{L}\p{N}_\s.,'’&()/\\-]{1,198}$/u;
const CONTACT = /^[\p{L}\p{N}_][\p{L}\p{N}_\s.'-]{1,149}$/u;
const KRA = /^[A-Z]\d{9}[A-Z]$/;
const COUNTRY = /^[A-Z]{2}$/;
const CURRENCY = /^[A-Z]{3}$/;
const URL = /^https?:\/\/[^\s/$.?#].[^\s]*$/;
const REG_NO = /^[A-Za-z0-9][A-Za-z0-9./-]{1,49}$/;
const LICENCE = /^[A-Za-z0-9./ -]{2,80}$/;
const ACCOUNT = /^[A-Za-z0-9-]{4,34}$/;
const ID_NO = /^[A-Za-z0-9/-]{3,40}$/;
const COUNT = /^(0|[1-9]\d{0,8})$/;
const MONEY = /^\d{1,15}(\.\d{1,2})?$/;
const PCT = /^(100(\.0+)?|[0-9]{1,2}(\.[0-9]{1,4})?)$/;

function text(value: unknown): string {
  return String(value ?? "").trim();
}

function namedPeople(rows: KycPerson[]): boolean {
  return rows.some((row) => row.name.trim());
}

export type KycPerson = { name: string; title?: string; notes?: string };

export type FiKycForm = {
  legal_registered_name: string;
  code: string;
  trading_name: string;
  institution_type: string;
  other_institution_type: string;
  registration_number: string;
  incorporation_date: string;
  incorporation_country: string;
  kra_pin: string;
  registered_address_line1: string;
  registered_address_line2: string;
  registered_county: string;
  registered_postal_code: string;
  physical_address: string;
  website_url: string;
  support_email: string;
  main_telephone: string;
  business_description: string;
  primary_regulator: string;
  regulator_other_name: string;
  licence_number: string;
  licence_issue_date: string;
  licence_expiry_date: string;
  licence_status: string;
  regulator_register_url: string;
  ownership_structure_summary: string;
  parent_company_name: string;
  related_entities: string;
  owners_and_shareholders: KycPerson[];
  ownership_percentage: string;
  ubo_details: KycPerson[];
  directors_board_members: KycPerson[];
  ceo_managing_director_name: string;
  senior_management_details: KycPerson[];
  pep_screening_status: string;
  sanctions_screening_status: string;
  adverse_media_screening_status: string;
  primary_contact_full_name: string;
  primary_contact_title: string;
  primary_contact_work_email: string;
  primary_contact_phone: string;
  compliance_officer_name: string;
  compliance_officer_email: string;
  authorized_signatories: KycPerson[];
  representative_id_type: string;
  representative_id_number: string;
  representative_identity_verification_status: string;
  authority_to_act_document_id: string;
  settlement_bank_name: string;
  settlement_account_name: string;
  settlement_branch: string;
  settlement_account_number: string;
  settlement_currency: string;
  settlement_account_verification_status: string;
  settlement_account_evidence_document_id: string;
  expected_monthly_transaction_count: string;
  expected_monthly_transaction_value: string;
  typical_transaction_amount: string;
  maximum_transaction_amount: string;
  target_go_live_date: string;
  commercial_agreement_status: string;
  pricing_schedule_reference: string;
  dispute_contact_email: string;
};

export function emptyFiKyc(): FiKycForm {
  return {
    legal_registered_name: "",
    code: "",
    trading_name: "",
    institution_type: "BANK",
    other_institution_type: "",
    registration_number: "",
    incorporation_date: "",
    incorporation_country: "KE",
    kra_pin: "",
    registered_address_line1: "",
    registered_address_line2: "",
    registered_county: "",
    registered_postal_code: "",
    physical_address: "",
    website_url: "",
    support_email: "",
    main_telephone: "+254",
    business_description: "",
    primary_regulator: "CBK",
    regulator_other_name: "",
    licence_number: "",
    licence_issue_date: "",
    licence_expiry_date: "",
    licence_status: "ACTIVE",
    regulator_register_url: "",
    ownership_structure_summary: "",
    parent_company_name: "",
    related_entities: "",
    owners_and_shareholders: [{ name: "", title: "" }],
    ownership_percentage: "",
    ubo_details: [{ name: "", title: "" }],
    directors_board_members: [{ name: "", title: "" }],
    ceo_managing_director_name: "",
    senior_management_details: [{ name: "", title: "" }],
    pep_screening_status: "NOT_STARTED",
    sanctions_screening_status: "NOT_STARTED",
    adverse_media_screening_status: "NOT_STARTED",
    primary_contact_full_name: "",
    primary_contact_title: "",
    primary_contact_work_email: "",
    primary_contact_phone: "+254",
    compliance_officer_name: "",
    compliance_officer_email: "",
    authorized_signatories: [{ name: "", title: "" }],
    representative_id_type: "NATIONAL_ID",
    representative_id_number: "",
    representative_identity_verification_status: "NOT_STARTED",
    authority_to_act_document_id: "",
    settlement_bank_name: "",
    settlement_account_name: "",
    settlement_branch: "",
    settlement_account_number: "",
    settlement_currency: "KES",
    settlement_account_verification_status: "NOT_STARTED",
    settlement_account_evidence_document_id: "",
    expected_monthly_transaction_count: "",
    expected_monthly_transaction_value: "",
    typical_transaction_amount: "",
    maximum_transaction_amount: "",
    target_go_live_date: "",
    commercial_agreement_status: "NOT_STARTED",
    pricing_schedule_reference: "",
    dispute_contact_email: "",
  };
}

function asPeople(value: unknown): KycPerson[] {
  if (!Array.isArray(value) || value.length === 0) return [{ name: "", title: "" }];
  return value.map((row) => {
    if (typeof row === "string") return { name: row, title: "" };
    const rec = row as Record<string, unknown>;
    return { name: String(rec.name || rec.full_name || ""), title: String(rec.title || rec.role || "") };
  });
}

export function formFromOnboarding(data: Record<string, unknown>): FiKycForm {
  const base = emptyFiKyc();
  const next = { ...base };
  for (const key of Object.keys(base) as (keyof FiKycForm)[]) {
    const raw = data[key];
    if (key === "legal_registered_name") {
      next.legal_registered_name = String(data.legal_registered_name || data.name || "");
      continue;
    }
    if (
      key === "owners_and_shareholders" ||
      key === "ubo_details" ||
      key === "directors_board_members" ||
      key === "senior_management_details" ||
      key === "authorized_signatories"
    ) {
      next[key] = asPeople(raw);
      continue;
    }
    if (key === "related_entities") {
      next.related_entities = Array.isArray(raw) ? raw.map(String).join(", ") : String(raw || "");
      continue;
    }
    if (raw != null && raw !== "") next[key] = String(raw);
  }
  return next;
}

export function payloadFromForm(form: FiKycForm) {
  const people = (rows: KycPerson[]) => rows.filter((row) => row.name.trim()).map((row) => ({ name: row.name.trim(), title: row.title?.trim() || undefined }));
  return {
    ...form,
    related_entities: form.related_entities
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean),
    owners_and_shareholders: people(form.owners_and_shareholders),
    ubo_details: people(form.ubo_details),
    directors_board_members: people(form.directors_board_members),
    senior_management_details: people(form.senior_management_details),
    authorized_signatories: people(form.authorized_signatories),
    expected_monthly_transaction_count: form.expected_monthly_transaction_count
      ? Number(form.expected_monthly_transaction_count)
      : null,
    incorporation_country: form.incorporation_country.trim().toUpperCase() || null,
    settlement_currency: form.settlement_currency.trim().toUpperCase() || null,
  };
}

export function lifecycleLabel(status?: string | null, active?: boolean) {
  if (status === "pending_approval") return "Pending approval";
  if (status === "draft") return "Draft";
  if (status === "dormant") return "Dormant";
  if (status === "deactivated") return "Deactivated";
  if (status === "active" || active !== false) return "Active";
  return "Inactive";
}

export function isActiveInstitution(item: { lifecycle_status?: string | null; active?: boolean }) {
  return (item.lifecycle_status || (item.active === false ? "deactivated" : "active")) === "active";
}

export function stepErrors(stepId: WizardStepId, form: FiKycForm): Record<string, string> {
  const errors: Record<string, string> = {};
  const requireField = (key: keyof FiKycForm, label: string, pattern?: RegExp, invalid = `${label} is not valid`) => {
    const value = text(form[key]);
    if (!value) errors[key] = `${label} is required`;
    else if (pattern && !pattern.test(value)) errors[key] = invalid;
  };
  const optionalFormat = (key: keyof FiKycForm, label: string, pattern: RegExp) => {
    const value = text(form[key]);
    if (value && !pattern.test(value)) errors[key] = `${label} is not valid`;
  };

  if (stepId === "identity") {
    requireField("legal_registered_name", "Legal registered name", NAME);
    requireField("institution_type", "Institution type");
    if (form.institution_type === "OTHER") requireField("other_institution_type", "Other type");
    requireField("support_email", "Support email", EMAIL);
    requireField("main_telephone", "Main telephone", PHONE, "Use international format, for example +2547...");
    optionalFormat("registration_number", "Registration number", REG_NO);
    optionalFormat("incorporation_country", "Incorporation country", COUNTRY);
    optionalFormat("kra_pin", "KRA PIN", KRA);
    optionalFormat("website_url", "Website", URL);
  }

  if (stepId === "regulatory") {
    requireField("primary_regulator", "Primary regulator");
    if (form.primary_regulator === "OTHER") requireField("regulator_other_name", "Regulator name");
    requireField("licence_number", "Licence number", LICENCE);
    requireField("licence_issue_date", "Licence issue date");
    requireField("licence_status", "Licence status");
    optionalFormat("regulator_register_url", "Regulator register URL", URL);
  }

  if (stepId === "ownership") {
    if (!namedPeople(form.owners_and_shareholders)) errors.owners_and_shareholders = "Add at least one shareholder";
    if (!namedPeople(form.ubo_details)) errors.ubo_details = "Add at least one ultimate beneficial owner";
    if (!namedPeople(form.directors_board_members)) errors.directors_board_members = "Add at least one board member";
    requireField("ceo_managing_director_name", "CEO / managing director", CONTACT);
    optionalFormat("ownership_percentage", "Ownership percentage", PCT);
  }

  if (stepId === "representatives") {
    requireField("primary_contact_full_name", "Primary contact name", CONTACT);
    requireField("primary_contact_title", "Title");
    requireField("primary_contact_work_email", "Work email", EMAIL);
    requireField("primary_contact_phone", "Phone", PHONE, "Use international format, for example +2547...");
    optionalFormat("compliance_officer_email", "Compliance email", EMAIL);
    if (!namedPeople(form.authorized_signatories)) errors.authorized_signatories = "Add at least one authorized signatory";
    requireField("representative_id_type", "ID type");
    requireField("representative_id_number", "ID number", ID_NO);
    requireField("representative_identity_verification_status", "Identity verification");
    requireField("authority_to_act_document_id", "Authority to act document reference");
  }

  if (stepId === "settlement") {
    requireField("settlement_bank_name", "Settlement bank");
    requireField("settlement_account_name", "Account name");
    requireField("settlement_account_number", "Account number", ACCOUNT);
    requireField("settlement_currency", "Currency", CURRENCY);
    requireField("settlement_account_verification_status", "Verification status");
  }

  if (stepId === "commercial") {
    requireField("expected_monthly_transaction_count", "Expected monthly count", COUNT);
    requireField("expected_monthly_transaction_value", "Expected monthly value", MONEY);
    requireField("typical_transaction_amount", "Typical transaction amount", MONEY);
    requireField("maximum_transaction_amount", "Maximum transaction amount", MONEY);
    requireField("target_go_live_date", "Target go-live");
    requireField("commercial_agreement_status", "Commercial agreement");
    optionalFormat("dispute_contact_email", "Dispute contact email", EMAIL);
  }

  return errors;
}

export function isStepComplete(stepId: WizardStepId, form: FiKycForm): boolean {
  if (stepId === "review") return true;
  return Object.keys(stepErrors(stepId, form)).length === 0;
}

export function maxReachableStep(form: FiKycForm): number {
  for (let i = 0; i < WIZARD_STEPS.length; i += 1) {
    const id = WIZARD_STEPS[i].id;
    if (id === "review" || !isStepComplete(id, form)) return i;
  }
  return WIZARD_STEPS.length - 1;
}

export function wizardGated(lifecycle?: string | null): boolean {
  return !lifecycle || lifecycle === "draft";
}
