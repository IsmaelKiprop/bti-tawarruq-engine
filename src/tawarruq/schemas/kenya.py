from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    institution_id: str | None = Field(None, description='Institution UUID (defaults to DEFAULT)')
    phone: str = Field(..., examples=['254712345678'])
    email: str | None = Field(None, examples=['jane.wanjiku@example.com'])
    full_name: str = Field(..., examples=['Jane Wanjiku'])
    wallet_number: str = Field(..., examples=['254712345678'])
    national_id: str | None = Field(None, examples=['12345678'])
    kyc_status: str = Field('verified', examples=['verified'])
    aml_status: str = Field('clear', examples=['clear'])
    credit_score: int = Field(650)
    wallet_provider: str = Field('mpesa', examples=['mpesa'])

class CustomerUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    national_id: str | None = None
    kyc_status: str | None = Field(None, examples=['verified', 'pending', 'rejected'])
    aml_status: str | None = Field(None, examples=['clear', 'pending', 'flagged'])
    credit_score: int | None = Field(None)
    wallet_number: str | None = None
    wallet_provider: str | None = None

class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    institution_id: str
    institution_name: str | None = None
    institution_code: str | None = None
    phone: str
    email: str | None = None
    full_name: str
    national_id: str | None
    kyc_status: str
    aml_status: str
    credit_score: int
    wallet_provider: str
    wallet_number: str
    created_at: datetime

class KenyaApplicationCreate(BaseModel):
    customer_id: str
    amount_requested: Decimal = Field(..., examples=['50000.00'])
    term_months: int = Field(..., examples=[6])
    purpose: str = Field(..., examples=['Airtime float financing'])

class EligibilityDecisionRequest(BaseModel):
    passed: bool = Field(..., description='Bank or SACCO credit decision')
    kyc_status: str | None = Field(None, examples=['verified'])
    aml_status: str | None = Field(None, examples=['clear'])
    credit_score: int | None = Field(None)
    decision_ref: str | None = Field(None, examples=['CORE-ELIG-8891'])
    notes: str | None = None

class EligibilityResultRead(BaseModel):
    application_id: str
    status: str
    eligibility_passed: bool | None
    message: str | None = None
    source: str | None = Field(None, description='engine | institution')

class MnoTransactionCreate(BaseModel):
    application_id: str
    commodity_code: str | None = Field(None, description='Omit to use the Agent Dealer pool when one is active, otherwise Safaricom airtime.', examples=['AIRTIME_SAFARICOM', 'FLOAT_MPESA_DEALER'])
    mode: str | None = Field(None, description='Omit to drain the dealer pool when a dealer is active. Send mno to keep the MNO path.', examples=['mno', 'agent_dealer'])

class PossessionVerifyRequest(BaseModel):
    batch_id: str | None = None
    mno_receipt_id: str | None = None

class WakalaConsentRequest(BaseModel):
    consent_ref: str = Field(..., examples=['WAKALA-CONSENT-001'])
    notes: str | None = Field(None, examples=['I appoint Buruuj as my agent to sell airtime'])

class WakalaConsentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    status: str
    notes: str | None
    appointed_at: datetime

class OfferSummaryRead(BaseModel):
    application_id: str
    cost_price: Decimal
    profit_amount: Decimal
    total_payable: Decimal
    installment_count: int
    accepted: bool

class OfferEmailRead(BaseModel):
    status: str
    email: str | None = None
    journey_url: str
    smtp_sent: bool = False
    mail_path: str | None = None
    reason: str | None = None

class MurabahaSignRequest(BaseModel):
    signature_ref: str | None = Field(None, examples=['DIGITAL-SIG-001'])

class MurabahaContractRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    document_hash: str
    signature_ref: str | None
    signed_at: datetime | None
    installment_count: int
    created_at: datetime

class RepaymentInstallmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    contract_id: str
    installment_number: int
    due_date: datetime
    amount: Decimal
    status: str
    paid_at: datetime | None
    payment_ref: str | None

class WalletDisbursementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    wallet_number: str
    amount: Decimal
    external_txn_id: str | None
    status: str
    credited_at: datetime | None

class ShariahAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    timestamp: datetime
    step_id: str
    entity_type: str
    entity_id: str
    asset_ref_no: str | None
    actor_from: str
    actor_to: str
    payload_hash: str
    details: str | None
    verified_at: datetime | None = None
    mno_receipt_id: str | None = None
    institution_id: str | None = None
    transaction_id: str | None = None
    application_id: str | None = None
    previous_hash: str | None = None
    entry_hash: str | None = None

class ShariahIntegrityRead(BaseModel):
    valid: bool
    ledger_chain: dict
    possession_sealed: bool
    entry_count: int
    application_id: str

class KenyaFlowStatusRead(BaseModel):
    application_id: str
    current_phase: str | None
    eligibility_passed: bool | None
    wad_accepted: bool = False
    offer_accepted: bool
    murabaha_signed: bool
    wakala_appointed: bool
    wallet_credited: bool
    transaction_id: str | None
    transaction_status: str | None
    transaction_phase: str | None
    installments_total: int
    installments_paid: int

class KenyaDisbursementRead(BaseModel):
    disbursement_id: str
    wallet_disbursement_id: str
    external_txn_id: str | None
    installment_count: int
