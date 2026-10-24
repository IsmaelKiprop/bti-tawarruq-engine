"""Audit ops scoping: institution, actor user, request group, HTTP context.

Revision ID: 014
Revises: 013
Create Date: 2026-10-24
"""

from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "audit_events" not in tables:
        return
    cols = {col["name"] for col in inspector.get_columns("audit_events")}
    additions = [
        ("institution_id", sa.Column("institution_id", sa.String(length=36), nullable=True)),
        ("actor_user_id", sa.Column("actor_user_id", sa.String(length=36), nullable=True)),
        ("group_id", sa.Column("group_id", sa.String(length=36), nullable=True)),
        ("action_group", sa.Column("action_group", sa.String(length=64), nullable=True)),
        ("http_method", sa.Column("http_method", sa.String(length=16), nullable=True)),
        ("http_path", sa.Column("http_path", sa.String(length=512), nullable=True)),
        ("http_status", sa.Column("http_status", sa.Integer(), nullable=True)),
    ]
    for name, column in additions:
        if name not in cols:
            op.add_column("audit_events", column)
    # Indexes (best-effort; ignore if already present)
    try:
        op.create_index("ix_audit_events_institution_id", "audit_events", ["institution_id"])
    except Exception:
        pass
    try:
        op.create_index("ix_audit_events_group_id", "audit_events", ["group_id"])
    except Exception:
        pass
    try:
        op.create_index("ix_audit_events_action_group", "audit_events", ["action_group"])
    except Exception:
        pass


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "audit_events" not in tables:
        return
    cols = {col["name"] for col in inspector.get_columns("audit_events")}
    for index in ("ix_audit_events_action_group", "ix_audit_events_group_id", "ix_audit_events_institution_id"):
        try:
            op.drop_index(index, table_name="audit_events")
        except Exception:
            pass
    for name in (
        "http_status",
        "http_path",
        "http_method",
        "action_group",
        "group_id",
        "actor_user_id",
        "institution_id",
    ):
        if name in cols:
            op.drop_column("audit_events", name)
