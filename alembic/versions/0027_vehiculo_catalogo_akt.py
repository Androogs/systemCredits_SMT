"""Seed del listado AKT en el catálogo de vehículos.

Revision ID: 0027_vehiculo_catalogo_akt
Revises: 0026_vehiculo_catalogo
Create Date: 2026-11-06

Carga las 58 referencias del listado «PRECIOS PAP NOVIEMBRE 2026» de
AKT (una fila por variante de color: el precio cambia entre variantes
del mismo modelo, p. ej. AK125TTR CBS Ng 7.790.000 vs G/N/V 8.200.000).
Incluye las líneas VOGE/Karguero/Tuk Tuk que AKT comercializa bajo su
mismo listado — quedan con marca 'AKT' para que el select de la oferta
las muestre al elegir esa marca.

Idempotente: ON CONFLICT (marca, referencia) DO NOTHING.
"""

import sqlalchemy as sa
from alembic import op


revision = "0027_vehiculo_catalogo_akt"
down_revision = "0026_vehiculo_catalogo"
branch_labels = None
depends_on = None

VIGENCIA_NOV_2026 = "2026-11"

# referencia, precio_lista, bono_pesos, soat, matricula, impuesto
AKT_NOV_2026 = [
    ("Moto AK125NKD CLASICA 27 PT", 6_090_000, 1_000_000, 428_300, 450_000, None),
    ("Moto AK125NKD FP 27 PT", 6_490_000, 1_000_000, 428_300, 450_000, None),
    ("AK125NKD+ GR 27 PT (NUEVA)", 5_490_000, 500_000, 428_300, 450_000, None),
    ("AK125NKD+ VE/AZ 27 PT (NUEVA)", 5_490_000, 500_000, 428_300, 450_000, None),
    ("AK125NKD+ NG 27 PT (NUEVA)", 5_490_000, 500_000, 428_300, 450_000, None),
    ("AK125NKD+ BL 27 PT (NUEVA)", 5_490_000, 500_000, 428_300, 450_000, None),
    ("125NKD+ MOR 27 PT (NUEVA)", 5_490_000, 500_000, 428_300, 450_000, None),
    ("Moto AK125 CHR CBS AZUL 27 PT", 5_990_000, 500_000, 428_300, 450_000, None),
    ("Moto AK125 CHR CBS Ng 27 PT", 5_990_000, 500_000, 428_300, 450_000, None),
    ("Moto AK125 CHR CBS Rj 27 PT", 5_990_000, 500_000, 428_300, 450_000, None),
    ("Moto AK125CR4 CBS G/Mt 27 PT", 6_990_000, 500_000, 428_300, 450_000, None),
    ("Moto AK125CR4 CBS N/Br 27 PT", 6_990_000, 500_000, 428_300, 450_000, None),
    ("Moto AK125CR4 CBS N/Mt 27 PT", 6_990_000, 500_000, 428_300, 450_000, None),
    ("Moto AK150CR4 CBS Ng V 27 PT", 7_590_000, 500_000, 428_300, 450_000, 45_000),
    ("Moto AK150CR4 CBS N/Mt V 27 PT", 7_590_000, 500_000, 428_300, 450_000, 45_000),
    ("Moto AK150CR4 CBS G/Mt V 27 PT", 7_590_000, 500_000, 428_300, 450_000, 45_000),
    ("MOTO AK200CR4 DNP N/BR 27 PT", 8_990_000, 500_000, 428_300, 450_000, 50_000),
    ("MOTO AK200CR4 DNP N/MT 27 PT", 8_990_000, 500_000, 846_400, 450_000, 50_000),
    ("MOTO AK200CR4 DNP GR 27 PT", 8_990_000, 500_000, 846_400, 450_000, 50_000),
    ("Moto AK250EFI Ng/Mt 27 PT", 11_990_000, 500_000, 846_400, 450_000, 60_000),
    ("Moto AK250EFI BCO 27 PT", 11_990_000, 500_000, 846_400, 450_000, 60_000),
    ("Moto AK250EFI Gr 27 PT", 11_990_000, 500_000, 846_400, 450_000, 60_000),
    ("Moto AK110NV CBS GRIS LED (NUEVA)", 5_690_000, 400_000, 428_300, 450_000, None),
    ("Moto AK110NV CBS AZUL LED (NUEVA)", 5_690_000, 400_000, 428_300, 450_000, None),
    ("Moto AK110NV CBS NEGRO LED (NUEVA)", 5_690_000, 400_000, 428_300, 450_000, None),
    ("Moto AK125FLEX CBS N/Mt 27 PT", 6_290_000, 400_000, 428_300, 450_000, None),
    ("Moto AK125FLEX CBS Ng 27 PT", 6_290_000, 400_000, 428_300, 450_000, None),
    ("Moto AK125FLEX CBS G/Mt 27 PT", 6_290_000, 400_000, 428_300, 450_000, None),
    ("Moto AK125FLEX CBS MLT 27 PT", 6_490_000, 400_000, 428_300, 450_000, None),
    ("Moto AK150JET EVO Neg 27 PT", 12_990_000, 400_000, 428_300, 450_000, 65_000),
    ("Moto AK150JET EVO Gris 27 PT", 12_990_000, 400_000, 428_300, 450_000, 65_000),
    ("Moto AK150DYN RX Neg 27 PT", 9_890_000, 400_000, 428_300, 450_000, 52_000),
    ("Moto AK150DYN RX Gr/Mt 27 PT", 9_890_000, 400_000, 428_300, 450_000, 52_000),
    ("Moto AK150DYN RX Gr/Br 27 PT", 9_890_000, 400_000, 428_300, 450_000, 52_000),
    ("Moto voge AK XRS 180 Gr/Br 27PT", 13_990_000, None, 428_300, 450_000, 65_000),
    ("Moto voge AK XRS 180 Neg/Br 27PT", 13_990_000, None, 428_300, 450_000, 65_000),
    ("Moto voge AK XRS 180 Bl/Br 27PT", 13_990_000, None, 428_300, 450_000, 65_000),
    ("Moto AK125DYN PRO+ N/Mt 27 PT", 8_490_000, 400_000, 428_300, 450_000, None),
    ("Moto AK125DYN PRO+ N/Br 27 PT", 8_490_000, 400_000, 428_300, 450_000, None),
    ("Moto AK125DYN PRO+ G/Ver 26 PT", 8_490_000, 400_000, 428_300, 450_000, None),
    ("Moto AK125TTR CBS B/N 27 PT", 7_790_000, 400_000, 428_300, 450_000, None),
    ("Moto AK125TTR CBS Ng 27 PT", 7_790_000, 400_000, 428_300, 450_000, None),
    ("Moto AK125TTR CBS G/N/V 27 PT", 8_200_000, 400_000, 428_300, 450_000, None),
    ("Moto AK200TTR ABS B/N 27 PT", 9_590_000, 743_000, 428_300, 450_000, 51_000),
    ("Moto AK200TTR ABS Ng 27 PT", 9_590_000, 743_000, 428_300, 450_000, 51_000),
    ("Moto AK200TTR ABS G/N/V 27 PT", 9_790_000, 743_000, 428_300, 450_000, 52_000),
    ("Moto TT 200 DS+ ABS NEGRO 27 PT", 10_590_000, 800_000, 428_300, 450_000, 54_000),
    ("Moto TT 200 DS+ ABS BLANCO 27 PT", 10_590_000, 800_000, 428_300, 450_000, 54_000),
    ("Moto TT 200 DS+ Rally VERDE NEGRO+ABS", 11_390_000, 800_000, 428_300, 450_000, 57_000),
    ("Moto KARGUEROAK200ZW Grs 27 PT NS", 15_990_000, 400_000, 471_900, 450_000, 70_000),
    ("Moto KARGUERO AK200ZW Carp 27 PT", 18_490_000, 400_000, 471_900, 450_000, 80_000),
    ("Moto Tuk Tuk 200AT Bla 27 PT", 16_490_000, 500_000, 471_900, 450_000, 75_000),
    ("Moto VOGE300Rally Ng Mate 27 PT", 17_990_000, 400_000, 846_400, 450_000, 80_000),
    ("Moto VOGE300Rally Grs brillante 27 PT", 17_990_000, 400_000, 846_400, 450_000, 80_000),
    ("Moto VOGE300DS G/Ver mate 27 PT", 15_990_000, 400_000, 846_400, 450_000, 71_000),
    ("Moto VOGE300DS N/Rj mate 27 PT", 15_990_000, 400_000, 846_400, 450_000, 71_000),
    ("Moto VOGE300DS Ng Brillante 27 PT", 15_990_000, 400_000, 846_400, 450_000, 71_000),
    ("Moto VOGE300DS Gris brillante 27 PT", 15_990_000, 400_000, 846_400, 450_000, 71_000),
]


def upgrade() -> None:
    # ON CONFLICT DO NOTHING: portable Postgres/SQLite moderno.
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
                "marca": "AKT",
                "referencia": ref,
                "precio_lista": precio,
                "bono_pesos": bono,
                "soat": soat,
                "matricula": matricula,
                "impuesto": impuesto,
                "vigencia": VIGENCIA_NOV_2026,
            }
            for ref, precio, bono, soat, matricula, impuesto in AKT_NOV_2026
        ],
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "DELETE FROM vehiculo_catalogo "
            "WHERE marca = 'AKT' AND vigencia = :vigencia"
        ),
        {"vigencia": VIGENCIA_NOV_2026},
    )
