"""Alembic: customer_name + currency on financing_applications for Bursa desk packets."""

from alembic import op
import sqlalchemy as sa


revision = "005_application_desk_fields"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("financing_applications") as batch:
        batch.add_column(sa.Column("customer_name", sa.String(length=256), nullable=True))
        batch.add_column(sa.Column("currency", sa.String(length=8), nullable=False, server_default="KES"))


def downgrade() -> None:
    with op.batch_alter_table("financing_applications") as batch:
        batch.drop_column("currency")
        batch.drop_column("customer_name")
