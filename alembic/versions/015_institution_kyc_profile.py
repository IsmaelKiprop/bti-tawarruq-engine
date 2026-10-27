"""FI KYC profile and institution lifecycle.

Revision ID: 015
Revises: 014
Create Date: 2026-10-27
"""

from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "institutions" in tables:
        cols = {col["name"] for col in inspector.get_columns("institutions")}
        if "lifecycle_status" not in cols:
            op.add_column(
                "institutions",
                sa.Column("lifecycle_status", sa.String(length=32), nullable=False, server_default="active"),
            )
            try:
                op.create_index("ix_institutions_lifecycle_status", "institutions", ["lifecycle_status"])
            except Exception:
                pass
    if "institution_profiles" not in tables:
        op.create_table(
            "institution_profiles",
            sa.Column("institution_id", sa.String(length=36), nullable=False),
            sa.Column("trading_name", sa.String(length=200), nullable=True),
            sa.Column("institution_type", sa.String(length=64), nullable=True),
            sa.Column("other_institution_type", sa.String(length=120), nullable=True),
            sa.Column("registration_number", sa.String(length=64), nullable=True),
            sa.Column("incorporation_date", sa.Date(), nullable=True),
            sa.Column("incorporation_country", sa.String(length=2), nullable=True),
            sa.Column("kra_pin", sa.String(length=16), nullable=True),
            sa.Column("registered_address_line1", sa.String(length=200), nullable=True),
            sa.Column("registered_address_line2", sa.String(length=200), nullable=True),
            sa.Column("registered_county", sa.String(length=100), nullable=True),
            sa.Column("registered_postal_code", sa.String(length=16), nullable=True),
            sa.Column("physical_address", sa.String(length=250), nullable=True),
            sa.Column("website_url", sa.String(length=500), nullable=True),
            sa.Column("support_email", sa.String(length=254), nullable=True),
            sa.Column("main_telephone", sa.String(length=20), nullable=True),
            sa.Column("business_description", sa.Text(), nullable=True),
            sa.Column("primary_regulator", sa.String(length=32), nullable=True),
            sa.Column("regulator_other_name", sa.String(length=120), nullable=True),
            sa.Column("licence_number", sa.String(length=80), nullable=True),
            sa.Column("licence_issue_date", sa.Date(), nullable=True),
            sa.Column("licence_expiry_date", sa.Date(), nullable=True),
            sa.Column("licence_status", sa.String(length=32), nullable=True),
            sa.Column("regulator_register_url", sa.String(length=500), nullable=True),
            sa.Column("ownership_structure_summary", sa.Text(), nullable=True),
            sa.Column("parent_company_name", sa.String(length=200), nullable=True),
            sa.Column("related_entities", sa.JSON(), nullable=True),
            sa.Column("owners_and_shareholders", sa.JSON(), nullable=True),
            sa.Column("ownership_percentage", sa.Numeric(7, 4), nullable=True),
            sa.Column("ubo_details", sa.JSON(), nullable=True),
            sa.Column("directors_board_members", sa.JSON(), nullable=True),
            sa.Column("ceo_managing_director_name", sa.String(length=160), nullable=True),
            sa.Column("senior_management_details", sa.JSON(), nullable=True),
            sa.Column("pep_screening_status", sa.String(length=32), nullable=True),
            sa.Column("sanctions_screening_status", sa.String(length=32), nullable=True),
            sa.Column("adverse_media_screening_status", sa.String(length=32), nullable=True),
            sa.Column("primary_contact_full_name", sa.String(length=160), nullable=True),
            sa.Column("primary_contact_title", sa.String(length=100), nullable=True),
            sa.Column("primary_contact_work_email", sa.String(length=254), nullable=True),
            sa.Column("primary_contact_phone", sa.String(length=20), nullable=True),
            sa.Column("compliance_officer_name", sa.String(length=160), nullable=True),
            sa.Column("compliance_officer_email", sa.String(length=254), nullable=True),
            sa.Column("authorized_signatories", sa.JSON(), nullable=True),
            sa.Column("representative_id_type", sa.String(length=32), nullable=True),
            sa.Column("representative_id_number", sa.String(length=40), nullable=True),
            sa.Column("representative_identity_verification_status", sa.String(length=32), nullable=True),
            sa.Column("authority_to_act_document_id", sa.String(length=100), nullable=True),
            sa.Column("settlement_bank_name", sa.String(length=150), nullable=True),
            sa.Column("settlement_account_name", sa.String(length=200), nullable=True),
            sa.Column("settlement_branch", sa.String(length=120), nullable=True),
            sa.Column("settlement_account_number", sa.String(length=34), nullable=True),
            sa.Column("settlement_currency", sa.String(length=3), nullable=True),
            sa.Column("settlement_account_verification_status", sa.String(length=32), nullable=True),
            sa.Column("settlement_account_evidence_document_id", sa.String(length=100), nullable=True),
            sa.Column("expected_monthly_transaction_count", sa.Integer(), nullable=True),
            sa.Column("expected_monthly_transaction_value", sa.Numeric(18, 2), nullable=True),
            sa.Column("typical_transaction_amount", sa.Numeric(18, 2), nullable=True),
            sa.Column("maximum_transaction_amount", sa.Numeric(18, 2), nullable=True),
            sa.Column("target_go_live_date", sa.Date(), nullable=True),
            sa.Column("commercial_agreement_status", sa.String(length=32), nullable=True),
            sa.Column("pricing_schedule_reference", sa.String(length=100), nullable=True),
            sa.Column("dispute_contact_email", sa.String(length=254), nullable=True),
            sa.Column("application_status", sa.String(length=40), nullable=False, server_default="DRAFT"),
            sa.Column("submission_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("assigned_reviewer_id", sa.String(length=36), nullable=True),
            sa.Column("review_notes", sa.Text(), nullable=True),
            sa.Column("approval_decision", sa.String(length=40), nullable=False, server_default="PENDING"),
            sa.Column("approval_reason", sa.Text(), nullable=True),
            sa.Column("approver_id", sa.String(length=36), nullable=True),
            sa.Column("approval_timestamp", sa.DateTime(timezone=True), nullable=True),
            sa.Column("activation_date", sa.Date(), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("updated_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("institution_id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "institution_profiles" in tables:
        op.drop_table("institution_profiles")
    if "institutions" in tables:
        cols = {col["name"] for col in inspector.get_columns("institutions")}
        if "lifecycle_status" in cols:
            try:
                op.drop_index("ix_institutions_lifecycle_status", table_name="institutions")
            except Exception:
                pass
            op.drop_column("institutions", "lifecycle_status")
