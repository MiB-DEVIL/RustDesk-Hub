"""Base OpenDesk Hub v0.8.0

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cette migration sert de point de départ.
    # Les installations existantes seront marquées avec `alembic stamp head`.
    # Les nouvelles installations continueront à créer leurs tables via SQLAlchemy.
    pass


def downgrade() -> None:
    pass
