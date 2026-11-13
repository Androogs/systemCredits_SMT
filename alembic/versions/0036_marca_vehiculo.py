"""Catálogo de marcas aliadas (Ajustes → Concesionarios).

Revision ID: 0036_marca_vehiculo
Revises: 0035_rngm_archivo_lote
Create Date: 2026-11-11

Las marcas del resumen de concesionarios emergen de vehiculo_catalogo y
producto_vehiculo, pero el admin necesita dar de alta una marca antes de
que tenga precios o radicaciones. ``marca_vehiculo`` persiste ese alta;
el resumen la une con las otras dos fuentes.
"""

import sqlalchemy as sa
from alembic import op


revision = "0036_marca_vehiculo"
down_revision = "0035_rngm_archivo_lote"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marca_vehiculo",
        sa.Column("id_marca", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("nombre", sa.String(100), nullable=False, unique=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_table("marca_vehiculo")
