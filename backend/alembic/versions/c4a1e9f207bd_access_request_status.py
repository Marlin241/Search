"""access_request status + invite_code

Revision ID: c4a1e9f207bd
Revises: b7e2f4a91c3d
Create Date: 2026-09-01 14:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4a1e9f207bd"
down_revision: str | Sequence[str] | None = "b7e2f4a91c3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "access_requests",
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "access_requests",
        sa.Column("invite_code", sa.String(length=64), nullable=True),
    )
    # Les lignes déjà traitées (ancien schéma : handled_at non nul) sont
    # rétro-classées "approved" — c'était le seul geste possible avant.
    op.execute(
        "UPDATE access_requests SET status = 'approved' WHERE handled_at IS NOT NULL"
    )
    op.create_index(
        "ix_access_requests_status", "access_requests", ["status"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_access_requests_status", table_name="access_requests")
    op.drop_column("access_requests", "invite_code")
    op.drop_column("access_requests", "status")
