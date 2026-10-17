"""Add is_mno_pool flag to third_party_brokers."""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "third_party_brokers" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("third_party_brokers")}
    if "is_mno_pool" not in existing:
        op.add_column(
            "third_party_brokers",
            sa.Column("is_mno_pool", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "third_party_brokers" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("third_party_brokers")}
    if "is_mno_pool" in existing:
        op.drop_column("third_party_brokers", "is_mno_pool")
