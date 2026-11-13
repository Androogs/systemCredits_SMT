"""Seed del listado Fratelli en el catálogo de vehículos.

Revision ID: 0028_vehiculo_catalogo_fratelli
Revises: 0027_vehiculo_catalogo_akt
Create Date: 2026-11-06

Carga las 16 entradas de la hoja «IMPRIMIR» de la «LISTA DE PRECIOS
NOVIEMBRE 2026» de Fratelli — la lista pública, no la de mayoreo.
Cada fila es referencia + año modelo porque el bono de fábrica cambia
por año (FTR100 2025 → $500.000; FTR100 2026 → $400.000), así que la
referencia queda "FTR100 2025", etc.

- `precio_lista` = columna PRECIO (PVP).
- `bono_pesos` = bono de fábrica del año modelo (el que descuenta
  «PRECIO FINAL»). El BONO PROGRESER adicional ($300.000 en todas) es
  una campaña condicionada — no se precarga, el asesor lo suma a mano
  en el descuento si aplica.
- `soat`/`matricula`/`impuesto` quedan NULL: la hoja trae un paquete
  «PAPELES» ($869.000 / $900.000) sin desagregar; inventar la división
  metería datos erróneos — el asesor los digita.

Idempotente: ON CONFLICT (marca, referencia) DO NOTHING.
"""

import sqlalchemy as sa
from alembic import op


revision = "0028_vehiculo_catalogo_fratelli"
down_revision = "0027_vehiculo_catalogo_akt"
branch_labels = None
depends_on = None

VIGENCIA_NOV_2026 = "2026-11"

# referencia, precio_lista, bono_pesos
FRATELLI_NOV_2026 = [
    ("FTR100 2025", 4_590_000, 500_000),
    ("FTR100 2026", 4_590_000, 400_000),
    ("FTR125 CBS 2026", 4_690_000, 400_000),
    ("FTR125 CBS 2027", 4_790_000, 400_000),
    ("FT125 CBS 2026", 5_149_000, 250_000),
    ("FT125 CBS 2027", 5_199_000, 200_000),
    ("FS 125 2027", 5_890_000, 400_000),
    ("SFX160 2026", 13_890_000, 900_000),
    ("SFX160 2027", 14_390_000, 1_100_000),
    ("SFR125 CBS 2026", 7_290_000, 300_000),
    ("SFR125 CBS 2027", 7_790_000, 600_000),
    ("SFR125 SPORT 2027", 7_790_000, 300_000),
    ("SFRX125 2026", 7_790_000, 400_000),
    ("SFRX125 2027", 7_990_000, 400_000),
    ("XE125 CBS 2026", 7_790_000, 300_000),
    ("XE125 CBS 2027", 7_990_000, 300_000),
]


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO vehiculo_catalogo
                (marca, referencia, precio_lista, bono_pesos, vigencia)
            VALUES
                (:marca, :referencia, :precio_lista, :bono_pesos, :vigencia)
            ON CONFLICT (marca, referencia) DO NOTHING
            """
        ),
        [
            {
                "marca": "Fratelli",
                "referencia": ref,
                "precio_lista": precio,
                "bono_pesos": bono,
                "vigencia": VIGENCIA_NOV_2026,
            }
            for ref, precio, bono in FRATELLI_NOV_2026
        ],
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "DELETE FROM vehiculo_catalogo "
            "WHERE marca = 'Fratelli' AND vigencia = :vigencia"
        ),
        {"vigencia": VIGENCIA_NOV_2026},
    )
