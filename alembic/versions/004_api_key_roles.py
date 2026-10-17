"""Add RBAC role column to api_keys."""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "api_keys" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("api_keys")}
    if "role" not in existing:
        op.add_column(
            "api_keys",
            sa.Column("role", sa.String(length=32), nullable=False, server_default="institution_ops"),
        )
        op.create_index("ix_api_keys_role", "api_keys", ["role"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "api_keys" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("api_keys")}
    if "role" in existing:
        op.drop_index("ix_api_keys_role", table_name="api_keys")
        op.drop_column("api_keys", "role")
