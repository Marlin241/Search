"""add user quota_overrides

Revision ID: e07136365389
Revises: fd00424a560e
Create Date: 2026-08-29 19:31:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e07136365389"
down_revision: str | Sequence[str] | None = "fd00424a560e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("quota_overrides", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "quota_overrides")
