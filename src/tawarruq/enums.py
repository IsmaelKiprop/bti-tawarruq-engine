from enum import StrEnum


class ApplicationStatus(StrEnum):
    DRAFT = "draft"
    ELIGIBILITY_PENDING = "eligibility_pending"
    ELIGIBILITY_FAILED = "eligibility_failed"
    OFFER_PENDING = "offer_pending"
    OFFER_ACCEPTED = "offer_accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class TransactionPhase(StrEnum):
    PHASE_1_PURCHASE = "phase_1_purchase"
    PHASE_2_MURABAHA = "phase_2_murabaha"
    PHASE_3_LIQUIDATION = "phase_3_liquidation"
    PHASE_4_REPAYMENT = "phase_4_repayment"
    COMPLETED = "completed"


class ShariahStepId(StrEnum):
    FINANCING_REQUEST = "FINANCING_REQUEST"
    WAD_UNDERTAKING = "WAD_UNDERTAKING"
    ELIGIBILITY_CHECK = "ELIGIBILITY_CHECK"
    MURABAHA_PURCHASE = "MURABAHA_PURCHASE"
    CONSTRUCTIVE_POSSESSION = "CONSTRUCTIVE_POSSESSION"
    MURABAHA_OFFER = "MURABAHA_OFFER"
    CUSTOMER_ACCEPTANCE = "CUSTOMER_ACCEPTANCE"
    OWNERSHIP_TRANSFER = "OWNERSHIP_TRANSFER"
    WAKALA_APPOINTMENT = "WAKALA_APPOINTMENT"
    THIRD_PARTY_LIQUIDATION = "THIRD_PARTY_LIQUIDATION"
    WALLET_DISBURSEMENT = "WALLET_DISBURSEMENT"
    REPAYMENT_SCHEDULED = "REPAYMENT_SCHEDULED"
    REPAYMENT_RECEIVED = "REPAYMENT_RECEIVED"


class LegNumber(StrEnum):
    PURCHASE = "1"
    TRANSFER = "2"
    SALE = "3"


class LegStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    AWAITING_POSSESSION = "awaiting_possession"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class TransactionMode(StrEnum):
    MOCK = "mock"
    LIVE = "live"
    MANUAL_BRIDGE = "manual_bridge"
    MNO = "mno"
    AGENT_DEALER = "agent_dealer"


class TransactionStatus(StrEnum):
    CREATED = "created"
    EXECUTING = "executing"
    AWAITING_MANUAL = "awaiting_manual"
    AWAITING_POSSESSION = "awaiting_possession"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class AuditActor(StrEnum):
    HUMAN = "human"
    AI_WORKER = "ai_worker"
    SYSTEM = "system"
    CUSTOMER = "customer"
    MNO = "mno"
    BROKER = "broker"
    SACCO = "sacco"
    SEDANIA = "sedania"


class WebhookEvent(StrEnum):
    APPLICATION_CREATED = "application.created"
    ELIGIBILITY_PASSED = "eligibility.passed"
    ELIGIBILITY_FAILED = "eligibility.failed"
    OFFER_GENERATED = "offer.generated"
    OFFER_ACCEPTED = "offer.accepted"
    POSSESSION_VERIFIED = "possession.verified"
    CUSTOMER_SALE_RECORDED = "customer_sale.recorded"
    CUSTOMER_AGENCY_APPOINTED = "customer_agency.appointed"
    TRANSACTION_CREATED = "transaction.created"
    LEG_CONFIRMED = "leg.confirmed"
    LIQUIDATION_COMPLETED = "liquidation.completed"
    NO_INAH_BLOCKED = "no_inah.blocked"
    TRANSACTION_COMPLETED = "transaction.completed"
    TRANSACTION_FAILED = "transaction.failed"
    TRANSACTION_ESCALATED = "transaction.escalated"
    DISBURSEMENT_CREATED = "disbursement.created"
    WALLET_CREDITED = "wallet.credited"
    TAWARRUQ_CERTIFICATE_ISSUED = "tawarruq_certificate.issued"
    REPAYMENT_DUE = "repayment.due"
    REPAYMENT_RECEIVED = "repayment.received"
    HANDOFF_RECORDED = "handoff.recorded"
    TAWARRUQ_CERTIFICATES_READY = "tawarruq.certificates_ready"


class AgencyStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"


class KycStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class AmlStatus(StrEnum):
    CLEAR = "clear"
    PENDING = "pending"
    FLAGGED = "flagged"
    BLOCKED = "blocked"


class WalletProvider(StrEnum):
    MPESA = "mpesa"
    AIRTEL_MONEY = "airtel_money"


class InstallmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    DUE = "due"
    AWAITING_PAYMENT = "awaiting_payment"
    PAID = "paid"
    OVERDUE = "overdue"
    DEFAULTED = "defaulted"


class PossessionStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class CommodityType(StrEnum):
    AIRTIME_SAFARICOM = "AIRTIME_SAFARICOM"
    AIRTIME_AIRTEL = "AIRTIME_AIRTEL"
    FLOAT_SAFARICOM = "FLOAT_SAFARICOM"
    FLOAT_AIRTEL = "FLOAT_AIRTEL"
    FLOAT_MPESA_DEALER = "FLOAT_MPESA_DEALER"
    PALM_OIL = "PALM_OIL"


class ExecutionStatus(StrEnum):
    RECEIVED = "received"
    STAMPING_CONTRACTS = "stamping_contracts"
    SPOT_PURCHASE = "spot_purchase"
    DEFERRED_MURABAHAH = "deferred_murabahah"
    SPOT_LIQUIDATION = "spot_liquidation"
    WEBHOOK_RELAY = "webhook_relay"
    READY_FOR_SACCO_DISBURSEMENT = "ready_for_sacco_disbursement"
    FAILED = "failed"


class VaultCertificateKind(StrEnum):
    WAD = "wad"
    WAKALAH = "wakalah"
    PURCHASE = "purchase"
    MURABAHAH = "murabahah"
    LIQUIDATION = "liquidation"


class ApiKeyRole(StrEnum):
    """RBAC roles for API keys and ops portal access."""

    PLATFORM_ADMIN = "platform_admin"
    INSTITUTION_ADMIN = "institution_admin"
    INSTITUTION_OPS = "institution_ops"
    AGENT_DEALER = "agent_dealer"
    SHARIAH_OFFICER = "shariah_officer"
    READ_ONLY = "read_only"
