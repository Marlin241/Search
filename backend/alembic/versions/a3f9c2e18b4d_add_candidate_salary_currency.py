"""add candidate salary currency

Revision ID: a3f9c2e18b4d
Revises: c4a1e9f207bd
Create Date: 2026-09-05 14:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f9c2e18b4d"
down_revision: str | Sequence[str] | None = "c4a1e9f207bd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "candidate_profiles",
        sa.Column("salary_currency", sa.String(length=3), nullable=True),
    )
    # Les profils existants avec une fourchette de salaire déjà renseignée
    # la supposaient implicitement en FCFA (XOF) - on aligne les données pour
    # que le scoring de compatibilité continue de les évaluer normalement.
    op.execute(
        "UPDATE candidate_profiles SET salary_currency = 'XOF' "
        "WHERE salary_min IS NOT NULL OR salary_max IS NOT NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("candidate_profiles", "salary_currency")
