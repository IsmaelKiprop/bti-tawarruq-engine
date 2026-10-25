const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";
const API_KEY_STORAGE = "tawarruq_api_key";
const ACCESS_TOKEN_STORAGE = "tawarruq_access_token";
const SESSION_USER_STORAGE = "tawarruq_session_user";

export function getStoredApiKey(): string {
  return localStorage.getItem(API_KEY_STORAGE) || import.meta.env.VITE_API_KEY || "";
}

export function setStoredApiKey(key: string) {
  if (key.trim()) {
    localStorage.setItem(API_KEY_STORAGE, key.trim());
  } else {
    localStorage.removeItem(API_KEY_STORAGE);
  }
}

export function clearStoredApiKey() {
  localStorage.removeItem(API_KEY_STORAGE);
}

export function getAccessToken(): string {
  return localStorage.getItem(ACCESS_TOKEN_STORAGE) || "";
}

export function setAccessToken(token: string) {
  if (token.trim()) localStorage.setItem(ACCESS_TOKEN_STORAGE, token.trim());
  else localStorage.removeItem(ACCESS_TOKEN_STORAGE);
}

export function clearAccessToken() {
  localStorage.removeItem(ACCESS_TOKEN_STORAGE);
  localStorage.removeItem(SESSION_USER_STORAGE);
}

export function clearPortalSession() {
  clearAccessToken();
  clearStoredApiKey();
}

export interface SessionUser {
  email: string;
  full_name: string;
  role: string;
  institution_id: string | null;
  institution_name?: string | null;
  agent_dealer_id?: string | null;
  user_id?: string | null;
  must_change_password: boolean;
  permissions: string[];
  mfa_enroll_required?: boolean;
  mfa_enabled?: boolean;
  mfa_method?: "totp" | "email" | null;
  job_title?: string | null;
  department?: string | null;
  employee_number?: string | null;
  phone?: string | null;
  office?: string | null;
}

export function getStoredSessionUser(): SessionUser | null {
  const raw = localStorage.getItem(SESSION_USER_STORAGE);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionUser;
  } catch {
    return null;
  }
}

export function setStoredSessionUser(user: SessionUser | null) {
  if (!user) localStorage.removeItem(SESSION_USER_STORAGE);
  else localStorage.setItem(SESSION_USER_STORAGE, JSON.stringify(user));
}

function authHeaders(extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const apiKey = getStoredApiKey();
  if (apiKey) headers["X-API-Key"] = apiKey;
  return { ...headers, ...extra };
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: authHeaders(options?.headers),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail;
    if (response.status === 404) {
      throw new Error(
        typeof detail === "string" && detail !== "Not Found"
          ? detail
          : "API route not found — restart the engine so it loads the latest Kenya ops endpoints.",
      );
    }
    throw new Error(
      typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : `Request failed: ${response.status}`,
    );
  }
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export interface Application {
  id: string;
  institution_id?: string;
  institution_name?: string | null;
  customer_id?: string | null;
  customer_ref: string;
  customer_name?: string | null;
  currency?: string;
  amount_requested: string;
  term_months: number;
  purpose: string;
  status: string;
  current_phase?: string | null;
  created_at: string;
}

export interface KenyaCustomer {
  id: string;
  institution_id: string;
  institution_name?: string | null;
  institution_code?: string | null;
  full_name: string;
  phone: string;
  email?: string | null;
  wallet_number: string;
  national_id?: string | null;
  kyc_status: string;
  aml_status: string;
  credit_score: number;
  wallet_provider?: string;
  created_at: string | null;
}

export interface Certificate {
  id?: string;
  certificate_number: string;
  issuer: string;
  seller?: string | null;
  buyer?: string | null;
  bid_no?: string | null;
  selling_time?: string | null;
  selling_date?: string | null;
  value_date?: string | null;
  product_code?: string | null;
  product_description?: string | null;
  unit?: string | null;
  volume?: string | null;
  currency?: string | null;
  price?: string | null;
  price_myr_equivalent?: string | null;
  value_amount?: string | null;
  transaction_type?: string | null;
  pdf_path?: string | null;
  pdf_filename?: string | null;
  received_at?: string;
}

export interface Leg {
  id: string;
  leg_number: string;
  status: string;
  external_ref: string | null;
  bsas_fee: string | null;
  executed_at: string | null;
  certificate: Certificate | null;
}

export interface EcertConfirmInput {
  certificate_number: string;
  issuer?: string;
  seller?: string;
  buyer?: string;
  bid_no?: string;
  selling_time?: string;
  selling_date?: string;
  value_date?: string;
  product_code?: string;
  product_description?: string;
  unit?: string;
  volume?: string;
  currency?: string;
  price?: string;
  price_myr_equivalent?: string;
  value_amount?: string;
  transaction_type?: string;
  file?: File | null;
}

export interface Transaction {
  id: string;
  application_id: string;
  commodity_code: string;
  mode: string;
  status: string;
  legs: Leg[];
  created_at: string;
}

export interface AuditEvent {
  id: string;
  entity_type?: string;
  entity_id?: string;
  actor: string;
  action: string;
  details: string | null;
  evidence_ref?: string | null;
  timestamp: string;
  institution_id?: string | null;
  actor_user_id?: string | null;
  group_id?: string | null;
  action_group?: string | null;
  http_method?: string | null;
  http_path?: string | null;
  http_status?: number | null;
}

export interface AuditGroup {
  group_id: string;
  action_group: string;
  institution_id?: string | null;
  actor_user_id?: string | null;
  actor?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  events: AuditEvent[];
}

export interface AuditFeed {
  scope_institution_id?: string | null;
  cross_tenant: boolean;
  groups: AuditGroup[];
  events: AuditEvent[];
}

export interface ShariahAuditEntry {
  id: string;
  timestamp: string;
  step_id: string;
  entity_type: string;
  entity_id: string;
  asset_ref_no: string | null;
  actor_from: string;
  actor_to: string;
  payload_hash: string;
  details: string | null;
  mno_receipt_id?: string | null;
  previous_hash?: string | null;
  entry_hash?: string | null;
}

export interface BusinessStatus {
  application_id: string;
  customer_sale_recorded: boolean;
  customer_agency_appointed: boolean;
  ready_for_leg_3: boolean;
}

export interface SedaniaStep {
  n: number;
  id: string;
  title: string;
  status: "done" | "pending" | "skipped" | string;
  detail: string;
  documents: string[];
}

export interface SedaniaCertificate {
  kind: string;
  certificate_number: string;
  source: string;
  url: string;
  source_url?: string | null;
  batch_id?: string | null;
  serial_numbers: string[];
  retention_until: string;
}

export interface SedaniaStamp {
  token_id: string;
  signature: string;
  kind: string;
}

export interface SedaniaFinancing {
  execution_id: string;
  application_id: string | null;
  customer_id: string;
  institution_id: string;
  amount: string;
  profit_amount: string;
  deferred_price: string;
  tenor_months: number;
  currency: string;
  status: string;
  sedania_batch_id: string | null;
  wad: SedaniaStamp | null;
  wakalah: SedaniaStamp | null;
  cmp: SedaniaStamp | null;
  certificates: Record<string, SedaniaCertificate>;
  callback_delivered: boolean;
  cash_disbursement: string;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  path: string;
  flow_variant: string;
  delivery_mode: string;
  agency_role: string;
  agency_party: string;
  appoint_sasc: boolean;
  purchase_order_ref: string | null;
  commodity_invoice_ref: string | null;
  delivery_order_ref: string | null;
  trading_ecert_ref: string | null;
  supplier_ref: string | null;
  purchaser_ref: string | null;
  muqassah_ref: string | null;
  muqassah_at: string | null;
  casa_account: string | null;
  casa_ref: string | null;
  casa_credited_at: string | null;
  physical_delivery_requested: boolean;
  physical_delivery_status: string | null;
  physical_delivery_notified_at: string | null;
  repayment_settled_at: string | null;
  steps: SedaniaStep[];
}

export interface SedaniaFinancingRequest {
  customer_id: string;
  amount: string;
  tenor: number;
  currency: string;
  flow_variant: "approved_wakeel" | "aaoifi_rasul";
  delivery_mode: "constructive" | "physical";
  appoint_sasc: boolean;
  casa_account?: string;
  institution_id?: string;
  client_request_id?: string;
}

export interface SedaniaDocumentIndex {
  kind: string;
  label: string;
  available: boolean;
  ref: string | null;
  url: string | null;
}

export interface Institution {
  id: string;
  name: string;
  code: string;
  bsas_mode: string;
  active?: boolean;
  approval_steps?: string;
  approval_limit_amount?: string | null;
  billing_fee_bps?: number;
  created_at: string;
}

export interface Webhook {
  id: string;
  institution_id: string;
  url: string;
  events: string[];
  active: boolean;
  created_at: string;
}

export interface ApiKeyRecord {
  id: string;
  institution_id: string;
  name: string;
  key_prefix: string;
  role: string;
  active: boolean;
  created_at: string;
}

export interface AuthContext {
  auth_enabled: boolean;
  authenticated: boolean;
  role: string | null;
  institution_id: string | null;
  institution_name?: string | null;
  is_platform_admin: boolean;
  permissions: string[];
  email?: string | null;
  full_name?: string | null;
  user_id?: string | null;
  agent_dealer_id?: string | null;
  must_change_password?: boolean;
  auth_method?: string | null;
  mfa_enabled?: boolean;
  mfa_enroll_required?: boolean;
  mfa_method?: "totp" | "email" | null;
  job_title?: string | null;
  department?: string | null;
  employee_number?: string | null;
  phone?: string | null;
  office?: string | null;
  deployment_mode?: string;
  enabled_products?: string[];
  brand_name?: string;
}

export interface OpsMetrics {
  timestamp: string;
  scoped_institution_id: string | null;
  applications_total: number;
  applications_by_status: Record<string, number>;
  transactions_total: number;
  transactions_by_status: Record<string, number>;
  manual_bridge_pending: number;
  institutions_total: number;
  active_webhooks: number;
  active_api_keys: number;
  audit_events_today: number;
  amanah_enabled: boolean;
  amanah_write_enabled: boolean;
  auth_enabled: boolean;
  kenya_integration_mode: string;
  http_requests_total: number;
  http_errors_total: number;
  http_latency_ms_avg: number;
  http_by_status: Record<string, number>;
  http_top_paths: Record<string, number>;
  applications_open?: number;
  applications_completed?: number;
  applications_failed?: number;
  transactions_open?: number;
  pending_approvals?: number;
  book_amount_requested?: number;
  disbursed_volume?: number;
  completion_rate_pct?: number;
  projected_30d_volume?: number;
  projected_open_book?: number;
  week_disbursed_volume?: number;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: string;
  email: string;
  full_name: string;
  institution_id: string | null;
  institution_name?: string | null;
  agent_dealer_id?: string | null;
  must_change_password: boolean;
  permissions: string[];
  mfa_required?: boolean;
  mfa_token?: string | null;
  mfa_enroll_required?: boolean;
  mfa_enabled?: boolean;
  mfa_method?: "totp" | "email" | null;
  mfa_dev_code?: string | null;
}

export interface PendingApproval {
  id: string;
  institution_id: string;
  institution_name?: string | null;
  step: string;
  action: string;
  status: string;
  amount: string | null;
  currency: string;
  application_id: string | null;
  transaction_id: string | null;
  requested_by_id: string | null;
  decision_note: string | null;
  last_error: string | null;
  created_at: string | null;
  queued?: boolean;
}

export interface BillingInvoice {
  id: string;
  institution_id: string;
  institution_name?: string | null;
  period_start: string | null;
  period_end: string | null;
  transaction_count: number;
  volume_amount: string;
  fee_bps: number;
  fee_amount: string;
  currency: string;
  status: string;
  issued_at: string | null;
  paid_at: string | null;
  note: string | null;
}

export interface ReconciliationRow {
  id: string;
  institution_id: string;
  institution_name?: string | null;
  transaction_id: string;
  application_id: string | null;
  expected_amount: string;
  settled_amount: string;
  currency: string;
  status: string;
  note: string | null;
  created_at: string | null;
}

export interface OpsUserRecord {
  id: string;
  email: string;
  full_name: string;
  role: string;
  institution_id: string | null;
  agent_dealer_id?: string | null;
  must_change_password: boolean;
  active: boolean;
  approval_limit_amount?: string | null;
  mfa_enabled?: boolean;
  job_title?: string | null;
  department?: string | null;
  employee_number?: string | null;
  phone?: string | null;
  office?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export type OpsUserProfilePatch = {
  full_name?: string | null;
  job_title?: string | null;
  department?: string | null;
  employee_number?: string | null;
  phone?: string | null;
  office?: string | null;
};

export type OpsUserAdminPatch = OpsUserProfilePatch & {
  email?: string | null;
  role?: string | null;
  institution_id?: string | null;
  agent_dealer_id?: string | null;
  active?: boolean | null;
  approval_limit_amount?: string | null;
};

export interface KenyaOpsCase {
  application_id: string;
  institution_id: string;
  customer_ref: string;
  customer_name: string;
  customer_phone: string | null;
  customer_email: string | null;
  journey_url: string | null;
  wallet_number: string | null;
  amount_requested: string;
  term_months: number;
  purpose: string;
  status: string;
  current_phase: string | null;
  eligibility_passed: boolean | null;
  offer_accepted: boolean;
  murabaha_signed: boolean;
  wakala_appointed: boolean;
  wakala_notes: string | null;
  possession_sealed: boolean;
  transaction_id: string | null;
  transaction_status: string | null;
  transaction_phase: string | null;
  transaction_mode: string | null;
  commodity_code: string | null;
  batch_id: string | null;
  asset_ref_hash: string | null;
  mno_receipt_id: string | null;
  possession_status: string | null;
  broker_code: string | null;
  broker_name: string | null;
  broker_is_mno_pool: boolean | null;
  no_inah_validated: boolean | null;
  liquidation_spot_amount: string | null;
  wallet_status: string | null;
  wallet_provider: string | null;
  wallet_external_txn_id: string | null;
  wallet_credited: boolean;
  installments_total: number;
  installments_paid: number;
  next_action: string;
  next_action_label: string;
  created_at: string | null;
  offer: {
    cost_price: string;
    profit_amount: string;
    total_payable: string;
    accepted: boolean;
  } | null;
  legs: { leg_number: string; status: string; external_ref: string | null }[];
}

export interface RepaymentBoardItem {
  installment_id: string;
  application_id: string;
  customer_ref: string;
  customer_name: string;
  installment_number: number;
  due_date: string | null;
  amount: string;
  status: string;
  paid_at: string | null;
  payment_ref: string | null;
}

export interface BrokerInfo {
  id: string;
  code: string;
  name: string;
  is_mno_pool: boolean;
  active: boolean;
  eligible_for_liquidation: boolean;
}

export interface KenyaFlowStatus {
  application_id: string;
  current_phase: string | null;
  eligibility_passed: boolean | null;
  offer_accepted: boolean;
  murabaha_signed: boolean;
  wakala_appointed: boolean;
  wallet_credited: boolean;
  transaction_id: string | null;
  transaction_status: string | null;
  transaction_phase: string | null;
  installments_total: number;
  installments_paid: number;
}

export interface OfferSummary {
  application_id: string;
  cost_price: string;
  profit_amount: string;
  total_payable: string;
  installment_count: number;
  accepted: boolean;
}

export interface RepaymentInstallment {
  id: string;
  contract_id: string;
  installment_number: number;
  due_date: string;
  amount: string;
  status: string;
  paid_at: string | null;
  payment_ref: string | null;
}

export interface ShariahIntegrity {
  valid: boolean;
  ledger_chain: Record<string, unknown>;
  possession_sealed: boolean;
  entry_count: number;
  application_id: string;
}

export interface Disbursement {
  id: string;
  application_id: string;
  transaction_id: string;
  amount: string;
  tawarruq_certificate?: { certificate_number: string } | null;
}

export interface ManualBridgePendingItem {
  transaction_id: string;
  application_id: string;
  institution_id?: string | null;
  institution_code?: string | null;
  institution_name?: string | null;
  customer_ref: string | null;
  customer_name?: string | null;
  currency?: string | null;
  amount_requested: string | null;
  bid_amount?: string | null;
  profit_amount?: string | null;
  murabaha_total?: string | null;
  commodity_code: string;
  product_code?: string | null;
  purchase_type?: string | null;
  transaction_status: string;
  leg_number: string;
  leg_label: string;
  leg_status: string;
  external_ref: string | null;
  request: Record<string, unknown> | null;
  email_body?: string | null;
  created_at: string | null;
}

export interface ManualBridgeDetail extends ManualBridgePendingItem {
  reply_on_disk: boolean;
  ops_instructions: string[];
}

export interface ManualBridgeInbox {
  inbox_dir: string;
  request_count: number;
  reply_count: number;
  unanswered_request_refs: string[];
}

export interface DeskBatch {
  institution_id: string | null;
  institution_name: string | null;
  institution_code: string | null;
  leg_number: string;
  customer_count: number;
  customers: {
    end_customer_name: string | null;
    customer_ref: string | null;
    external_ref: string | null;
    currency: string;
    bid_amount: number;
    profit_amount: number;
    murabaha_total: number;
    product_code: string;
    purchase_type: string;
  }[];
  email_body: string;
  batch_email_path?: string | null;
  generated_at: string;
}

export interface InstitutionIntegration {
  institution_id: string;
  kenya_mode: string | null;
  callback_base_url: string | null;
  mpesa_env: string | null;
  mpesa_shortcode: string | null;
  mpesa_initiator_name: string | null;
  mpesa_b2c_command_id: string | null;
  mno_safaricom_api_url: string | null;
  mno_safaricom_dealer_code: string | null;
  mno_airtel_api_url: string | null;
  mno_airtel_token_url: string | null;
  mno_airtel_client_id: string | null;
  active: boolean;
  mpesa_consumer_key_set: boolean;
  mpesa_consumer_secret_set: boolean;
  mpesa_security_credential_set: boolean;
  mpesa_stk_passkey_set: boolean;
  mno_safaricom_api_key_set: boolean;
  mno_airtel_client_secret_set: boolean;
}

export interface IntegrationStatus {
  institution_id: string;
  kenya_mode: string;
  mpesa_configured: boolean;
  mno_safaricom_configured: boolean;
  callback_urls: Record<string, string>;
}

export type InstitutionIntegrationPayload = Partial<{
  kenya_mode: string;
  callback_base_url: string;
  mpesa_env: string;
  mpesa_consumer_key: string;
  mpesa_consumer_secret: string;
  mpesa_shortcode: string;
  mpesa_initiator_name: string;
  mpesa_security_credential: string;
  mpesa_stk_passkey: string;
  mpesa_b2c_command_id: string;
  mno_safaricom_api_url: string;
  mno_safaricom_api_key: string;
  mno_safaricom_dealer_code: string;
  mno_airtel_api_url: string;
  mno_airtel_token_url: string;
  mno_airtel_client_id: string;
  mno_airtel_client_secret: string;
  active: boolean;
}>;

export interface AgentDealer {
  id: string;
  code: string;
  business_name: string;
  mpesa_number: string;
  mpesa_till_number: string | null;
  float_balance: number;
  institution_id: string | null;
  contact_name: string | null;
  contact_phone: string | null;
  active: boolean;
  created_at: string | null;
  float_history?: AgentDealerTopup[];
}

export interface AgentDealerSummary {
  total_active_dealers: number;
  total_float_balance: number;
  health: "green" | "amber" | "red";
  primary_dealer: {
    id: string;
    code: string;
    business_name: string;
    float_balance: number;
    mpesa_till_number: string | null;
  } | null;
}

export interface AgentDealerTopup {
  id: string;
  amount: number;
  kind?: "topup" | "draw";
  reference: string | null;
  note: string | null;
  added_by: string | null;
  created_at: string | null;
}

export interface JourneyStep {
  number: number;
  label: string;
  description: string;
  actor: string;
  status: "done" | "active" | "pending";
  timestamp: string | null;
  certificate?: JourneyCertificate | null;
  installments_total?: number;
  installments_paid?: number;
  next_due?: string | null;
  wad_accepted?: boolean;
  wad_text?: string | null;
  wakala_ref?: string | null;
  wakala_notes?: string | null;
  wallet_txn_id?: string | null;
  wallet_provider?: string | null;
  wallet_credited?: boolean;
  payments?: {
    installment_number: number;
    amount: string;
    status: string;
    payment_ref: string | null;
  }[];
  documents?: {
    purchase_order?: string | null;
    supplier_invoice?: string | null;
    delivery_order?: string | null;
    batch_id?: string | null;
    receipt_id?: string | null;
    source_dealer?: string | null;
    commodity_kind?: string | null;
    commodity_operator?: string | null;
    commodity_label?: string | null;
    downloadable?: boolean;
  } | null;
}

export interface JourneyCertificate {
  certificate_number: string;
  issuer: string;
  seller?: string | null;
  buyer?: string | null;
  selling_time?: string | null;
  selling_date?: string | null;
  value_date?: string | null;
  product_code?: string | null;
  volume?: string | null;
  currency?: string | null;
  price?: string | null;
  value_amount?: string | null;
  pdf_filename?: string | null;
  downloadable: boolean;
  type?: string;
}

export interface CustomerJourney {
  application_id: string;
  customer_ref: string;
  customer_name: string | null;
  customer_phone: string | null;
  track: "malaysia" | "kenya";
  status: string;
  amount: string;
  term_months?: number;
  currency: string;
  murabaha_total: string | null;
  profit: string | null;
  commodity: string | null;
  institution_name: string | null;
  wad_accepted?: boolean;
  wad_text?: string | null;
  offer_accepted?: boolean;
  contract_signed?: boolean;
  customer_action?: "accept" | "sign" | null;
  trade_documents?: JourneyStep["documents"];
  created_at: string | null;
  steps: JourneyStep[];
  certificates: (JourneyCertificate & { step: number; label: string })[]; 
  overall_progress: number;
  total_steps: number;
}

async function requestOptional<T>(path: string): Promise<T | null> {
  const response = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  if (response.status === 404) return null;
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

export const api = {
  listApplications: () => request<Application[]>("/applications"),
  listTransactions: () => request<Transaction[]>("/transactions"),
  createApplication: (body: {
    customer_ref?: string;
    customer_id?: string;
    customer_name?: string;
    currency?: string;
    amount_requested: string;
    term_months: number;
    purpose: string;
  }) => request<Application>("/applications", { method: "POST", body: JSON.stringify(body) }),
  getApplication: (id: string) => request<Application>(`/applications/${id}`),
  deleteApplication: (id: string) => request<void>(`/applications/${id}`, { method: "DELETE" }),
  getBusinessStatus: (id: string) => request<BusinessStatus>(`/applications/${id}/business-status`),
  getShariahAudit: (applicationId: string) =>
    request<ShariahAuditEntry[]>(`/applications/${applicationId}/shariah-audit`),
  createOffer: (id: string, body?: { cost_price?: string; profit_rate_pct?: string }) =>
    request(`/applications/${id}/offer`, {
      method: "POST",
      body: JSON.stringify(body || {}),
    }),
  acceptOffer: (id: string) => request(`/applications/${id}/accept`, { method: "POST" }),
  recordCustomerSale: (id: string) =>
    request(`/applications/${id}/customer-sale`, { method: "POST" }),
  appointCustomerAgency: (id: string) =>
    request(`/applications/${id}/customer-agency`, { method: "POST", body: "{}" }),
  runFullMalaysiaFlow: (applicationId: string) =>
    request<{
      application_id: string;
      transaction_id: string;
      status: string;
      legs_confirmed: number;
      disbursement_id: string | null;
      certificate_number: string | null;
    }>(`/malaysia/applications/${applicationId}/run-full-flow`, { method: "POST" }),
  createTransaction: (application_id: string, mode = "mock", commodity_code = "PALM_OIL") =>
    request<Transaction>("/transactions", {
      method: "POST",
      body: JSON.stringify({ application_id, mode, commodity_code }),
    }),
  createDisbursement: (application_id: string, transaction_id: string) =>
    request<Disbursement>("/disbursements", {
      method: "POST",
      body: JSON.stringify({ application_id, transaction_id }),
    }),
  getTransaction: (id: string) => request<Transaction>(`/transactions/${id}`),
  confirmLeg: (
    transactionId: string,
    legNumber: string,
    certificate_number: string,
    issuer = "Bursa Malaysia Islamic Services Sdn.Bhd.",
  ) =>
    request<Transaction>(`/transactions/${transactionId}/legs/${legNumber}/confirm`, {
      method: "POST",
      body: JSON.stringify({ certificate_number, issuer }),
    }),

  confirmEcert: async (transactionId: string, legNumber: string, input: EcertConfirmInput) => {
    const form = new FormData();
    form.append("certificate_number", input.certificate_number);
    form.append("issuer", input.issuer || "Bursa Malaysia Islamic Services Sdn.Bhd.");
    const optional: Array<keyof EcertConfirmInput> = [
      "seller",
      "buyer",
      "bid_no",
      "selling_time",
      "selling_date",
      "value_date",
      "product_code",
      "product_description",
      "unit",
      "volume",
      "currency",
      "price",
      "price_myr_equivalent",
      "value_amount",
      "transaction_type",
    ];
    for (const key of optional) {
      const value = input[key];
      if (typeof value === "string" && value.trim()) form.append(key, value.trim());
    }
    if (input.file) form.append("file", input.file);

    const headers: Record<string, string> = {};
    const token = getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    const apiKey = getStoredApiKey();
    if (apiKey) headers["X-API-Key"] = apiKey;

    const response = await fetch(
      `${API_BASE}/manual-bridge/transactions/${transactionId}/legs/${legNumber}/confirm`,
      { method: "POST", headers, body: form },
    );
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const detail = body.detail;
      throw new Error(typeof detail === "string" ? detail : `Request failed: ${response.status}`);
    }
    return response.json() as Promise<Transaction>;
  },
  executeLeg: (transactionId: string, leg: "purchase" | "transfer" | "sale") =>
    request<Transaction>(`/transactions/${transactionId}/legs/${leg}`, { method: "POST" }),
  listManualBridgePending: () => request<ManualBridgePendingItem[]>("/manual-bridge/pending"),
  getManualBridgeInbox: () => request<ManualBridgeInbox>("/manual-bridge/inbox"),
  getManualBridgeDeskBatch: (institutionId?: string) =>
    request<DeskBatch>(
      `/manual-bridge/desk-batch${institutionId ? `?institution_id=${institutionId}` : ""}`,
    ),
  getManualBridgeLeg: (transactionId: string, legNumber: string) =>
    request<ManualBridgeDetail>(`/manual-bridge/transactions/${transactionId}/legs/${legNumber}`),
  advanceManualBridge: (transactionId: string) =>
    request<Transaction>(`/manual-bridge/transactions/${transactionId}/advance`, { method: "POST" }),
  getAudit: (entityId: string) => request<AuditEvent[]>(`/audit?entity_id=${entityId}`),
  getOpsAuditFeed: (params?: {
    institution_id?: string;
    action_group?: string;
    actor_user_id?: string;
    group_id?: string;
    limit?: number;
    grouped?: boolean;
  }) => {
    const q = new URLSearchParams();
    if (params?.institution_id) q.set("institution_id", params.institution_id);
    if (params?.action_group) q.set("action_group", params.action_group);
    if (params?.actor_user_id) q.set("actor_user_id", params.actor_user_id);
    if (params?.group_id) q.set("group_id", params.group_id);
    if (params?.limit != null) q.set("limit", String(params.limit));
    if (params?.grouped != null) q.set("grouped", String(params.grouped));
    const qs = q.toString();
    return request<AuditFeed>(`/ops/audit${qs ? `?${qs}` : ""}`);
  },

  listInstitutions: () => request<Institution[]>("/institutions"),
  getInstitution: (institutionId: string) => request<Institution>(`/institutions/${institutionId}`),
  createInstitution: (body: {
    name: string;
    code: string;
    bsas_mode?: string;
    approval_limit_amount?: string | null;
    approval_steps?: string;
  }) =>
    request<Institution>("/institutions", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateInstitution: (
    institutionId: string,
    body: {
      name?: string;
      bsas_mode?: string;
      active?: boolean;
      approval_steps?: string;
      approval_limit_amount?: string | null;
      billing_fee_bps?: number;
    },
  ) =>
    request<Institution>(`/institutions/${institutionId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteInstitution: (institutionId: string) =>
    request<void>(`/institutions/${institutionId}`, { method: "DELETE" }),
  listWebhooks: (institutionId?: string) =>
    request<Webhook[]>(`/webhooks${institutionId ? `?institution_id=${institutionId}` : ""}`),
  registerWebhook: (body: { institution_id: string; url: string; events: string[] }) =>
    request<Webhook & { secret: string }>("/webhooks", { method: "POST", body: JSON.stringify(body) }),
  listApiKeys: (institutionId: string) =>
    request<ApiKeyRecord[]>(`/institutions/${institutionId}/api-keys`),
  createApiKey: (institutionId: string, name: string, role = "institution_ops") =>
    request<ApiKeyRecord & { api_key: string; hmac_secret?: string }>(`/institutions/${institutionId}/api-keys`, {
      method: "POST",
      body: JSON.stringify({ name, role }),
    }),

  getAuthContext: () => request<AuthContext>("/ops/auth/me"),
  updateOwnProfile: (body: OpsUserProfilePatch) =>
    request<AuthContext>("/ops/auth/me", { method: "PATCH", body: JSON.stringify(body) }),
  getOpsMetrics: () => request<OpsMetrics>("/ops/metrics"),
  logUiAudit: (body: { action: string; label: string; path: string }) =>
    request<void>("/ops/audit/ui", { method: "POST", body: JSON.stringify(body) }).catch(() => undefined),

  login: (email: string, password: string) =>
    request<LoginResponse>("/ops/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  verifyMfa: (mfa_token: string, code: string) =>
    request<LoginResponse>("/ops/auth/mfa", {
      method: "POST",
      body: JSON.stringify({ mfa_token, code }),
    }),

  enrollMfa: () =>
    request<{ secret: string; otpauth_url: string; email: string; method?: string }>("/ops/auth/mfa/enroll", {
      method: "POST",
    }),

  confirmMfa: (code: string) =>
    request<LoginResponse>("/ops/auth/mfa/confirm", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),

  sendEmailMfa: () =>
    request<{ email: string; smtp_sent: boolean; mail_path: string; dev_code?: string | null; method: string }>(
      "/ops/auth/mfa/email/send",
      { method: "POST" },
    ),

  confirmEmailMfa: (code: string) =>
    request<LoginResponse>("/ops/auth/mfa/email/confirm", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),

  enableEmailMfa: () => request<LoginResponse>("/ops/auth/mfa/email/enable", { method: "POST" }),

  enableTotpMfa: () => request<LoginResponse>("/ops/auth/mfa/enable", { method: "POST" }),

  disableMfa: (password: string) =>
    request<LoginResponse>("/ops/auth/mfa/disable", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),

  listApprovals: (status = "pending") =>
    request<PendingApproval[]>(`/ops/approvals${status ? `?status=${status}` : ""}`),
  approvePending: (id: string, note?: string) =>
    request<PendingApproval>(`/ops/approvals/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  rejectPending: (id: string, note?: string) =>
    request<PendingApproval>(`/ops/approvals/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  listBillingInvoices: (institutionId?: string) =>
    request<BillingInvoice[]>(
      `/ops/billing/invoices${institutionId ? `?institution_id=${institutionId}` : ""}`,
    ),
  generateInvoice: (body: { institution_id: string; period_start: string; period_end: string; note?: string }) =>
    request<BillingInvoice>("/ops/billing/invoices", { method: "POST", body: JSON.stringify(body) }),
  payInvoice: (id: string) => request<BillingInvoice>(`/ops/billing/invoices/${id}/pay`, { method: "POST" }),
  scanReconciliation: (institutionId?: string) =>
    request<{ scanned: boolean; created_or_updated: number }>(
      `/ops/reconciliation/scan${institutionId ? `?institution_id=${institutionId}` : ""}`,
      { method: "POST" },
    ),
  listReconciliation: (status?: string) =>
    request<ReconciliationRow[]>(`/ops/reconciliation${status ? `?status=${status}` : ""}`),
  resolveReconciliation: (id: string, status: string, note?: string) =>
    request<ReconciliationRow>(`/ops/reconciliation/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify({ status, note }),
    }),
  retryKenyaCase: (applicationId: string) =>
    request<{ application_id: string; reset_legs: number; message: string }>(
      `/kenya/ops/cases/${applicationId}/retry`,
      { method: "POST" },
    ),

  changePassword: (current_password: string, new_password: string) =>
    request<LoginResponse>("/ops/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    }),

  listOpsUsers: () => request<OpsUserRecord[]>("/ops/auth/users"),
  getOpsUser: (userId: string) => request<OpsUserRecord>(`/ops/auth/users/${userId}`),

  createOpsUser: (body: {
    email: string;
    full_name: string;
    role: string;
    institution_id?: string | null;
    agent_dealer_id?: string | null;
    approval_limit_amount?: string | null;
    temporary_password?: string;
  }) =>
    request<
      OpsUserRecord & {
        temporary_password?: string | null;
        smtp_sent?: boolean;
        mail_path?: string | null;
        invite_message?: string;
      }
    >("/ops/auth/users", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  updateOpsUser: (userId: string, body: OpsUserAdminPatch) =>
    request<OpsUserRecord>(`/ops/auth/users/${userId}`, { method: "PATCH", body: JSON.stringify(body) }),

  resetOpsUserPassword: (userId: string, temporary_password?: string) =>
    request<{
      id: string;
      email: string;
      full_name?: string;
      role?: string;
      temporary_password?: string | null;
      must_change_password: boolean;
      smtp_sent?: boolean;
      mail_path?: string | null;
      invite_message?: string;
    }>(`/ops/auth/users/${userId}/reset-password`, {
      method: "POST",
      body: JSON.stringify(temporary_password ? { temporary_password } : {}),
    }),

  deleteOpsUser: (userId: string) => request<void>(`/ops/auth/users/${userId}`, { method: "DELETE" }),

  listKenyaCustomers: (institutionId?: string) =>
    request<KenyaCustomer[]>(`/kenya/customers${institutionId ? `?institution_id=${institutionId}` : ""}`),

  getKenyaCustomer: (customerId: string) => request<KenyaCustomer>(`/kenya/customers/${customerId}`),

  registerKenyaCustomer: (body: {
    phone: string;
    full_name: string;
    wallet_number: string;
    email?: string;
    institution_id?: string;
    national_id?: string;
    kyc_status?: string;
    aml_status?: string;
    credit_score?: number;
    wallet_provider?: string;
  }) => request<KenyaCustomer>("/kenya/customers", { method: "POST", body: JSON.stringify(body) }),

  updateKenyaCustomer: (
    customerId: string,
    body: {
      full_name?: string;
      email?: string;
      national_id?: string;
      kyc_status?: string;
      aml_status?: string;
      credit_score?: number;
      wallet_number?: string;
    },
  ) => request<KenyaCustomer>(`/kenya/customers/${customerId}`, { method: "PATCH", body: JSON.stringify(body) }),

  deleteKenyaCustomer: (customerId: string) =>
    request<void>(`/kenya/customers/${customerId}`, { method: "DELETE" }),

  listMobileAccounts: (approvalStatus?: string) =>
    request<
      {
        id: string;
        email: string;
        full_name: string;
        email_verified: boolean;
        approval_status: string;
        phone: string | null;
        credit_limit: string | null;
        can_borrow: boolean;
        approval_message: string | null;
        institution_id: string | null;
        institution_name: string | null;
        created_at: string | null;
      }[]
    >(`/ops/mobile/accounts${approvalStatus ? `?approval_status=${encodeURIComponent(approvalStatus)}` : ""}`),

  approveMobileAccount: (
    accountId: string,
    body: { phone: string; credit_limit: string; institution_id?: string; credit_score?: number },
  ) => request(`/ops/mobile/accounts/${accountId}/approve`, { method: "POST", body: JSON.stringify(body) }),

  rejectMobileAccount: (accountId: string, reason: string) =>
    request(`/ops/mobile/accounts/${accountId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  listMobileInvites: () =>
    request<
      {
        id: string;
        email: string;
        phone: string | null;
        full_name: string | null;
        code: string;
        credit_limit: string;
        activate_on_claim: boolean;
        status: string;
        institution_name: string | null;
      }[]
    >("/ops/mobile/invites"),

  createMobileInvite: (body: {
    institution_id: string;
    email: string;
    phone?: string;
    full_name?: string;
    credit_limit: string;
    activate_on_claim?: boolean;
    expires_days?: number;
  }) =>
    request<{
      id: string;
      email: string;
      code: string;
      credit_limit: string;
      delivery?: { dev_code?: string | null };
    }>("/ops/mobile/invites", { method: "POST", body: JSON.stringify(body) }),

  recordKenyaEligibilityDecision: (
    applicationId: string,
    body: {
      passed: boolean;
      kyc_status?: string;
      aml_status?: string;
      credit_score?: number;
      decision_ref?: string;
      notes?: string;
    },
  ) => request(`/kenya/applications/${applicationId}/eligibility/decision`, { method: "POST", body: JSON.stringify(body) }),

  createKenyaApplication: (body: {
    customer_id: string;
    amount_requested: string;
    term_months: number;
    purpose: string;
  }) => request<Application>("/kenya/applications", { method: "POST", body: JSON.stringify(body) }),

  runKenyaEligibility: (id: string) =>
    request(`/kenya/applications/${id}/eligibility`, { method: "POST" }),

  kenyaOffer: (id: string, body?: { profit_rate_pct?: number; cost_price?: string }) =>
    request(`/kenya/applications/${id}/offer`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),

  kenyaResendOfferEmail: (id: string) =>
    request<{
      status: string;
      email: string | null;
      journey_url: string;
      smtp_sent: boolean;
      mail_path: string | null;
      reason: string | null;
    }>(`/kenya/applications/${id}/offer-email`, { method: "POST" }),

  kenyaAccept: (id: string) => request(`/kenya/applications/${id}/accept`, { method: "POST" }),

  kenyaMurabaha: (id: string) =>
    request(`/kenya/applications/${id}/murabaha`, { method: "POST" }),

  kenyaMurabahaSign: (id: string, signature_ref = "portal-demo-sign") =>
    request(`/kenya/applications/${id}/murabaha/sign`, {
      method: "POST",
      body: JSON.stringify({ signature_ref }),
    }),

  runFullKenyaFlow: (id: string) => request(`/kenya/applications/${id}/run-full-flow`, { method: "POST" }),

  getKenyaFlowStatus: (id: string) => request<KenyaFlowStatus>(`/kenya/applications/${id}/status`),

  getKenyaOffer: (id: string) => request<OfferSummary>(`/kenya/applications/${id}/offer`),

  kenyaWakala: (id: string, consent_ref: string, notes?: string) =>
    request(`/kenya/applications/${id}/wakala`, {
      method: "POST",
      body: JSON.stringify({ consent_ref, notes }),
    }),

  kenyaCompleteSettlement: (id: string) =>
    request(`/kenya/applications/${id}/complete-settlement`, { method: "POST" }),

  kenyaPossessionConfirm: (transactionId: string, batch_id?: string, mno_receipt_id?: string) =>
    request<Transaction>(`/kenya/transactions/${transactionId}/possession`, {
      method: "POST",
      body: JSON.stringify({ batch_id, mno_receipt_id }),
    }),

  listKenyaRepayments: (applicationId: string) =>
    request<RepaymentInstallment[]>(`/kenya/applications/${applicationId}/repayments`),

  collectKenyaRepayment: (installmentId: string) =>
    request<RepaymentInstallment>(`/kenya/repayments/${installmentId}/collect`, { method: "POST" }),

  listKenyaOpsCases: (queue?: string) => {
    const q = queue && queue !== "all" ? `?queue=${queue}` : "";
    return request<KenyaOpsCase[]>(`/kenya/ops/cases${q}`);
  },

  getKenyaOpsCase: (applicationId: string) =>
    request<KenyaOpsCase>(`/kenya/ops/cases/${applicationId}`),

  listKenyaOpsRepayments: () => request<RepaymentBoardItem[]>("/kenya/ops/repayments"),

  listKenyaBrokers: () => request<BrokerInfo[]>("/kenya/ops/brokers"),

  getKenyaShariahAudit: (applicationId: string) =>
    request<ShariahAuditEntry[]>(`/kenya/applications/${applicationId}/shariah-audit`),

  verifyKenyaShariah: (applicationId: string) =>
    request<ShariahIntegrity>(`/kenya/applications/${applicationId}/shariah-audit/verify`),

  verifyShariahChain: (institutionId?: string) =>
    request<Record<string, unknown>>(
      `/kenya/shariah-audit/verify-chain${institutionId ? `?institution_id=${institutionId}` : ""}`,
    ),

  exportShariahAuditUrl: (params: { format?: "json" | "csv"; application_id?: string; institution_id?: string }) => {
    const q = new URLSearchParams();
    q.set("format", params.format || "csv");
    if (params.application_id) q.set("application_id", params.application_id);
    if (params.institution_id) q.set("institution_id", params.institution_id);
    return `${API_BASE}/kenya/shariah-audit/export?${q.toString()}`;
  },

  downloadShariahExport: async (params: {
    format?: "json" | "csv";
    application_id?: string;
    institution_id?: string;
  }) => {
    const url = api.exportShariahAuditUrl(params);
    const response = await fetch(url, { headers: authHeaders() });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Export failed: ${response.status}`);
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = params.format === "json" ? "shariah_audit.json" : "shariah_audit.csv";
    a.click();
    URL.revokeObjectURL(objectUrl);
  },

  kenyaPurchase: (transactionId: string) =>
    request<Transaction>(`/kenya/transactions/${transactionId}/purchase`, { method: "POST" }),

  kenyaPossession: (transactionId: string) =>
    request<Transaction>(`/kenya/transactions/${transactionId}/possession`, { method: "POST" }),

  kenyaTransfer: (transactionId: string) =>
    request<Transaction>(`/kenya/transactions/${transactionId}/transfer`, { method: "POST" }),

  kenyaLiquidate: (transactionId: string) =>
    request<Transaction>(`/kenya/transactions/${transactionId}/liquidate`, { method: "POST" }),

  startKenyaTransaction: (applicationId: string) =>
    request<Transaction>("/kenya/transactions", {
      method: "POST",
      body: JSON.stringify({ application_id: applicationId }),
    }),

  runKenyaFullFlow: (applicationId: string) =>
    request<KenyaFlowStatus>(`/kenya/applications/${applicationId}/run-full-flow`, { method: "POST" }),

  getInstitutionIntegration: (institutionId: string) =>
    requestOptional<InstitutionIntegration>(`/institutions/${institutionId}/integrations`),

  putInstitutionIntegration: (institutionId: string, body: InstitutionIntegrationPayload) =>
    request<InstitutionIntegration>(`/institutions/${institutionId}/integrations`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  getIntegrationStatus: (institutionId: string) =>
    request<IntegrationStatus>(`/institutions/${institutionId}/integrations/status`),

  getCallbackUrls: (institutionId: string) =>
    request<Record<string, string>>(`/institutions/${institutionId}/integrations/callback-urls`),

  // ── Agent Dealer ──────────────────────────────────────────────────────────
  getAgentDealerSummary: (institutionId?: string) =>
    request<AgentDealerSummary>(`/kenya/agent-dealers/summary${institutionId ? `?institution_id=${institutionId}` : ""}`),

  listAgentDealers: (institutionId?: string) =>
    request<AgentDealer[]>(`/kenya/agent-dealers${institutionId ? `?institution_id=${institutionId}` : ""}`),

  createAgentDealer: (body: {
    business_name: string;
    mpesa_number: string;
    mpesa_till_number?: string;
    code?: string;
    institution_id?: string;
    contact_name?: string;
    contact_phone?: string;
  }) =>
    request<AgentDealer>("/kenya/agent-dealers", { method: "POST", body: JSON.stringify(body) }),

  getMyAgentDealer: () => request<AgentDealer>("/kenya/agent-dealers/me"),

  getAgentDealer: (dealerId: string) =>
    request<AgentDealer>(`/kenya/agent-dealers/${dealerId}`),

  topupAgentDealer: (dealerId: string, amount: number, reference?: string, note?: string) =>
    request<{ float_balance: number; message: string }>(`/kenya/agent-dealers/${dealerId}/topup`, {
      method: "POST",
      body: JSON.stringify({ amount, reference, note }),
    }),

  updateAgentDealer: (
    dealerId: string,
    body: {
      active?: boolean;
      business_name?: string;
      mpesa_number?: string;
      mpesa_till_number?: string | null;
      contact_name?: string | null;
      contact_phone?: string | null;
    },
  ) =>
    request<AgentDealer & { message: string }>(`/kenya/agent-dealers/${dealerId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  agentDealerPurchase: (transactionId: string) =>
    request<{ transaction_id: string; status: string; message: string }>(
      `/kenya/transactions/${transactionId}/agent-dealer-purchase`,
      { method: "POST" },
    ),

  // ── Customer Journey ─────────────────────────────────────────────────────
  getCustomerApplication: (applicationRef: string, phone?: string) =>
    request<{
      application_id: string;
      application_ref: string;
      customer_name: string | null;
      track: "malaysia" | "kenya";
      status: string;
      amount: string;
      murabaha_total: string | null;
      institution_name: string | null;
      overall_progress: number;
      total_steps: number;
    }>(`/customer/applications/${applicationRef}${phone ? `?phone=${encodeURIComponent(phone)}` : ""}`),

  getCustomerJourney: (applicationRef: string, phone?: string) =>
    request<CustomerJourney>(
      `/customer/applications/${applicationRef}/journey${phone ? `?phone=${encodeURIComponent(phone)}` : ""}`,
    ),

  customerAcceptOffer: (applicationRef: string, phone?: string) =>
    request<CustomerJourney>(
      `/customer/applications/${applicationRef}/accept${phone ? `?phone=${encodeURIComponent(phone)}` : ""}`,
      { method: "POST" },
    ),

  customerSignContract: (applicationRef: string, phone?: string) =>
    request<CustomerJourney>(
      `/customer/applications/${applicationRef}/sign${phone ? `?phone=${encodeURIComponent(phone)}` : ""}`,
      { method: "POST" },
    ),

  getCustomerCertificate: (applicationRef: string) =>
    request<{ application_ref: string; certificate: JourneyCertificate; downloadable: boolean }>(
      `/customer/applications/${applicationRef}/certificate`,
    ),

  getCustomerCertificates: (applicationRef: string) =>
    request<CustomerJourney["certificates"]>(`/customer/applications/${applicationRef}/certificates`),

  tradeDocumentUrl: (applicationRef: string, kind: "purchase_order" | "supplier_invoice" | "delivery_order") =>
    `${API_BASE}/customer/applications/${encodeURIComponent(applicationRef)}/trade-documents/${kind}`,

  downloadTradeDocument: async (
    applicationRef: string,
    kind: "purchase_order" | "supplier_invoice" | "delivery_order",
  ) => {
    const response = await fetch(
      `${API_BASE}/customer/applications/${encodeURIComponent(applicationRef)}/trade-documents/${kind}`,
      { headers: authHeaders() },
    );
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || "This document is not ready to download.");
    }
    const blob = await response.blob();
    const header = response.headers.get("content-disposition") || "";
    const match = header.match(/filename="([^"]+)"/);
    const filename = match?.[1] || `${kind}.html`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },

  lookupCustomerByPhone: (phone: string) =>
    request<{ application_id: string; customer_ref: string; amount: string; status: string; institution: string | null; created_at: string | null }[]>(
      `/customer/applications?phone=${encodeURIComponent(phone)}`,
    ),

  createSedaniaFinancing: (body: SedaniaFinancingRequest) =>
    request<SedaniaFinancing>("/sedania/financing", { method: "POST", body: JSON.stringify(body) }),

  listSedaniaFinancing: (institutionId?: string) =>
    request<SedaniaFinancing[]>(
      `/sedania/financing${institutionId ? `?institution_id=${encodeURIComponent(institutionId)}` : ""}`,
    ),

  getSedaniaFinancing: (executionId: string) =>
    request<SedaniaFinancing>(`/sedania/financing/${executionId}`),

  listSedaniaDocuments: (executionId: string) =>
    request<SedaniaDocumentIndex[]>(`/sedania/financing/${executionId}/documents`),

  sedaniaDocumentUrl: (executionId: string, kind: string) =>
    `${API_BASE}/sedania/financing/${encodeURIComponent(executionId)}/documents/${encodeURIComponent(kind)}`,

  downloadSedaniaDocument: async (executionId: string, kind: string) => {
    const response = await fetch(
      `${API_BASE}/sedania/financing/${encodeURIComponent(executionId)}/documents/${encodeURIComponent(kind)}`,
      { headers: authHeaders() },
    );
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error((body as { detail?: string }).detail || "This document is not ready.");
    }
    const blob = await response.blob();
    const header = response.headers.get("content-disposition") || "";
    const match = header.match(/filename="([^"]+)"/);
    const filename = match?.[1] || `${kind}.html`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },

  settleSedaniaFinancing: (executionId: string) =>
    request<SedaniaFinancing>(`/sedania/financing/${executionId}/settle`, { method: "POST" }),

  arrangeSedaniaPhysicalDelivery: (executionId: string, markSettled = true) =>
    request<SedaniaFinancing>(`/sedania/financing/${executionId}/physical-delivery`, {
      method: "POST",
      body: JSON.stringify({ mark_settled: markSettled }),
    }),
};

export type HealthPayload = {
  status?: string;
  auth_enabled?: boolean;
  deployment_mode?: string;
  enabled_products?: string[];
  brand_name?: string;
  uptime_seconds?: number;
  uptime_pct?: number;
};

export async function fetchHealth(): Promise<HealthPayload> {
  const base = import.meta.env.VITE_API_URL?.replace("/api/v1", "") || "";
  const response = await fetch(`${base}/health`);
  return response.json();
}
