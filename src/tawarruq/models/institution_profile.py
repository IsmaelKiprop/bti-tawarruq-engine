"""KYC profile for a financial institution (BTI customer)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from tawarruq.database import Base


class InstitutionProfile(Base):
    __tablename__ = "institution_profiles"

    institution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("institutions.id", ondelete="CASCADE"), primary_key=True
    )
    trading_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    institution_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    other_institution_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    incorporation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    incorporation_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    kra_pin: Mapped[str | None] = mapped_column(String(16), nullable=True)
    registered_address_line1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    registered_address_line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    registered_county: Mapped[str | None] = mapped_column(String(100), nullable=True)
    registered_postal_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    physical_address: Mapped[str | None] = mapped_column(String(250), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    support_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    main_telephone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    business_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    primary_regulator: Mapped[str | None] = mapped_column(String(32), nullable=True)
    regulator_other_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    licence_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    licence_issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    licence_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    licence_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    regulator_register_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    ownership_structure_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    related_entities: Mapped[list | None] = mapped_column(JSON, nullable=True)
    owners_and_shareholders: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ownership_percentage: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    ubo_details: Mapped[list | None] = mapped_column(JSON, nullable=True)
    directors_board_members: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ceo_managing_director_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    senior_management_details: Mapped[list | None] = mapped_column(JSON, nullable=True)
    pep_screening_status: Mapped[str | None] = mapped_column(String(32), nullable=True, default="NOT_STARTED")
    sanctions_screening_status: Mapped[str | None] = mapped_column(String(32), nullable=True, default="NOT_STARTED")
    adverse_media_screening_status: Mapped[str | None] = mapped_column(String(32), nullable=True, default="NOT_STARTED")

    primary_contact_full_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    primary_contact_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    primary_contact_work_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    primary_contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    compliance_officer_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    compliance_officer_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    authorized_signatories: Mapped[list | None] = mapped_column(JSON, nullable=True)
    representative_id_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    representative_id_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    representative_identity_verification_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    authority_to_act_document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    settlement_bank_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    settlement_account_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    settlement_branch: Mapped[str | None] = mapped_column(String(120), nullable=True)
    settlement_account_number: Mapped[str | None] = mapped_column(String(34), nullable=True)
    settlement_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    settlement_account_verification_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    settlement_account_evidence_document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    expected_monthly_transaction_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_monthly_transaction_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    typical_transaction_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    maximum_transaction_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    target_go_live_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    commercial_agreement_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pricing_schedule_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dispute_contact_email: Mapped[str | None] = mapped_column(String(254), nullable=True)

    application_status: Mapped[str] = mapped_column(String(40), default="DRAFT", nullable=False)
    submission_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_reviewer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_decision: Mapped[str] = mapped_column(String(40), default="PENDING", nullable=False)
    approval_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approver_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approval_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    institution = relationship("Institution", backref="kyc_profile", uselist=False)


def new_profile_id() -> str:
    return str(uuid.uuid4())
