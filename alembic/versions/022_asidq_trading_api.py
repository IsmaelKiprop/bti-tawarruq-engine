"""As-Sidq trading ref, callback payload, and certificate numbers.

Revision ID: 022
Revises: 021
Create Date: 2026-11-02
"""

from alembic import op
import sqlalchemy as sa

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None

COLUMNS = (
    ("as_sidq_ref_no", sa.Column("as_sidq_ref_no", sa.String(100), nullable=True)),
    ("as_sidq_status_code", sa.Column("as_sidq_status_code", sa.Integer(), nullable=True)),
    ("as_sidq_status_desc", sa.Column("as_sidq_status_desc", sa.String(100), nullable=True)),
    ("as_sidq_trading_status", sa.Column("as_sidq_trading_status", sa.String(100), nullable=True)),
    ("as_sidq_product_code", sa.Column("as_sidq_product_code", sa.String(30), nullable=True)),
    ("as_sidq_cert_url", sa.Column("as_sidq_cert_url", sa.String(512), nullable=True)),
    ("as_sidq_cert_a", sa.Column("as_sidq_cert_a", sa.String(100), nullable=True)),
    ("as_sidq_cert_b", sa.Column("as_sidq_cert_b", sa.String(100), nullable=True)),
    ("as_sidq_cert_c", sa.Column("as_sidq_cert_c", sa.String(100), nullable=True)),
    ("as_sidq_callback_json", sa.Column("as_sidq_callback_json", sa.Text(), nullable=True)),
    ("as_sidq_cancel_reason", sa.Column("as_sidq_cancel_reason", sa.String(50), nullable=True)),
    ("as_sidq_cancel_request_id", sa.Column("as_sidq_cancel_request_id", sa.String(32), nullable=True)),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tawarruq_executions" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("tawarruq_executions")}
    for name, column in COLUMNS:
        if name not in existing:
            op.add_column("tawarruq_executions", column)
    indexes = {idx["name"] for idx in inspector.get_indexes("tawarruq_executions")}
    if "ix_tawarruq_executions_as_sidq_ref_no" not in indexes:
        op.create_index("ix_tawarruq_executions_as_sidq_ref_no", "tawarruq_executions", ["as_sidq_ref_no"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tawarruq_executions" not in inspector.get_table_names():
        return
    indexes = {idx["name"] for idx in inspector.get_indexes("tawarruq_executions")}
    if "ix_tawarruq_executions_as_sidq_ref_no" in indexes:
        op.drop_index("ix_tawarruq_executions_as_sidq_ref_no", table_name="tawarruq_executions")
    existing = {col["name"] for col in inspector.get_columns("tawarruq_executions")}
    for name, _column in reversed(COLUMNS):
        if name in existing:
            op.drop_column("tawarruq_executions", name)
