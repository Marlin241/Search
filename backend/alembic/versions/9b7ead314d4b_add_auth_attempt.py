"""add auth_attempt

Revision ID: 9b7ead314d4b
Revises: 264a111a689c
Create Date: 2026-08-29 18:40:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9b7ead314d4b"
down_revision: str | Sequence[str] | None = "264a111a689c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "auth_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("identifier", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_auth_attempts_action", "auth_attempts", ["action"])
    op.create_index(
        "ix_auth_attempts_identifier", "auth_attempts", ["identifier"]
    )
    op.create_index(
        "ix_auth_attempts_created_at", "auth_attempts", ["created_at"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_auth_attempts_created_at", table_name="auth_attempts")
    op.drop_index("ix_auth_attempts_identifier", table_name="auth_attempts")
    op.drop_index("ix_auth_attempts_action", table_name="auth_attempts")
    op.drop_table("auth_attempts")
