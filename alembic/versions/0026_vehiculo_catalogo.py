"""Catálogo de vehículos financiables con precio de lista.

Revision ID: 0026_vehiculo_catalogo
Revises: 0025_factura_vehiculo
Create Date: 2026-11-06

`vehiculo_catalogo` trae el listado de precios vigente por marca y
referencia: el asesor elige la moto en la etapa 5 de originación y el
formulario precarga valor de la moto, bono en pesos, SOAT, matrícula e
impuesto de rodamiento — el mismo desglose de la hoja de negocio.

Seed: listado Suzuki vigencia octubre 2026 (precio de lista, SOAT,
matrícula e impuesto final; `bono_pesos` solo cuando el bono es en
dinero — el bono "SOAT" ya va descontado en la columna `soat`).

Idempotente: CREATE TABLE IF NOT EXISTS + ON CONFLICT DO NOTHING.
"""

import sqlalchemy as sa
from alembic import op


revision = "0026_vehiculo_catalogo"
down_revision = "0025_factura_vehiculo"
branch_labels = None
depends_on = None

VIGENCIA_OCT_2026 = "2026-10"

# referencia, precio_lista, bono_pesos, soat, matricula, impuesto
SUZUKI_OCT_2026 = [
    ("ADDRESS NM", 7_990_000, None, 423_300, 350_000, None),
    ("AVENIS", 9_699_000, None, 423_300, 350_000, None),
    ("BURGMAN FI 125", 10_890_000, None, 423_300, 350_000, None),
    ("BURGMAN FI 150 (LANZAMIENTO)", 15_550_000, None, 423_300, 350_000, 70_000),
    ("VIVA FI ABS", 9_999_500, 500_000, 423_300, 350_000, None),
    ("AX4 ABS", 6_350_000, None, 25_000, 350_000, None),
    ("GN 125 ABS", 7_419_000, None, 25_000, 350_000, None),
    ("GN 160 (LANZAMIENTO)", 10_630_000, None, 423_300, 350_000, 54_000),
    ("GSX-S150 ABS (2027)", 11_990_000, None, 423_300, 350_000, 58_000),
    ("GSX-R ABS (2027)", 13_990_000, None, 423_300, 350_000, 65_000),
    ("GIXXER FI ABS", 11_390_000, None, 25_000, 350_000, 56_000),
    ("GIXER SF FI (2027)", 12_990_000, None, 423_300, 350_000, 61_000),
    ("DR 150 CARBURADA ABS", 10_990_000, None, 25_000, 350_000, 55_000),
    ("DR 160X", 12_999_000, None, 423_300, 350_000, 61_000),
    ("V-STROM 160 (2026-2027)", 13_490_000, None, 25_000, 350_000, 63_000),
    ("GIXXER 250", 14_990_000, None, 841_400, 350_000, 65_000),
    ("GIXXER SF 250", 15_990_000, None, 841_400, 350_000, 68_000),
    ("VSTROM 250SX (2027)", 20_990_000, None, 841_400, 350_000, 82_000),
    ("DR-Z4S", 50_000_000, None, 841_400, 350_000, 168_000),
    ("DR-Z4SM", 50_000_000, None, 841_400, 350_000, 168_000),
    ("V-STROM 800 DE", 69_390_000, None, 841_400, 350_000, 225_000),
    ("GSX-S1000", 77_990_000, None, 841_400, 350_000, 251_000),
]


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS vehiculo_catalogo (
            id_vehiculo_catalogo SERIAL PRIMARY KEY,
            marca VARCHAR(60) NOT NULL,
            referencia VARCHAR(120) NOT NULL,
            precio_lista NUMERIC(18,2) NOT NULL,
            bono_pesos NUMERIC(18,2),
            soat NUMERIC(18,2),
            matricula NUMERIC(18,2),
            impuesto NUMERIC(18,2),
            vigencia VARCHAR(30),
            activo BOOLEAN NOT NULL DEFAULT TRUE,
            CONSTRAINT uq_vehiculo_catalogo UNIQUE (marca, referencia)
        )
        """
    )
    # SQL literal: ON CONFLICT DO NOTHING va al final del INSERT y lo
    # entienden tanto Postgres como SQLite moderno (upsert portable).
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO vehiculo_catalogo
                (marca, referencia, precio_lista, bono_pesos,
                 soat, matricula, impuesto, vigencia)
            VALUES
                (:marca, :referencia, :precio_lista, :bono_pesos,
                 :soat, :matricula, :impuesto, :vigencia)
            ON CONFLICT (marca, referencia) DO NOTHING
            """
        ),
        [
            {
                "marca": "Suzuki",
                "referencia": ref,
                "precio_lista": precio,
                "bono_pesos": bono,
                "soat": soat,
                "matricula": matricula,
                "impuesto": impuesto,
                "vigencia": VIGENCIA_OCT_2026,
            }
            for ref, precio, bono, soat, matricula, impuesto in SUZUKI_OCT_2026
        ],
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS vehiculo_catalogo")
