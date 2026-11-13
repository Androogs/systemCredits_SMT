"""Ficha del usuario: sede del catálogo de la marca.

Revision ID: 0034_usuario_sede
Revises: 0033_usuario_ficha
Create Date: 2026-03-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034_usuario_sede"
down_revision: str | None = "0033_usuario_ficha"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("usuario", sa.Column("sede", sa.String(120)))


def downgrade() -> None:
    op.drop_column("usuario", "sede")
