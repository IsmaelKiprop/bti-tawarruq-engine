"""Add customer email for Murabaha accept notices.

Revision ID: 009
Revises: 008
Create Date: 2026-09-07
"""

from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "customers" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("customers")}
    if "email" in existing:
        return
    op.add_column("customers", sa.Column("email", sa.String(length=255), nullable=True))
    op.create_index("ix_customers_email", "customers", ["email"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "customers" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("customers")}
    if "email" not in existing:
        return
    op.drop_index("ix_customers_email", table_name="customers")
    op.drop_column("customers", "email")
