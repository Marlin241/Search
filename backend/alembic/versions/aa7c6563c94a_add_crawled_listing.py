"""add crawled_listing

Revision ID: aa7c6563c94a
Revises: 9c3b2b7e5a41
Create Date: 2026-08-28 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aa7c6563c94a"
down_revision: str | Sequence[str] | None = "9c3b2b7e5a41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "crawled_listing",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column("salary", sa.String(length=255), nullable=True),
        sa.Column("contract_type", sa.String(length=64), nullable=True),
        sa.Column(
            "is_remote", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "missed_crawls", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
    )
    op.create_index("ix_crawled_listing_url", "crawled_listing", ["url"], unique=True)
    op.create_index("ix_crawled_listing_source", "crawled_listing", ["source"])
    op.create_index(
        "ix_crawled_listing_last_seen_at", "crawled_listing", ["last_seen_at"]
    )
    op.create_index("ix_crawled_listing_is_active", "crawled_listing", ["is_active"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_crawled_listing_is_active", table_name="crawled_listing")
    op.drop_index("ix_crawled_listing_last_seen_at", table_name="crawled_listing")
    op.drop_index("ix_crawled_listing_source", table_name="crawled_listing")
    op.drop_index("ix_crawled_listing_url", table_name="crawled_listing")
    op.drop_table("crawled_listing")
