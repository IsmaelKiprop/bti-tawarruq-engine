"""Add SACCO execute path: HMAC secrets, executions, 7-year certificate vault.

Revision ID: 010
Revises: 009
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "api_keys" in tables:
        cols = {col["name"] for col in inspector.get_columns("api_keys")}
        if "hmac_secret" not in cols:
            op.add_column("api_keys", sa.Column("hmac_secret", sa.String(length=64), nullable=True))

    if "tawarruq_executions" not in tables:
        op.create_table(
            "tawarruq_executions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("institution_id", sa.String(length=36), sa.ForeignKey("institutions.id"), nullable=False),
            sa.Column("application_id", sa.String(length=36), sa.ForeignKey("financing_applications.id"), nullable=True),
            sa.Column("customer_id", sa.String(length=36), sa.ForeignKey("customers.id"), nullable=False),
            sa.Column("client_request_id", sa.String(length=128), nullable=True),
            sa.Column("amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("profit_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("deferred_price", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("tenor_months", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(length=8), nullable=False, server_default="KES"),
            sa.Column("status", sa.String(length=48), nullable=False, server_default="received"),
            sa.Column("wad_token_id", sa.String(length=128), nullable=True),
            sa.Column("wad_signature", sa.String(length=128), nullable=True),
            sa.Column("wakalah_token_id", sa.String(length=128), nullable=True),
            sa.Column("wakalah_signature", sa.String(length=128), nullable=True),
            sa.Column("sedania_batch_id", sa.String(length=128), nullable=True),
            sa.Column("callback_url", sa.String(length=512), nullable=True),
            sa.Column("callback_delivered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_tawarruq_executions_institution_id", "tawarruq_executions", ["institution_id"])
        op.create_index("ix_tawarruq_executions_application_id", "tawarruq_executions", ["application_id"])
        op.create_index("ix_tawarruq_executions_customer_id", "tawarruq_executions", ["customer_id"])
        op.create_index("ix_tawarruq_executions_client_request_id", "tawarruq_executions", ["client_request_id"])
        op.create_index("ix_tawarruq_executions_status", "tawarruq_executions", ["status"])
        op.create_index("ix_tawarruq_executions_sedania_batch_id", "tawarruq_executions", ["sedania_batch_id"])

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "certificate_vault" not in tables:
        op.create_table(
            "certificate_vault",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("execution_id", sa.String(length=36), sa.ForeignKey("tawarruq_executions.id"), nullable=False),
            sa.Column("institution_id", sa.String(length=36), sa.ForeignKey("institutions.id"), nullable=False),
            sa.Column("application_id", sa.String(length=36), sa.ForeignKey("financing_applications.id"), nullable=True),
            sa.Column("kind", sa.String(length=32), nullable=False),
            sa.Column("certificate_number", sa.String(length=128), nullable=False),
            sa.Column("source", sa.String(length=32), nullable=False),
            sa.Column("source_url", sa.String(length=512), nullable=True),
            sa.Column("access_token", sa.String(length=64), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("serial_numbers_json", sa.Text(), nullable=True),
            sa.Column("batch_id", sa.String(length=128), nullable=True),
            sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_certificate_vault_execution_id", "certificate_vault", ["execution_id"])
        op.create_index("ix_certificate_vault_institution_id", "certificate_vault", ["institution_id"])
        op.create_index("ix_certificate_vault_kind", "certificate_vault", ["kind"])
        op.create_index("ix_certificate_vault_certificate_number", "certificate_vault", ["certificate_number"])
        op.create_index("ix_certificate_vault_access_token", "certificate_vault", ["access_token"], unique=True)
        op.create_index("ix_certificate_vault_retention_until", "certificate_vault", ["retention_until"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "certificate_vault" in tables:
        op.drop_table("certificate_vault")
    if "tawarruq_executions" in tables:
        op.drop_table("tawarruq_executions")
    if "api_keys" in tables:
        cols = {col["name"] for col in inspector.get_columns("api_keys")}
        if "hmac_secret" in cols:
            op.drop_column("api_keys", "hmac_secret")
