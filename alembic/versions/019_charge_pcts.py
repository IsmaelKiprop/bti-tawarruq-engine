"""Sedania charge precision and per-FI BTI % Charge.

Revision ID: 019
Revises: 018
Create Date: 2026-10-28
"""

from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "platform_settings" in tables:
        cols = {col["name"]: col for col in inspector.get_columns("platform_settings")}
        if "sedania_charge_pct" in cols:
            try:
                op.alter_column(
                    "platform_settings",
                    "sedania_charge_pct",
                    existing_type=sa.Numeric(5, 2),
                    type_=sa.Numeric(10, 6),
                    existing_nullable=False,
                )
            except Exception:
                pass
        op.execute("UPDATE platform_settings SET sedania_charge_pct = 0.0035 WHERE sedania_charge_pct = 5")
    if "institutions" in tables:
        cols = {col["name"] for col in inspector.get_columns("institutions")}
        if "bti_charge_pct" not in cols:
            op.add_column(
                "institutions",
                sa.Column("bti_charge_pct", sa.Numeric(10, 6), nullable=False, server_default="0.004"),
            )
            op.execute("UPDATE institutions SET bti_charge_pct = 0.004")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "institutions" in set(inspector.get_table_names()):
        cols = {col["name"] for col in inspector.get_columns("institutions")}
        if "bti_charge_pct" in cols:
            op.drop_column("institutions", "bti_charge_pct")
