"""Trazabilidad del cargue de garantías al SGM (RUNT Pro).

Revision ID: 0031_garantia_runt_exportacion
Revises: 0030_vehiculo_catalogo_tvs
Create Date: 2026-11-08

Operaciones exporta las prendas de las solicitudes facturadas/
desembolsadas a un Excel multi-hoja para cargue masivo en RUNT Pro;
el backend marca cada garantía incluida para que un segundo clic no
la repita (el SGM rechaza duplicados).

- garantia_runt_exportada_en: cuándo entró la prenda en un archivo.
- garantia_runt_lote: el lote que la incluyó ("SGM-AAAAMMDD-HHMM");
  permite regenerar un archivo anterior con incluir_exportadas.
"""

import sqlalchemy as sa
from alembic import op


revision = "0031_garantia_runt_exportacion"
down_revision = "0030_vehiculo_catalogo_tvs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "solicitud_credito",
        sa.Column(
            "garantia_runt_exportada_en",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "solicitud_credito",
        sa.Column("garantia_runt_lote", sa.String(30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("solicitud_credito", "garantia_runt_lote")
    op.drop_column("solicitud_credito", "garantia_runt_exportada_en")
