"""Tawarruq provider + rate history.

Revision ID: 020
Revises: 019
Create Date: 2026-10-30
"""

from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tawarruq_provider_rates" in inspector.get_table_names():
        return
    op.create_table(
        "tawarruq_provider_rates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("rate_pct", sa.Numeric(10, 6), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("ops_users.id"), nullable=True),
    )
    op.create_index("ix_tawarruq_provider_rates_provider", "tawarruq_provider_rates", ["provider"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tawarruq_provider_rates" in inspector.get_table_names():
        op.drop_index("ix_tawarruq_provider_rates_provider", table_name="tawarruq_provider_rates")
        op.drop_table("tawarruq_provider_rates")
