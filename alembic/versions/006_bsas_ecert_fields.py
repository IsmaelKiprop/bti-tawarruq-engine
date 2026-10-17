"""Alembic: richer Bursa e-certificate fields + PDF path."""

from alembic import op
import sqlalchemy as sa


revision = "006_bsas_ecert_fields"
down_revision = "005_application_desk_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("certificates") as batch:
        batch.add_column(sa.Column("seller", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("buyer", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("bid_no", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("selling_time", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("selling_date", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("value_date", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("product_code", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("product_description", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("unit", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("volume", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("currency", sa.String(length=8), nullable=True))
        batch.add_column(sa.Column("price", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("price_myr_equivalent", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("value_amount", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("transaction_type", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("pdf_path", sa.String(length=512), nullable=True))
        batch.add_column(sa.Column("pdf_filename", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("details_json", sa.Text(), nullable=True))


def downgrade() -> None:
    cols = [
        "seller",
        "buyer",
        "bid_no",
        "selling_time",
        "selling_date",
        "value_date",
        "product_code",
        "product_description",
        "unit",
        "volume",
        "currency",
        "price",
        "price_myr_equivalent",
        "value_amount",
        "transaction_type",
        "pdf_path",
        "pdf_filename",
        "details_json",
    ]
    with op.batch_alter_table("certificates") as batch:
        for col in cols:
            batch.drop_column(col)
