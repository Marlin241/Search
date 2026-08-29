"""add user consent columns

Revision ID: c85fccec5431
Revises: 9b7ead314d4b
Create Date: 2026-08-29 18:45:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c85fccec5431"
down_revision: str | Sequence[str] | None = "9b7ead314d4b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users", sa.Column("consent_accepted_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "users", sa.Column("consent_version", sa.String(length=16), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "consent_version")
    op.drop_column("users", "consent_accepted_at")
