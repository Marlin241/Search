"""split full_name into first_name and last_name

Revision ID: 9c3b2b7e5a41
Revises: 4afb7f1be9a4
Create Date: 2026-08-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c3b2b7e5a41'
down_revision: Union[str, Sequence[str], None] = '4afb7f1be9a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'candidate_profiles',
        sa.Column('first_name', sa.String(length=255), nullable=False, server_default=''),
    )
    op.add_column(
        'candidate_profiles',
        sa.Column('last_name', sa.String(length=255), nullable=False, server_default=''),
    )

    # Backfill from the existing full_name: split on the first whitespace run.
    connection = op.get_bind()
    candidate_profiles = sa.table(
        'candidate_profiles',
        sa.column('id', sa.Integer),
        sa.column('full_name', sa.String),
        sa.column('first_name', sa.String),
        sa.column('last_name', sa.String),
    )
    for row in connection.execute(
        sa.select(candidate_profiles.c.id, candidate_profiles.c.full_name)
    ):
        full_name = (row.full_name or "").strip()
        if not full_name:
            continue
        parts = full_name.split(None, 1)
        first = parts[0]
        last = parts[1] if len(parts) > 1 else ""
        connection.execute(
            candidate_profiles.update()
            .where(candidate_profiles.c.id == row.id)
            .values(first_name=first, last_name=last)
        )

    op.alter_column('candidate_profiles', 'first_name', server_default=None)
    op.alter_column('candidate_profiles', 'last_name', server_default=None)
    op.drop_column('candidate_profiles', 'full_name')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'candidate_profiles',
        sa.Column('full_name', sa.String(length=255), nullable=False, server_default=''),
    )

    connection = op.get_bind()
    candidate_profiles = sa.table(
        'candidate_profiles',
        sa.column('id', sa.Integer),
        sa.column('full_name', sa.String),
        sa.column('first_name', sa.String),
        sa.column('last_name', sa.String),
    )
    for row in connection.execute(
        sa.select(
            candidate_profiles.c.id,
            candidate_profiles.c.first_name,
            candidate_profiles.c.last_name,
        )
    ):
        full_name = f"{row.first_name or ''} {row.last_name or ''}".strip()
        connection.execute(
            candidate_profiles.update()
            .where(candidate_profiles.c.id == row.id)
            .values(full_name=full_name)
        )

    op.alter_column('candidate_profiles', 'full_name', server_default=None)
    op.drop_column('candidate_profiles', 'last_name')
    op.drop_column('candidate_profiles', 'first_name')
