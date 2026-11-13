"""Ficha general del usuario: cédula, marca y observaciones.

La cédula existía solo en la ficha de asesor; ahora también vive en
`usuario` para que cualquier rol la registre. Marca y observaciones
son datos libres del admin (p. ej. relevo de personal).

Revision ID: 0033_usuario_ficha
Revises: 0032_origen_solicitud
Create Date: 2026-03-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033_usuario_ficha"
down_revision: str | None = "0032_origen_solicitud"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("usuario", sa.Column("cedula", sa.String(40)))
    op.add_column("usuario", sa.Column("marca", sa.String(120)))
    op.add_column("usuario", sa.Column("observaciones", sa.Text()))


def downgrade() -> None:
    op.drop_column("usuario", "observaciones")
    op.drop_column("usuario", "marca")
    op.drop_column("usuario", "cedula")
