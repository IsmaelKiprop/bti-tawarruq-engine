"""Initial schema — creates all tables from SQLAlchemy models."""

from alembic import op
from tawarruq.database import Base
from tawarruq import models  # noqa: F401

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
