"""Add agent_dealers and agent_dealer_float_topups tables.

Revision ID: 007
Revises: 006
Create Date: 2026-09-05
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006_bsas_ecert_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_dealers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("business_name", sa.String(256), nullable=False),
        sa.Column("mpesa_number", sa.String(20), nullable=False),
        sa.Column("mpesa_till_number", sa.String(20), nullable=True),
        sa.Column("float_balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("institution_id", sa.String(36), sa.ForeignKey("institutions.id"), nullable=True),
        sa.Column("contact_name", sa.String(128), nullable=True),
        sa.Column("contact_phone", sa.String(20), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_agent_dealers_code", "agent_dealers", ["code"])
    op.create_index("ix_agent_dealers_institution_id", "agent_dealers", ["institution_id"])

    op.create_table(
        "agent_dealer_float_topups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dealer_id", sa.String(36), sa.ForeignKey("agent_dealers.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("reference", sa.String(128), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("added_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_agent_dealer_float_topups_dealer_id", "agent_dealer_float_topups", ["dealer_id"])


def downgrade() -> None:
    op.drop_table("agent_dealer_float_topups")
    op.drop_table("agent_dealers")
