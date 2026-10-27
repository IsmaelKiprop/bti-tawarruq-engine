"""Store issued API client key for FI Admin copy.

Revision ID: 016
Revises: 015
Create Date: 2026-10-27
"""

from alembic import op
import sqlalchemy as sa

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "api_keys" not in tables:
        return
    cols = {col["name"] for col in inspector.get_columns("api_keys")}
    if "reveal_key" not in cols:
        op.add_column("api_keys", sa.Column("reveal_key", sa.String(length=128), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "api_keys" not in tables:
        return
    cols = {col["name"] for col in inspector.get_columns("api_keys")}
    if "reveal_key" in cols:
        op.drop_column("api_keys", "reveal_key")
