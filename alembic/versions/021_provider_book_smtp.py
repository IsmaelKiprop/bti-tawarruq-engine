"""Provider book, per-FI provider, and optional SMTP settings.

Revision ID: 021
Revises: 020
Create Date: 2026-11-02
"""

from alembic import op
import sqlalchemy as sa

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "tawarruq_providers" not in tables:
        op.create_table(
            "tawarruq_providers",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("code", sa.String(16), nullable=False),
            sa.Column("company_name", sa.String(256), nullable=False),
            sa.Column("country", sa.String(128), nullable=False, server_default=""),
            sa.Column("website", sa.String(512), nullable=False, server_default=""),
            sa.Column("rate_pct", sa.Numeric(10, 6), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_tawarruq_providers_code", "tawarruq_providers", ["code"], unique=True)
    if "institutions" in tables:
        columns = {col["name"] for col in inspector.get_columns("institutions")}
        if "tawarruq_provider" not in columns:
            op.add_column("institutions", sa.Column("tawarruq_provider", sa.String(16), nullable=False, server_default="sedania"))
    if "platform_settings" in tables:
        columns = {col["name"] for col in inspector.get_columns("platform_settings")}
        if "smtp_host" not in columns:
            op.add_column("platform_settings", sa.Column("smtp_host", sa.String(256), nullable=False, server_default=""))
        if "smtp_port" not in columns:
            op.add_column("platform_settings", sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="587"))
        if "smtp_user" not in columns:
            op.add_column("platform_settings", sa.Column("smtp_user", sa.String(256), nullable=False, server_default=""))
        if "smtp_password" not in columns:
            op.add_column("platform_settings", sa.Column("smtp_password", sa.String(256), nullable=False, server_default=""))
        if "smtp_from" not in columns:
            op.add_column("platform_settings", sa.Column("smtp_from", sa.String(256), nullable=False, server_default=""))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "platform_settings" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("platform_settings")}
        for name in ("smtp_from", "smtp_password", "smtp_user", "smtp_port", "smtp_host"):
            if name in columns:
                op.drop_column("platform_settings", name)
    if "institutions" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("institutions")}
        if "tawarruq_provider" in columns:
            op.drop_column("institutions", "tawarruq_provider")
    if "tawarruq_providers" in inspector.get_table_names():
        op.drop_index("ix_tawarruq_providers_code", table_name="tawarruq_providers")
        op.drop_table("tawarruq_providers")
