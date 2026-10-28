"""Super Admin platform settings (Sedania % Charge).

Revision ID: 018
Revises: 017
Create Date: 2026-10-28
"""

from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "platform_settings" in set(inspector.get_table_names()):
        return
    op.create_table(
        "platform_settings",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("sedania_charge_pct", sa.Numeric(10, 6), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_by_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["updated_by_id"], ["ops_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "platform_settings" not in set(inspector.get_table_names()):
        return
    op.drop_table("platform_settings")
