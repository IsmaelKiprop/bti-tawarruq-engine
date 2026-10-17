"""Bind ops users to one Agent Dealer desk.

Revision ID: 008
Revises: 007
Create Date: 2026-09-07
"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ops_users" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("ops_users")}
    if "agent_dealer_id" in existing:
        return
    op.add_column("ops_users", sa.Column("agent_dealer_id", sa.String(length=36), nullable=True))
    op.create_index("ix_ops_users_agent_dealer_id", "ops_users", ["agent_dealer_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ops_users" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("ops_users")}
    if "agent_dealer_id" not in existing:
        return
    op.drop_index("ix_ops_users_agent_dealer_id", table_name="ops_users")
    op.drop_column("ops_users", "agent_dealer_id")
