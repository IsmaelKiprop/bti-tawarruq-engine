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
