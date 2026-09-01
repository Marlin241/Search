"""add access_request

Revision ID: b7e2f4a91c3d
Revises: 99fe683ffb98
Create Date: 2026-08-30 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e2f4a91c3d"
down_revision: str | Sequence[str] | None = "99fe683ffb98"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "access_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_ip", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("handled_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_access_requests_email", "access_requests", ["email"])
    op.create_index(
        "ix_access_requests_created_at", "access_requests", ["created_at"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_access_requests_created_at", table_name="access_requests")
    op.drop_index("ix_access_requests_email", table_name="access_requests")
    op.drop_table("access_requests")
