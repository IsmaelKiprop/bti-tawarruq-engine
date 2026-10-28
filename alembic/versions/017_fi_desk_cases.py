"""FI Ops origination desk cases.

Revision ID: 017
Revises: 016
Create Date: 2026-10-28
"""

from alembic import op
import sqlalchemy as sa

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "fi_desk_cases" in set(inspector.get_table_names()):
        return
    op.create_table(
        "fi_desk_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("institution_id", sa.String(length=36), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assigned_approver_id", sa.String(length=36), nullable=True),
        sa.Column("requested_by_id", sa.String(length=36), nullable=True),
        sa.Column("approval_comments", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("otp_purpose", sa.String(length=32), nullable=True),
        sa.Column("otp_hash", sa.String(length=64), nullable=True),
        sa.Column("otp_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(["assigned_approver_id"], ["ops_users.id"]),
        sa.ForeignKeyConstraint(["requested_by_id"], ["ops_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fi_desk_cases_institution_id", "fi_desk_cases", ["institution_id"])
    op.create_index("ix_fi_desk_cases_status", "fi_desk_cases", ["status"])
    op.create_index("ix_fi_desk_cases_assigned_approver_id", "fi_desk_cases", ["assigned_approver_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "fi_desk_cases" not in set(inspector.get_table_names()):
        return
    op.drop_index("ix_fi_desk_cases_assigned_approver_id", table_name="fi_desk_cases")
    op.drop_index("ix_fi_desk_cases_status", table_name="fi_desk_cases")
    op.drop_index("ix_fi_desk_cases_institution_id", table_name="fi_desk_cases")
    op.drop_table("fi_desk_cases")
