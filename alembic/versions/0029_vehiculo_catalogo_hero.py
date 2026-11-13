"""Seed del listado Hero en el catálogo de vehículos.

Revision ID: 0029_vehiculo_catalogo_hero
Revises: 0028_vehiculo_catalogo_fratelli
Create Date: 2026-11-06

Carga las 148 entradas de la hoja «LP sugerido al público 2026» de la
«HERO LISTA DE PRECIOS NOVIEMBRE 2026» (HMCL Colombia) — la lista
pública. Cada fila es referencia + año modelo ("Eco 100 2020"); la
hoja cubre años 2017-2027 porque el concesionario vende modelos de
años anteriores al precio listado.

- La hoja `ITEMS` (precios a concesionario por código/color) no se
  usa — es información comercial interna.
- No hay bono/SOAT/matrícula/impuesto en esta lista: quedan NULL y el
  asesor los digita como siempre.
- Nombres normalizados: U+00A0 (espacio no separable del Excel) se
  reemplaza por espacio común — si no, "Xpulse 200 4V" escrito a mano
  nunca cruzaría con el catálogo.
- Duplicado del origen: "HUNK 160 STEALTH R NEGRO MATE 2024" aparece
  dos veces ($10.190.000 y $10.390.000); se conserva el primero —
  ON CONFLICT ignora el segundo.

Idempotente: ON CONFLICT (marca, referencia) DO NOTHING.
"""

import sqlalchemy as sa
from alembic import op


revision = "0029_vehiculo_catalogo_hero"
down_revision = "0028_vehiculo_catalogo_fratelli"
branch_labels = None
depends_on = None

VIGENCIA_NOV_2026 = "2026-11"

# referencia, precio_lista
HERO_NOV_2026 = [
    ("Eco 100 2020", 2990000),
    ("Eco 100 2021", 3350000),
    ("Eco CW 2020", 3650000),
    ("Splendor 100 2017", 3650000),
    ("Splendor 100 2018", 3850000),
    ("Splendor 110 2018", 3890000),
    ("Splendor 110 2019", 3890000),
    ("Eco CW 2021", 3950000),
    ("Splendor 110 2020", 3990000),
    ("Dash 2017", 3990000),
    ("Dash 2018", 3990000),
    ("Dash 2019", 3990000),
    ("Dash 2020", 3990000),
    ("Super Splendor 2018", 4000000),
    ("Eco 100 2022", 4149000),
    ("Ignitor 2020", 4290000),
    ("Ignitor SS 2020", 4350000),
    ("Splendor 110 2021", 4390000),
    ("Eco SP 2022", 4490000),
    ("Dash 125 2020", 4490000),
    ("Dash 125 2021", 4690000),
    ("Glamour 2017", 4699000),
    ("Glamour 2018", 4699000),
    ("Eco CW 2022", 4749000),
    ("Ignitor SS 2021", 4890000),
    ("Thriller I3S 2018", 4899000),
    ("Thriller I3S MATE DE LINEA 2018", 4899000),
    ("Thriller I3S 2019", 4899000),
    ("Thriller I3S MATE DE LINEA 2019", 4899000),
    ("Thriller I3S 2020", 4899000),
    ("Eco 100/c 2024", 4900000),
    ("Eco 100/c 2025", 4990000),
    ("Eco 100/c 2026", 4990000),
    ("ECO 100/c IBS 2027", 4990000),
    ("ECO 100/c LIMITADA NEGRO GRIS 2025", 4990000),
    ("Splendor 110 2022", 4990000),
    ("Eco 100/c 2023", 4999000),
    ("Dash 125 FI 2020", 5050000),
    ("Thriller I3S SS ED ESPECIAL 2018", 5100000),
    ("Thriller Pro 2019", 5199000),
    ("Splendor 110 RW 2022", 5250000),
    ("Thriller 2017", 5290000),
    ("Thriller 2018", 5290000),
    ("Thriller Pro 2020", 5290000),
    ("Ignitor 100M 2022", 5350000),
    ("Eco T 2026", 5390000),
    ("Thriller Sports 2017", 5450000),
    ("Thriller Sports 2018", 5450000),
    ("Eco T 2027", 5490000),
    ("Eco SP 2026", 5590000),
    ("Eco Cargo 2025", 5590000),
    ("Dash 125 FI 2021", 5590000),
    ("Thriller Sports SS 2018", 5590000),
    ("Eco CW 2026", 5690000),
    ("Ignitor SS 2022", 5750000),
    ("Eco SP 2023", 5790000),
    ("Eco SP 2025", 5790000),
    ("Eco SP 2027", 5790000),
    ("Eco Cargo 2023", 5890000),
    ("Eco Cargo 2024", 5890000),
    ("Eco CW 2023", 5990000),
    ("Eco CW 2025", 5990000),
    ("Eco CW E.LTD ROJA 2026", 5990000),
    ("Eco CW 2027", 5990000),
    ("Thriller Pro 2021", 5990000),
    ("Eco SP 2024", 6149000),
    ("Splendor 110 RW 2023", 6190000),
    ("Splendor XPRO 2025", 6290000),
    ("Splendor XPRO 2026", 6290000),
    ("Eco CW 2024", 6390000),
    ("Splendor XPRO 2027", 6390000),
    ("Splendor XPRO 2023", 6449000),
    ("Splendor XPRO 2024", 6490000),
    ("Thriller 200R 2019", 6550000),
    ("Thriller 200R 2020", 6550000),
    ("Dash 125 FI 2022", 6690000),
    ("Thriller Pro 2022", 6790000),
    ("Thriller 200R 2021", 6790000),
    ("Ignitor 5S 2025", 6900000),
    ("IGNITOR 5SPEED 2026", 6900000),
    ("IGNITOR XTECH 2026", 6900000),
    ("IGNITOR XTECH 2027", 6900000),
    ("Ignitor SS 2023", 6990000),
    ("XOOM 110 2026", 6990000),
    ("XOOM 110 2027", 6990000),
    ("Ignitor 5S 2024", 7100000),
    ("Ignitor SS 2024", 7190000),
    ("Hunk 190 FI 2021", 7390000),
    ("HUNK 125R 2026", 7490000),
    ("Thriller Xtreme 2025", 7700000),
    ("HUNK 125R 2027", 7790000),
    ("Thriller Pro 2023", 7900000),
    ("Thriller Pro 2024", 7990000),
    ("Thriller Xtreme 2024", 7990000),
    ("HUNK 125R REDVOL 2027", 7990000),
    ("Dash 125 FI 2023", 7990000),
    ("XOOM 125 2027", 7990000),
    ("Xpulse 200 2021", 8190000),
    ("Dash 125 FI 2024", 8190000),
    ("ZMR 2017", 8235000),
    ("Hunk 160 FI 2022", 8249000),
    ("HUNK 150 XT 2025", 8290000),
    ("Dash FI EV 2024", 8490000),
    ("Dash FI EV 2025", 8490000),
    ("Dash FI EV 2026", 8490000),
    ("HUNK 150 XT 2026", 8590000),
    ("Xpulse T 2021", 8650000),
    ("HUNK 150 XT 2027", 8790000),
    ("Hunk 190 FI 2022", 8849000),
    ("HUNK 150 XT REDVOL 2027", 8990000),
    ("Hunk 160 FI 2023", 8990000),
    ("HUNK 160 FI ST 2025", 8990000),
    ("HUNK 160 V2 2025", 8990000),
    ("HUNK 160R STEALTH NEGRO MATE 2025", 8990000),
    ("Xpulse 200T FI OC 2023", 9000000),
    ("Xpulse FI 2021", 9090000),
    ("Hunk 190 FI 2023", 9190000),
    ("HUNK 160 V2 2026", 9390000),
    ("HUNK 160 STEALTH RS NEGRO MATE 2026", 9390000),
    ("Xpulse T 2022", 9390000),
    ("HUNK 160 STEALTH RS NEGRO MATE 2025", 9490000),
    ("Xpulse 200T FI OC 2024", 9490000),
    ("HUNK 160 V2 2027", 9590000),
    ("HUNK 160 STEALTH RS NEGRO MATE 2027", 9590000),
    ("HUNK 160 FI ST 2024", 9900000),
    ("Hunk 190 FI 2024", 9990000),
    ("HUNK 160 FI ST 2023", 9999000),
    ("HUNK 160 STEALTH R NEGRO MATE 2024", 10190000),
    ("Xpulse 200T FI OC 2025", 10290000),
    ("Xpulse 200 FI Advance 2025", 10290000),
    ("HUNK 160 4V 2025", 10490000),
    ("Xpulse 200T FI 2023", 10490000),
    ("Xpulse 200T FI OC 2026", 10490000),
    ("Xpulse 200 FI Advance 2026", 10490000),
    ("Xpulse FI 2023", 10590000),
    ("HUNK 160 4V 2026", 10740000),
    ("HUNK 160 4V 2027", 10990000),
    ("HUNK 160 4V REDVOL 2027", 10990000),
    ("Xpulse 200 FI Advance 2024", 11490000),
    ("Xpulse 200 4V 2025", 11900000),
    ("Xpulse 200 4V 2026", 12290000),
    ("Xpulse 200 4V 2027", 12390000),
    ("Xpulse PRO 4V 2025", 12890000),
    ("Xpulse PRO 4V 2026", 13190000),
    ("XPULSE 200 R 4V 2026", 13390000),
    ("Xpulse PRO 4V 2027", 13490000),
    ("Xpulse PRO 4V 2.0 2027", 13590000),
    ("XPULSE 200 R 4V 2027", 13790000),
]


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO vehiculo_catalogo
                (marca, referencia, precio_lista, vigencia)
            VALUES
                (:marca, :referencia, :precio_lista, :vigencia)
            ON CONFLICT (marca, referencia) DO NOTHING
            """
        ),
        [
            {
                "marca": "Hero",
                "referencia": ref,
                "precio_lista": precio,
                "vigencia": VIGENCIA_NOV_2026,
            }
            for ref, precio in HERO_NOV_2026
        ],
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "DELETE FROM vehiculo_catalogo "
            "WHERE marca = 'Hero' AND vigencia = :vigencia"
        ),
        {"vigencia": VIGENCIA_NOV_2026},
    )
