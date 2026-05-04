"""add display_name to users

Revision ID: 3a1c5f8e2d9b
Revises: 2f8b4c9d3e7a
Create Date: 2026-04-30 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "3a1c5f8e2d9b"
down_revision: Union[str, Sequence[str], None] = "2f8b4c9d3e7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(length=150), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "display_name")
