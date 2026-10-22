"""Sedania bank financing: SASC agency, trade docs, muqassah, CASA, physical delivery.

Revision ID: 012
Revises: 011
Create Date: 2026-10-22
"""

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "tawarruq_executions" not in tables:
        return
    cols = {col["name"] for col in inspector.get_columns("tawarruq_executions")}
    additions = [
        ("path", sa.Column("path", sa.String(length=32), nullable=False, server_default="sacco")),
        ("flow_variant", sa.Column("flow_variant", sa.String(length=32), nullable=False, server_default="approved_wakeel")),
        ("delivery_mode", sa.Column("delivery_mode", sa.String(length=32), nullable=False, server_default="constructive")),
        ("agency_role", sa.Column("agency_role", sa.String(length=16), nullable=False, server_default="wakeel")),
        ("agency_party", sa.Column("agency_party", sa.String(length=64), nullable=False, server_default="SEDANIA_AS_SALAM_CAPITAL")),
        ("appoint_sasc", sa.Column("appoint_sasc", sa.Boolean(), nullable=False, server_default=sa.true())),
        ("purchase_order_ref", sa.Column("purchase_order_ref", sa.String(length=64), nullable=True)),
        ("commodity_invoice_ref", sa.Column("commodity_invoice_ref", sa.String(length=64), nullable=True)),
        ("delivery_order_ref", sa.Column("delivery_order_ref", sa.String(length=128), nullable=True)),
        ("trading_ecert_ref", sa.Column("trading_ecert_ref", sa.String(length=128), nullable=True)),
        ("supplier_ref", sa.Column("supplier_ref", sa.String(length=128), nullable=True)),
        ("purchaser_ref", sa.Column("purchaser_ref", sa.String(length=128), nullable=True)),
        ("muqassah_ref", sa.Column("muqassah_ref", sa.String(length=64), nullable=True)),
        ("muqassah_at", sa.Column("muqassah_at", sa.DateTime(timezone=True), nullable=True)),
        ("casa_account", sa.Column("casa_account", sa.String(length=64), nullable=True)),
        ("casa_ref", sa.Column("casa_ref", sa.String(length=64), nullable=True)),
        ("casa_credited_at", sa.Column("casa_credited_at", sa.DateTime(timezone=True), nullable=True)),
        ("cash_disbursement", sa.Column("cash_disbursement", sa.String(length=32), nullable=False, server_default="sacco_cbs")),
        ("physical_delivery_requested", sa.Column("physical_delivery_requested", sa.Boolean(), nullable=False, server_default=sa.false())),
        ("physical_delivery_status", sa.Column("physical_delivery_status", sa.String(length=32), nullable=True)),
        ("physical_delivery_notified_at", sa.Column("physical_delivery_notified_at", sa.DateTime(timezone=True), nullable=True)),
        ("repayment_settled_at", sa.Column("repayment_settled_at", sa.DateTime(timezone=True), nullable=True)),
    ]
    for name, column in additions:
        if name not in cols:
            op.add_column("tawarruq_executions", column)
    if "path" not in cols:
        op.create_index("ix_tawarruq_executions_path", "tawarruq_executions", ["path"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "tawarruq_executions" not in tables:
        return
    cols = {col["name"] for col in inspector.get_columns("tawarruq_executions")}
    if "path" in cols:
        op.drop_index("ix_tawarruq_executions_path", table_name="tawarruq_executions")
    for name in (
        "repayment_settled_at",
        "physical_delivery_notified_at",
        "physical_delivery_status",
        "physical_delivery_requested",
        "cash_disbursement",
        "casa_credited_at",
        "casa_ref",
        "casa_account",
        "muqassah_at",
        "muqassah_ref",
        "purchaser_ref",
        "supplier_ref",
        "trading_ecert_ref",
        "delivery_order_ref",
        "commodity_invoice_ref",
        "purchase_order_ref",
        "appoint_sasc",
        "agency_party",
        "agency_role",
        "delivery_mode",
        "flow_variant",
        "path",
    ):
        if name in cols:
            op.drop_column("tawarruq_executions", name)
