"""add llm_call_log

Revision ID: fd00424a560e
Revises: df168a59e28b
Create Date: 2026-08-29 19:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fd00424a560e"
down_revision: str | Sequence[str] | None = "df168a59e28b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "llm_call_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("feature", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_llm_call_logs_user_id", "llm_call_logs", ["user_id"])
    op.create_index("ix_llm_call_logs_feature", "llm_call_logs", ["feature"])
    op.create_index(
        "ix_llm_call_logs_created_at", "llm_call_logs", ["created_at"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_llm_call_logs_created_at", table_name="llm_call_logs")
    op.drop_index("ix_llm_call_logs_feature", table_name="llm_call_logs")
    op.drop_index("ix_llm_call_logs_user_id", table_name="llm_call_logs")
    op.drop_table("llm_call_logs")
