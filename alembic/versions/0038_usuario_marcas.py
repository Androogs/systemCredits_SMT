"""Marcas múltiples por usuario (ficha general).

Revision ID: 0038_usuario_marcas
Revises: 0037_concesionario_marcas
Create Date: 2026-11-11

Un usuario puede atender varias marcas de moto. ``usuario_marca`` guarda
el conjunto completo; ``usuario.marca`` queda como la principal (la
primera del conjunto) para no romper la semántica de ``usuario.sede`` ni
los lectores legados. El alta migra la marca existente a la tabla
puente.
"""

import sqlalchemy as sa
from alembic import op


revision = "0038_usuario_marcas"
down_revision = "0037_concesionario_marcas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usuario_marca",
        sa.Column(
            "id_usuario",
            sa.Uuid(),
            sa.ForeignKey("usuario.id_usuario", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("marca", sa.String(120), primary_key=True),
        sa.Column(
            "fecha_asignacion",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # La marca única que ya tenía la ficha pasa a ser su conjunto.
    op.execute(
        "INSERT INTO usuario_marca (id_usuario, marca) "
        "SELECT id_usuario, trim(marca) FROM usuario "
        "WHERE marca IS NOT NULL AND trim(marca) <> ''"
    )


def downgrade() -> None:
    op.drop_table("usuario_marca")
