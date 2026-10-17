from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from tawarruq.schemas.common import ErrorResponse

class InstitutionCreate(BaseModel):
    name: str = Field(..., description='Institution display name', examples=['Demo Islamic Bank'])
    code: str = Field(..., description='Unique institution code', examples=['DIB001'])
    bsas_mode: str = Field('manual_bridge', description='Default BSAS backend: mock | manual_bridge | live', examples=['mock'])

class InstitutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description='UUID')
    name: str
    code: str
    bsas_mode: str = Field(..., description='Default BSAS integration mode for new transactions')
    created_at: datetime

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
    legs: list = Field(default_factory=list, description='All 3 legs with certificates')

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

class OpsChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(...)

class OpsUserCreate(BaseModel):
    email: str
    full_name: str
    role: str = Field('institution_ops', description='platform_admin | institution_admin | institution_ops | agent_dealer | shariah_officer | read_only')
    institution_id: str | None = None
    agent_dealer_id: str | None = Field(None, description='Required when role is agent_dealer. Binds this login to one float pool.')
    temporary_password: str | None = Field(None, description='Optional; generated if omitted. Shown once to admin to share.')

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
    created_at: datetime

class OpsUserUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    role: str | None = Field(None, description='platform_admin | institution_admin | institution_ops | agent_dealer | shariah_officer | read_only')
    institution_id: str | None = None
    agent_dealer_id: str | None = None
    active: bool | None = None

class OpsUserCreatedRead(BaseModel):
    temporary_password: str = Field(..., description='Share securely; not shown again')

class OpsUserPasswordResetRequest(BaseModel):
    temporary_password: str | None = Field(None, description='Optional admin-chosen password. Leave empty to auto-generate.')

class OpsUserPasswordResetRead(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    role: str | None = None
    temporary_password: str = Field(..., description='Share securely; not shown again')
    must_change_password: bool = True

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

class InstitutionUpdate(BaseModel):
    name: str | None = None
    bsas_mode: str | None = Field(None, description='mock | manual_bridge | live')

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

class WebhookCreatedRead(BaseModel):
    secret: str = Field(..., description='Signing secret shown once at creation')

class ApiKeyCreate(BaseModel):
    name: str = Field(..., examples=['Production integration'])
    role: str = Field('institution_ops', description='platform_admin | institution_admin | institution_ops | shariah_officer | read_only', examples=['institution_ops'])

class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    institution_id: str
    name: str
    key_prefix: str
    role: str = 'institution_ops'
    active: bool
    created_at: datetime

class ApiKeyCreatedRead(BaseModel):
    api_key: str = Field(..., description='Full key shown once at creation')
    hmac_secret: str | None = Field(None, description='HMAC secret shown once. Sign POST /tawarruq/execute with X-BTI-Signature.')

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
