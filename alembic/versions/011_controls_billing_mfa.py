"""Maker-checker, billing, reconciliation, tenant suspend, MFA columns.

Revision ID: 011
Revises: 010
Create Date: 2026-10-21
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "institutions" in tables:
        cols = {col["name"] for col in inspector.get_columns("institutions")}
        if "active" not in cols:
            op.add_column("institutions", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))
        if "approval_steps" not in cols:
            op.add_column(
                "institutions",
                sa.Column(
                    "approval_steps",
                    sa.String(length=256),
                    nullable=False,
                    server_default="murabaha,liquidation,disbursement",
                ),
            )
        if "approval_limit_amount" not in cols:
            op.add_column("institutions", sa.Column("approval_limit_amount", sa.Numeric(18, 2), nullable=True))
        if "billing_fee_bps" not in cols:
            op.add_column("institutions", sa.Column("billing_fee_bps", sa.Integer(), nullable=False, server_default="25"))

    if "ops_users" in tables:
        cols = {col["name"] for col in inspector.get_columns("ops_users")}
        if "approval_limit_amount" not in cols:
            op.add_column("ops_users", sa.Column("approval_limit_amount", sa.Numeric(18, 2), nullable=True))
        if "mfa_secret" not in cols:
            op.add_column("ops_users", sa.Column("mfa_secret", sa.String(length=64), nullable=True))
        if "mfa_enabled" not in cols:
            op.add_column("ops_users", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))

    if "pending_approvals" not in tables:
        op.create_table(
            "pending_approvals",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("institution_id", sa.String(length=36), sa.ForeignKey("institutions.id"), nullable=False),
            sa.Column("step", sa.String(length=32), nullable=False),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("amount", sa.Numeric(18, 2), nullable=True),
            sa.Column("currency", sa.String(length=8), nullable=True),
            sa.Column("application_id", sa.String(length=36), sa.ForeignKey("financing_applications.id"), nullable=True),
            sa.Column("transaction_id", sa.String(length=36), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("requested_by_id", sa.String(length=36), sa.ForeignKey("ops_users.id"), nullable=True),
            sa.Column("decided_by_id", sa.String(length=36), sa.ForeignKey("ops_users.id"), nullable=True),
            sa.Column("decision_note", sa.String(length=512), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_pending_approvals_institution_id", "pending_approvals", ["institution_id"])
        op.create_index("ix_pending_approvals_status", "pending_approvals", ["status"])
        op.create_index("ix_pending_approvals_step", "pending_approvals", ["step"])

    if "billing_invoices" not in tables:
        op.create_table(
            "billing_invoices",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("institution_id", sa.String(length=36), sa.ForeignKey("institutions.id"), nullable=False),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("transaction_count", sa.Integer(), nullable=False),
            sa.Column("volume_amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("fee_bps", sa.Integer(), nullable=False),
            sa.Column("fee_amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("currency", sa.String(length=8), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("note", sa.String(length=512), nullable=True),
        )
        op.create_index("ix_billing_invoices_institution_id", "billing_invoices", ["institution_id"])
        op.create_index("ix_billing_invoices_status", "billing_invoices", ["status"])

    if "reconciliation_items" not in tables:
        op.create_table(
            "reconciliation_items",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("institution_id", sa.String(length=36), sa.ForeignKey("institutions.id"), nullable=False),
            sa.Column("transaction_id", sa.String(length=36), sa.ForeignKey("commodity_transactions.id"), nullable=False),
            sa.Column("application_id", sa.String(length=36), nullable=True),
            sa.Column("expected_amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("settled_amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("currency", sa.String(length=8), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("note", sa.String(length=512), nullable=True),
            sa.Column("resolved_by_id", sa.String(length=36), sa.ForeignKey("ops_users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_reconciliation_items_institution_id", "reconciliation_items", ["institution_id"])
        op.create_index("ix_reconciliation_items_transaction_id", "reconciliation_items", ["transaction_id"], unique=True)
        op.create_index("ix_reconciliation_items_status", "reconciliation_items", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "reconciliation_items" in tables:
        op.drop_table("reconciliation_items")
    if "billing_invoices" in tables:
        op.drop_table("billing_invoices")
    if "pending_approvals" in tables:
        op.drop_table("pending_approvals")
