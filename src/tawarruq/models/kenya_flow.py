import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tawarruq.database import Base
from tawarruq.enums import InstallmentStatus, PossessionStatus, WalletProvider


class AgentDealer(Base):
    """M-Pesa Authorised Agent Dealer whose float pool Buruuj draws from for Kenya Tawarruq."""

    __tablename__ = "agent_dealers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    business_name: Mapped[str] = mapped_column(String(256), nullable=False)
    mpesa_number: Mapped[str] = mapped_column(String(20), nullable=False)
    mpesa_till_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    float_balance: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    institution_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("institutions.id"), nullable=True, index=True
    )
    contact_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    topups = relationship("AgentDealerFloatTopup", back_populates="dealer", order_by="AgentDealerFloatTopup.created_at.desc()")


class AgentDealerFloatTopup(Base):
    """Records each dealer float top-up or Kenya step 2 draw."""

    __tablename__ = "agent_dealer_float_topups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dealer_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_dealers.id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    dealer = relationship("AgentDealer", back_populates="topups")


class ThirdPartyBroker(Base):
    __tablename__ = "third_party_brokers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    mno_codes: Mapped[str] = mapped_column(Text, default="AIRTIME_SAFARICOM,AIRTIME_AIRTEL")
    is_mno_pool: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssetBatch(Base):
    """Constructive possession evidence for MNO airtime/float batches."""

    __tablename__ = "asset_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    leg_id: Mapped[str] = mapped_column(String(36), ForeignKey("transaction_legs.id"), unique=True, nullable=False)
    batch_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    asset_ref_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    mno_code: Mapped[str] = mapped_column(String(64), nullable=False)
    mno_receipt_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    purchase_order_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delivery_order_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    supplier_invoice_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_dealer_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    possession_status: Mapped[str] = mapped_column(String(32), default=PossessionStatus.PENDING)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    leg = relationship("TransactionLeg", back_populates="asset_batch")


class MurabahaContract(Base):
    __tablename__ = "murabaha_contracts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("financing_applications.id"), unique=True, nullable=False
    )
    offer_id: Mapped[str] = mapped_column(String(36), ForeignKey("financing_offers.id"), nullable=False)
    document_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signature_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    installment_count: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application = relationship("FinancingApplication", back_populates="murabaha_contract")
    installments = relationship("RepaymentInstallment", back_populates="contract", order_by="RepaymentInstallment.due_date")


class RepaymentInstallment(Base):
    __tablename__ = "repayment_installments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    contract_id: Mapped[str] = mapped_column(String(36), ForeignKey("murabaha_contracts.id"), nullable=False, index=True)
    installment_number: Mapped[int] = mapped_column(nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=InstallmentStatus.SCHEDULED)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)

    contract = relationship("MurabahaContract", back_populates="installments")


class LiquidationOrder(Base):
    __tablename__ = "liquidation_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("commodity_transactions.id"), unique=True)
    broker_id: Mapped[str] = mapped_column(String(36), ForeignKey("third_party_brokers.id"), nullable=False)
    spot_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    no_inah_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    counterparty_code: Mapped[str] = mapped_column(String(64), nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    transaction = relationship("CommodityTransaction", back_populates="liquidation_order")
    broker = relationship("ThirdPartyBroker")


class WalletDisbursement(Base):
    __tablename__ = "wallet_disbursements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    disbursement_id: Mapped[str] = mapped_column(String(36), ForeignKey("disbursements.id"), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), default=WalletProvider.MPESA)
    wallet_number: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    external_txn_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    credited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    disbursement = relationship("Disbursement", back_populates="wallet_disbursement")


class ShariahAuditLog(Base):
    """Isolated append-only Shariah audit ledger with tamper-evident hash chain."""

    __tablename__ = "shariah_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    step_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    asset_ref_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    actor_from: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_to: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mno_receipt_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    institution_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    transaction_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    application_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="0" * 64)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
