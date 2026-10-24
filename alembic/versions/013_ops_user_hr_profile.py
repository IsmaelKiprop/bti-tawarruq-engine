"""Ops user HR / profile fields for portal management.

Revision ID: 013
Revises: 012
Create Date: 2026-10-24
"""

from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "ops_users" not in tables:
        return
    cols = {col["name"] for col in inspector.get_columns("ops_users")}
    additions = [
        ("job_title", sa.Column("job_title", sa.String(length=128), nullable=True)),
        ("department", sa.Column("department", sa.String(length=128), nullable=True)),
        ("employee_number", sa.Column("employee_number", sa.String(length=64), nullable=True)),
        ("phone", sa.Column("phone", sa.String(length=64), nullable=True)),
        ("office", sa.Column("office", sa.String(length=128), nullable=True)),
    ]
    for name, column in additions:
        if name not in cols:
            op.add_column("ops_users", column)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "ops_users" not in tables:
        return
    cols = {col["name"] for col in inspector.get_columns("ops_users")}
    for name in ("office", "phone", "employee_number", "department", "job_title"):
        if name in cols:
            op.drop_column("ops_users", name)
