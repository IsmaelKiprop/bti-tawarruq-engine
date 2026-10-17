"""Alembic migration: immutable Shariah audit ledger columns."""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "shariah_audit_logs" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("shariah_audit_logs")}

    columns = [
        ("verified_at", sa.DateTime(timezone=True), True),
        ("mno_receipt_id", sa.String(128), True),
        ("institution_id", sa.String(36), True),
        ("transaction_id", sa.String(36), True),
        ("application_id", sa.String(36), True),
        ("previous_hash", sa.String(64), False),
        ("entry_hash", sa.String(64), False),
    ]
    for name, col_type, nullable in columns:
        if name not in existing:
            op.add_column("shariah_audit_logs", sa.Column(name, col_type, nullable=nullable))

    if "previous_hash" not in existing:
        op.execute(sa.text("UPDATE shariah_audit_logs SET previous_hash = :g WHERE previous_hash IS NULL").bindparams(g="0" * 64))
    if "entry_hash" not in existing:
        op.execute(sa.text("UPDATE shariah_audit_logs SET entry_hash = payload_hash WHERE entry_hash IS NULL"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "shariah_audit_logs" not in inspector.get_table_names():
        return
    for name in (
        "verified_at",
        "mno_receipt_id",
        "institution_id",
        "transaction_id",
        "application_id",
        "previous_hash",
        "entry_hash",
    ):
        existing = {col["name"] for col in inspector.get_columns("shariah_audit_logs")}
        if name in existing:
            op.drop_column("shariah_audit_logs", name)
