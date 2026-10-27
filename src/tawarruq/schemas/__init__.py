from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from tawarruq.schemas.common import ErrorResponse

class InstitutionCreate(BaseModel):
    name: str = Field(..., description='Institution display name', examples=['Demo Islamic Bank'])
    code: str = Field(..., description='Unique institution code', examples=['DIB001'])
    bsas_mode: str = Field('manual_bridge', description='Default BSAS backend: mock | manual_bridge | live', examples=['mock'])
    approval_limit_amount: Decimal | None = Field(
        None,
        description='Bank or SACCO cap for queued deals. Null means no institution cap.',
        examples=['500000.00'],
    )
    approval_steps: str = Field(
        'murabaha,liquidation,disbursement',
        description='Comma-separated maker-checker steps: murabaha, liquidation, disbursement. Remove a step to run it immediately.',
    )

class InstitutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description='UUID')
    name: str
    code: str
    bsas_mode: str = Field(..., description='Default BSAS integration mode for new transactions')
    active: bool = True
    lifecycle_status: str = 'active'
    approval_steps: str = 'murabaha,liquidation,disbursement'
    approval_limit_amount: Decimal | None = None
    billing_fee_bps: int = 25
    created_at: datetime


class InstitutionOnboardingWrite(BaseModel):
    legal_registered_name: str | None = None
    code: str | None = None
    trading_name: str | None = None
    institution_type: str | None = None
    other_institution_type: str | None = None
    registration_number: str | None = None
    incorporation_date: str | None = None
    incorporation_country: str | None = None
    kra_pin: str | None = None
    registered_address_line1: str | None = None
    registered_address_line2: str | None = None
    registered_county: str | None = None
    registered_postal_code: str | None = None
    physical_address: str | None = None
    website_url: str | None = None
    support_email: str | None = None
    main_telephone: str | None = None
    business_description: str | None = None
    primary_regulator: str | None = None
    regulator_other_name: str | None = None
    licence_number: str | None = None
    licence_issue_date: str | None = None
    licence_expiry_date: str | None = None
    licence_status: str | None = None
    regulator_register_url: str | None = None
    ownership_structure_summary: str | None = None
    parent_company_name: str | None = None
    related_entities: list | None = None
    owners_and_shareholders: list | None = None
    ownership_percentage: Decimal | str | None = None
    ubo_details: list | None = None
    directors_board_members: list | None = None
    ceo_managing_director_name: str | None = None
    senior_management_details: list | None = None
    pep_screening_status: str | None = None
    sanctions_screening_status: str | None = None
    adverse_media_screening_status: str | None = None
    primary_contact_full_name: str | None = None
    primary_contact_title: str | None = None
    primary_contact_work_email: str | None = None
    primary_contact_phone: str | None = None
    compliance_officer_name: str | None = None
    compliance_officer_email: str | None = None
    authorized_signatories: list | None = None
    representative_id_type: str | None = None
    representative_id_number: str | None = None
    representative_identity_verification_status: str | None = None
    authority_to_act_document_id: str | None = None
    settlement_bank_name: str | None = None
    settlement_account_name: str | None = None
    settlement_branch: str | None = None
    settlement_account_number: str | None = None
    settlement_currency: str | None = None
    settlement_account_verification_status: str | None = None
    settlement_account_evidence_document_id: str | None = None
    expected_monthly_transaction_count: int | None = None
    expected_monthly_transaction_value: Decimal | str | None = None
    typical_transaction_amount: Decimal | str | None = None
    maximum_transaction_amount: Decimal | str | None = None
    target_go_live_date: str | None = None
    commercial_agreement_status: str | None = None
    pricing_schedule_reference: str | None = None
    dispute_contact_email: str | None = None


class InstitutionOnboardingRead(InstitutionRead):
    trading_name: str | None = None
    institution_type: str | None = None
    other_institution_type: str | None = None
    registration_number: str | None = None
    incorporation_date: str | None = None
    incorporation_country: str | None = None
    kra_pin: str | None = None
    registered_address_line1: str | None = None
    registered_address_line2: str | None = None
    registered_county: str | None = None
    registered_postal_code: str | None = None
    physical_address: str | None = None
    website_url: str | None = None
    support_email: str | None = None
    main_telephone: str | None = None
    business_description: str | None = None
    primary_regulator: str | None = None
    regulator_other_name: str | None = None
    licence_number: str | None = None
    licence_issue_date: str | None = None
    licence_expiry_date: str | None = None
    licence_status: str | None = None
    regulator_register_url: str | None = None
    ownership_structure_summary: str | None = None
    parent_company_name: str | None = None
    related_entities: list | None = None
    owners_and_shareholders: list | None = None
    ownership_percentage: Decimal | None = None
    ubo_details: list | None = None
    directors_board_members: list | None = None
    ceo_managing_director_name: str | None = None
    senior_management_details: list | None = None
    pep_screening_status: str | None = None
    sanctions_screening_status: str | None = None
    adverse_media_screening_status: str | None = None
    primary_contact_full_name: str | None = None
    primary_contact_title: str | None = None
    primary_contact_work_email: str | None = None
    primary_contact_phone: str | None = None
    compliance_officer_name: str | None = None
    compliance_officer_email: str | None = None
    authorized_signatories: list | None = None
    representative_id_type: str | None = None
    representative_id_number: str | None = None
    representative_identity_verification_status: str | None = None
    authority_to_act_document_id: str | None = None
    settlement_bank_name: str | None = None
    settlement_account_name: str | None = None
    settlement_branch: str | None = None
    settlement_account_number: str | None = None
    settlement_currency: str | None = None
    settlement_account_verification_status: str | None = None
    settlement_account_evidence_document_id: str | None = None
    expected_monthly_transaction_count: int | None = None
    expected_monthly_transaction_value: Decimal | None = None
    typical_transaction_amount: Decimal | None = None
    maximum_transaction_amount: Decimal | None = None
    target_go_live_date: str | None = None
    commercial_agreement_status: str | None = None
    pricing_schedule_reference: str | None = None
    dispute_contact_email: str | None = None
    application_status: str | None = None
    submission_date: datetime | None = None
    approval_decision: str | None = None
    approval_reason: str | None = None
    activation_date: str | None = None


class InstitutionOnboardingDecision(BaseModel):
    decision: str = Field(..., description='approve | return | reject')
    reason: str | None = None


class InstitutionLifecycleUpdate(BaseModel):
    lifecycle_status: str = Field(..., description='active | dormant | deactivated')


class InstitutionSummaryRead(BaseModel):
    total: int
    by_type: dict[str, int]
    by_regulator: dict[str, int]
    by_month: dict[str, int]
    by_lifecycle: dict[str, int]
    active: int
    dormant: int
    deactivated: int

class ApplicationCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={'examples': [{'amount_requested': '150000.00', 'term_months': 12, 'purpose': 'Working capital for inventory purchase'}]})

    institution_id: str | None = Field(None, description='Institution UUID (optional if institution_code provided)')
    institution_code: str | None = Field(None, description='Institution code, e.g. DEFAULT', examples=['DEFAULT'])
    customer_ref: str | None = Field(None, description='Optional. Auto-generated as CUST-{INST_CODE}-{YYYY}-{NNNN} if omitted.', examples=['CUST-DEFAULT-2026-0001'])
    customer_id: str | None = Field(None, description='Onboarded customer UUID. Links the deal to the same customer record used on Customers.')
    customer_name: str | None = Field(None, description='Legal end-customer name for Bursa BSAS desk packets. Filled from the linked customer when customer_id is set.', examples=['Marian Abubakar'])
    currency: str = Field('KES', description='Currency for bid / profit / murabaha amounts on BSAS desk packets', examples=['KES', 'MYR'])
    amount_requested: Decimal = Field(..., description='Financing amount', examples=['150000.00'])
    term_months: int = Field(..., description='Financing term in months', examples=[12])
    purpose: str = Field(..., description='Shariah-compliant purpose of financing', examples=['Working capital'])

class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    institution_id: str
    institution_name: str | None = None
    customer_id: str | None = None
    customer_ref: str
    customer_name: str | None = None
    currency: str = 'KES'
    amount_requested: Decimal
    term_months: int
    purpose: str
    status: str = Field(..., description='draft | offer_pending | offer_accepted | in_progress | completed | failed | escalated')
    current_phase: str | None = None
    wad_accepted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

class OfferCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={'examples': [{'profit_rate_pct': '5.0'}, {'cost_price': '150000.00', 'profit_rate_pct': '4.5'}]})

    cost_price: Decimal | None = Field(None, description='Commodity cost price. Defaults to application amount_requested if omitted.', examples=['150000.00'])
    profit_rate_pct: Decimal = Field(Decimal('5.0'), description='Profit rate as percentage of cost price', examples=['5.0'])

class OfferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    cost_price: Decimal = Field(..., description='Commodity purchase cost')
    profit_amount: Decimal = Field(..., description='Institution profit (markup)')
    total_payable: Decimal = Field(..., description='cost_price + profit_amount')
    accepted_at: datetime | None = Field(None, description='Set when customer accepts the offer')
    created_at: datetime

class TransactionCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={'examples': [{'application_id': '00000000-0000-0000-0000-000000000000', 'commodity_code': 'PALM_OIL', 'mode': 'mock'}]})

    application_id: str = Field(..., description='UUID of an offer_accepted application')
    commodity_code: str = Field('PALM_OIL', description='BSAS commodity code (PALM_OIL maps to ACPO)', examples=['PALM_OIL', 'ACPO'])
    mode: str | None = Field(None, description='BSAS backend override: mock | manual_bridge | live. Defaults to institution bsas_mode.', examples=['mock'])

class CertificateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    certificate_number: str = Field(..., description='BSAS e-certificate number, e.g. CPO28AUG26-0009491-000')
    issuer: str = Field(..., description='Typically Bursa Malaysia Islamic Services Sdn.Bhd.')
    seller: str | None = None
    buyer: str | None = None
    bid_no: str | None = None
    selling_time: str | None = None
    selling_date: str | None = None
    value_date: str | None = None
    product_code: str | None = None
    product_description: str | None = None
    unit: str | None = None
    volume: str | None = None
    currency: str | None = None
    price: str | None = None
    price_myr_equivalent: str | None = None
    value_amount: str | None = None
    transaction_type: str | None = None
    pdf_path: str | None = None
    pdf_filename: str | None = None
    received_at: datetime

class LegRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    leg_number: str = Field(..., description='1=purchase, 2=transfer, 3=sale')
    status: str = Field(..., description='pending | in_progress | awaiting_confirmation | confirmed | failed')
    external_ref: str | None = Field(None, description='BSAS or manual-bridge reference')
    error_message: str | None = None
    bsas_fee: Decimal | None = Field(None, description='BSAS fee applied on Leg 1 purchase')
    executed_at: datetime | None = None
    certificate: CertificateRead | None = None

class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    institution_id: str
    commodity_code: str
    mode: str = Field(..., description='BSAS backend used for this transaction')
    status: str = Field(..., description='created | executing | awaiting_manual | completed | failed | escalated')
    created_at: datetime
    updated_at: datetime
    legs: list[LegRead] = Field(default_factory=list, description='All 3 legs with certificates')

class DisbursementCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={'examples': [{'application_id': '00000000-0000-0000-0000-000000000000', 'transaction_id': '00000000-0000-0000-0000-000000000000'}]})

    application_id: str
    transaction_id: str = Field(..., description='Must be a completed transaction')

class HealthRead(BaseModel):
    status: str = Field(..., examples=['ok'])
    version: str
    amanah_write_enabled: bool = Field(..., description='Whether Amanah can execute legs automatically')
    kenya_integration_mode: str = Field(..., description='live | mock')
    mpesa_configured: bool = Field(False, description='Daraja B2C/STK credentials present')
    mno_safaricom_configured: bool = Field(False, description='Safaricom airtime dealer API configured')
    airtel_money_configured: bool = Field(False, description='Airtel OAuth + disbursement API configured')
    broker_configured: bool = Field(False, description='Independent broker liquidation API configured')
    shariah_audit_mirror: bool = Field(False, description='SHARIAH_AUDIT_SERVICE_URL is set')
    auth_enabled: bool = Field(False, description='API key authentication required on protected routes')
    database_ok: bool = Field(True, description='Database connectivity check passed')
    malaysia_commodity_desk: str = Field('bsas', description='bsas | eiger')
    bsas_live_configured: bool = Field(False, description='BSAS_LIVE_API_URL and key are set')
    eiger_configured: bool = Field(False, description='EIGER_API_URL and key are set')
    manual_bridge_ready: bool = Field(True, description='Manual-bridge inbox directory is writable')
    sedania_mode: str = Field('mock', description='mock | live')
    sedania_configured: bool = Field(False, description='SEDANIA_API_URL and key are set')
    deployment_mode: str = Field('managed', description='managed | onprem')
    enabled_products: list[str] = Field(default_factory=list, description='Active product modules')
    brand_name: str = Field('Buruuj Fintech', description='White-label operator name')
    uptime_seconds: int = Field(0, description='Seconds since this process started')
    uptime_pct: float = Field(100, description='100 when status is ok, otherwise 0')

class MalaysiaFlowStatusRead(BaseModel):
    application_id: str
    transaction_id: str
    status: str
    legs_confirmed: int
    disbursement_id: str | None = None
    certificate_number: str | None = None

class AuthContextRead(BaseModel):
    auth_enabled: bool
    authenticated: bool
    role: str | None = None
    institution_id: str | None = None
    institution_name: str | None = None
    is_platform_admin: bool = False
    permissions: list = Field(default_factory=list)
    email: str | None = None
    full_name: str | None = None
    user_id: str | None = None
    agent_dealer_id: str | None = None
    must_change_password: bool = False
    auth_method: str | None = Field(None, description='session | api_key | none')
    mfa_enabled: bool = False
    mfa_enroll_required: bool = False
    mfa_method: str | None = Field(None, description='totp | email when MFA is enabled')
    job_title: str | None = None
    department: str | None = None
    employee_number: str | None = None
    phone: str | None = None
    office: str | None = None
    deployment_mode: str = Field('managed', description='managed | onprem')
    enabled_products: list[str] = Field(default_factory=list)
    brand_name: str = Field('Buruuj Fintech')

class OpsLoginRequest(BaseModel):
    email: str = Field(..., examples=['admin@bti.local'])
    password: str = Field(..., examples=['ChangeMeNow!123'])

class OpsLoginResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    role: str
    email: str
    full_name: str
    institution_id: str | None = None
    institution_name: str | None = None
    agent_dealer_id: str | None = None
    must_change_password: bool
    permissions: list = Field(default_factory=list)
    mfa_required: bool = False
    mfa_token: str | None = None
    mfa_enroll_required: bool = False
    mfa_enabled: bool = False
    mfa_method: str | None = Field(None, description='totp | email')
    mfa_dev_code: str | None = Field(
        None,
        description='Present only when SMTP is off (local demo). Never set in production with SMTP.',
    )

class OpsChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(...)

class OpsUserCreate(BaseModel):
    email: str
    full_name: str
    role: str = Field(
        'institution_admin',
        description=(
            'Use the API value. Super Admin may invite: Super Admin (platform_admin), BTI Ops (bti_ops), '
            'BTI Finance (bti_finance), FI Admin (institution_admin), Shariah / Audit (shariah_officer), '
            'Reconciliation (reconciler). Super Admin cannot invite FI Operations or FI Approver. '
            'FI Admin may invite: FI Admin, FI Operations, FI Approver, Shariah / Audit, Reconciliation.'
        ),
    )
    institution_id: str | None = None
    agent_dealer_id: str | None = Field(None, description='Required when role is agent_dealer. Binds this login to one float pool.')
    approval_limit_amount: Decimal | None = Field(None, description='Max amount this approver may authorize. Null inherits the institution limit.')
    temporary_password: str | None = Field(
        None,
        description='Optional; auto-generated if omitted. Emailed via SMTP when configured.',
    )

class OpsUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    role: str
    institution_id: str | None
    agent_dealer_id: str | None = None
    must_change_password: bool
    active: bool
    approval_limit_amount: Decimal | None = None
    mfa_enabled: bool = False
    job_title: str | None = None
    department: str | None = None
    employee_number: str | None = None
    phone: str | None = None
    office: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

class OpsUserUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    role: str | None = Field(
        None,
        description=(
            'Same invite rules as create. Super Admin cannot assign institution_ops or fi_approver. '
            'FI Admin cannot assign BTI-internal roles.'
        ),
    )
    institution_id: str | None = None
    agent_dealer_id: str | None = None
    active: bool | None = None
    approval_limit_amount: Decimal | None = None
    job_title: str | None = None
    department: str | None = None
    employee_number: str | None = None
    phone: str | None = None
    office: str | None = None


class OpsProfileUpdate(BaseModel):
    """Self-service profile / HR fields editable on Settings."""

    full_name: str | None = None
    job_title: str | None = None
    department: str | None = None
    employee_number: str | None = None
    phone: str | None = None
    office: str | None = None

class OpsUserCreatedRead(OpsUserRead):
    temporary_password: str | None = Field(
        None,
        description='Present only when SMTP did not deliver; share securely. Null when emailed.',
    )
    smtp_sent: bool = False
    mail_path: str | None = None
    invite_message: str = ''

class OpsUserPasswordResetRequest(BaseModel):
    temporary_password: str | None = Field(None, description='Optional admin-chosen password. Leave empty to auto-generate.')

class OpsUserPasswordResetRead(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    role: str | None = None
    temporary_password: str | None = Field(
        None,
        description='Present only when SMTP did not deliver; share securely. Null when emailed.',
    )
    must_change_password: bool = True
    smtp_sent: bool = False
    mail_path: str | None = None
    invite_message: str = ''

class OpsMetricsRead(BaseModel):
    timestamp: str
    scoped_institution_id: str | None = None
    applications_total: int
    applications_by_status: dict
    transactions_total: int
    transactions_by_status: dict
    manual_bridge_pending: int
    institutions_total: int
    active_webhooks: int
    active_api_keys: int
    audit_events_today: int
    amanah_enabled: bool
    amanah_write_enabled: bool
    auth_enabled: bool
    kenya_integration_mode: str
    http_requests_total: int
    http_errors_total: int
    http_latency_ms_avg: float
    http_by_status: dict = Field(default_factory=dict)
    http_top_paths: dict = Field(default_factory=dict)
    applications_open: int = 0
    applications_completed: int = 0
    applications_failed: int = 0
    transactions_open: int = 0
    pending_approvals: int = 0
    book_amount_requested: float = 0
    disbursed_volume: float = 0
    completion_rate_pct: float = 0
    projected_30d_volume: float = 0
    projected_open_book: float = 0
    week_disbursed_volume: float = 0

class InstitutionUpdate(BaseModel):
    name: str | None = None
    bsas_mode: str | None = Field(None, description='mock | manual_bridge | live')
    active: bool | None = Field(None, description='False suspends the tenant: writes are blocked')
    approval_steps: str | None = Field(None, description='Comma-separated: murabaha,liquidation,disbursement')
    approval_limit_amount: Decimal | None = None
    billing_fee_bps: int | None = Field(None, description='Platform fee in basis points of disbursed volume')

class WebhookCreate(BaseModel):
    institution_id: str
    url: str = Field(..., examples=['https://bank.example.com/webhooks/tawarruq'])
    events: list = Field(['*'], examples=[['transaction.completed', 'disbursement.created']])

class WebhookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    institution_id: str
    url: str
    events: str
    active: bool
    created_at: datetime

class WebhookCreatedRead(WebhookRead):
    secret: str = Field(..., description='Signing secret shown once at creation')

class ApiKeyCreate(BaseModel):
    name: str = Field(..., examples=['Production integration'])
    role: str = Field(
        'api_client',
        description='Super Admin only. Prefer api_client for machine clients. Also: institution_ops | institution_admin | platform_admin | bti_ops | shariah_officer | read_only',
        examples=['api_client'],
    )

class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    institution_id: str
    name: str
    key_prefix: str
    role: str = 'institution_ops'
    active: bool
    created_at: datetime

class ApiKeyCreatedRead(ApiKeyRead):
    api_key: str = Field(..., description='Full key shown once at creation')
    hmac_secret: str | None = Field(None, description='HMAC secret shown once. Sign POST /tawarruq/execute with X-BTI-Signature.')


class ApiClientRequestRead(BaseModel):
    institution_id: str
    status: str
    message: str
    requested_at: datetime | None = None
    issued_at: datetime | None = None
    key_count: int = 0
    key_prefix: str | None = None
    api_key: str | None = None
    hmac_secret: str | None = None


class ApiClientRequestListItem(ApiClientRequestRead):
    name: str
    code: str

class CustomerSaleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    cost_price: Decimal
    profit_amount: Decimal
    total_payable: Decimal
    sold_at: datetime

class CustomerAgencyCreate(BaseModel):
    notes: str | None = Field(None, examples=['Customer appoints bank as selling agent'])

class CustomerAgencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    agent_institution_id: str
    status: str
    appointed_at: datetime
    notes: str | None

class TawarruqCertificateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    disbursement_id: str
    certificate_number: str
    issued_at: datetime

class DisbursementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    transaction_id: str
    amount: Decimal = Field(..., description='Disbursed amount (cost price from offer)')
    certificate_id: str | None
    disbursed_at: datetime
    tawarruq_certificate: TawarruqCertificateRead | None = None

class HandoffCreate(BaseModel):
    entity_type: str = Field(..., examples=['commodity_transaction'])
    entity_id: str
    reason: str
    assigned_to: str | None = None
    channel: str | None = Field(None, examples=['whatsapp', 'slack'])

class HandoffRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: str
    entity_id: str
    reason: str
    assigned_to: str | None
    channel: str | None
    created_at: datetime

class BusinessStatusRead(BaseModel):
    application_id: str
    customer_sale_recorded: bool
    customer_agency_appointed: bool
    ready_for_leg_3: bool

class PaginatedMeta(BaseModel):
    total: int
    limit: int
    offset: int

class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: str = Field(..., description='e.g. financing_application, transaction_leg, certificate')
    entity_id: str
    actor: str = Field(..., description='human | ai_worker | system')
    action: str = Field(..., description='e.g. application.created, leg.1.confirmed')
    details: str | None = None
    evidence_ref: str | None = Field(None, description='Certificate number or file path')
    timestamp: datetime
    institution_id: str | None = None
    actor_user_id: str | None = None
    group_id: str | None = None
    action_group: str | None = None
    http_method: str | None = None
    http_path: str | None = None
    http_status: int | None = None


class AuditGroupRead(BaseModel):
    group_id: str
    action_group: str
    institution_id: str | None = None
    actor_user_id: str | None = None
    actor: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    events: list[AuditEventRead] = Field(default_factory=list)


class AuditFeedRead(BaseModel):
    scope_institution_id: str | None = None
    cross_tenant: bool = False
    groups: list[AuditGroupRead] = Field(default_factory=list)
    events: list[AuditEventRead] = Field(default_factory=list)

class ManualBridgeConfirm(BaseModel):
    model_config = ConfigDict(json_schema_extra={'examples': [{'certificate_number': 'CPO28AUG26-0009491-000', 'issuer': 'Bursa Malaysia Islamic Services Sdn.Bhd.', 'seller': 'Hidaya Said ( 000 )', 'buyer': 'Bursa Malaysia Islamic Services', 'bid_no': '1', 'selling_time': '19:00:50.857', 'selling_date': '28 AUGUST 2026', 'value_date': '28 AUGUST 2026', 'product_code': 'CPO-MSIA-09', 'product_description': 'Crude Palm Oil - Malaysia - Listed 09', 'unit': 'Tonnage', 'volume': '.32293179', 'currency': 'KES', 'price': '154831.46067416', 'price_myr_equivalent': '4823.00', 'value_amount': '50000.00', 'transaction_type': '-'}]})

    certificate_number: str = Field(..., description='Certificate number from BSAS e-cert PDF')
    issuer: str = Field('Bursa Malaysia Islamic Services Sdn.Bhd.', description='Certificate issuer')
    seller: str | None = Field(None, description='Seller on the e-cert')
    buyer: str | None = Field(None, description='Buyer on the e-cert')
    bid_no: str | None = None
    selling_time: str | None = None
    selling_date: str | None = None
    value_date: str | None = None
    product_code: str | None = None
    product_description: str | None = None
    unit: str | None = None
    volume: str | None = None
    currency: str | None = None
    price: str | None = Field(None, description='Price in certificate currency')
    price_myr_equivalent: str | None = None
    value_amount: str | None = Field(None, description='Transaction value')
    transaction_type: str | None = None
    pdf_filename: str | None = Field(None, description='Stored PDF filename if previously uploaded')
