"""Seed del listado TVS en el catálogo de vehículos.

Revision ID: 0030_vehiculo_catalogo_tvs
Revises: 0029_vehiculo_catalogo_hero
Create Date: 2026-11-08

Carga la lista pública TVS (PVP por año modelo 2025/2026/2027, IVA 19%
incluido en el PVP): cada celda con precio es una referencia propia
("APACHE 160 CARB ABS 2026") porque el precio cambia por año — igual
criterio que Fratelli y Hero.

- Las KING DELUXE son los motocarros TVS (carpa/pasajero): van bajo la
  misma marca, como los Tuk Tuk de AKT.
- Sin bono/SOAT/matrícula/impuesto en esta lista: quedan NULL y el
  asesor los digita en la hoja de negocio.
- `ON CONFLICT DO NOTHING` re-ejecutable: repoblar no pisa ajustes
  manuales hechos sobre una fila ya cargada.
"""

from alembic import op


revision = "0030_vehiculo_catalogo_tvs"
down_revision = "0029_vehiculo_catalogo_hero"
branch_labels = None
depends_on = None


# (referencia, precio_lista) — modelo + año.
TVS = [
    ("APACHE 160 CARB ABS 2026", 9_499_999),
    ("APACHE 160 CARB ABS 2027", 9_649_999),
    ("APACHE 160 FI ABS NG 2027", 11_499_999),
    ("APACHE 200 CARB ABS 2026", 11_999_999),
    ("APACHE 200 CARB ABS 2027", 12_199_999),
    ("APACHE 200 FI ABS NG 2027", 14_999_999),
    ("APACHE RTR 160 4V XC FI 2025", 10_399_999),
    ("APACHE RTR 160 4V XC FI 2026", 10_299_999),
    ("APACHE RTR 160 4V XC FI 2027", 10_499_999),
    ("APACHE RTR 160 4V XC FI ABS RACING 2026", 10_549_999),
    ("APACHE RTR 160 4V XC FI ABS RACING 2027", 10_749_999),
    ("APACHE RTR 160 4V XC FI ABS RACING DUO TONO 2026", 10_949_999),
    ("APACHE RTR 160 4V XC FI ABS RACING DUO TONO 2027", 11_149_999),
    ("APACHE RTR 200 4V XC FI ABS 2025", 12_999_999),
    ("APACHE RTR 200 4V XC FI ABS 2026", 12_799_999),
    ("APACHE RTR 200 4V XC FI ABS 2027", 12_999_999),
    ("APACHE RTR 200 4V XC FI ABS RACING DUO TONO 2026", 13_099_999),
    ("APACHE RTR 200 4V XC FI ABS RACING DUO TONO 2027", 13_299_999),
    ("DAZZ 110 2025", 6_099_999),
    ("DAZZ 110 2026", 6_299_999),
    ("DAZZ 110 2027", 6_499_999),
    ("KING DELUXE CARPA ESPECIAL 2027", 18_799_000),
    ("KING DELUXE CARPA FULL 2027", 19_599_000),
    ("KING DELUXE PASAJERO 2027", 17_999_000),
    ("NEO 125 FI 2027", 7_999_999),
    ("NEO NX 110 SBT 2026", 6_299_999),
    ("NEO NX 110 SBT 2027", 6_399_999),
    ("NEO NX 110 TK 2027", 6_699_999),
    ("NTORQ 125 XC TK 2027", 8_499_999),
    ("NTORQ 125 XCONNECT ED ESPECIAL SBT 2026", 8_249_999),
    ("NTORQ 125 XCONNECT ED ESPECIAL SBT 2027", 8_449_999),
    ("NTORQ 125 XCONNECT FI 2025", 8_699_999),
    ("NTORQ 125 XCONNECT FI 2026", 8_799_999),
    ("NTORQ 125 XCONNECT FI 2027", 10_199_999),
    ("NTORQ 125 XCONNECT SBT 2026", 7_299_999),
    ("NTORQ 125 XCONNECT SBT 2027", 7_999_999),
    ("RAIDER 125 FI 2026", 8_149_999),
    ("RAIDER 125 FI 2027", 8_199_999),
    ("RAIDER 125 RACING SBT 2026", 7_999_999),
    ("RAIDER 125 RACING SBT 2027", 8_049_999),
    ("RAIDER 125 SBT 2026", 7_749_999),
    ("RAIDER 125 SBT 2027", 7_799_999),
    ("RAIDER 125 TK 2026", 7_949_999),
    ("RAIDER 125 TK 2027", 7_999_999),
    ("SPORT 100 ELS 2025", 5_499_999),
    ("SPORT 100 ELS 2026", 5_699_999),
    ("SPORT 100 ELS 2027", 5_749_999),
    ("SPORT 110 FI 2027", 6_199_999),
    ("SPORT 110 FI TK 2027", 6_599_999),
    ("SPORT ELS AS TK 2027", 5_999_999),
    ("SPORT KLS SPOKE 2025", 3_899_999),
    ("SPORT KLS SPOKE 2026", 4_099_999),
    ("SPORT KLS SPOKE 2027", 4_999_999),
]


def upgrade() -> None:
    values = ",\n        ".join(
        f"('TVS', '{referencia}', {precio}, '2026-11', true)"
        for referencia, precio in TVS
    )
    op.execute(
        f"""
        INSERT INTO vehiculo_catalogo
            (marca, referencia, precio_lista, vigencia, activo)
        VALUES
        {values}
        ON CONFLICT (marca, referencia) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM vehiculo_catalogo WHERE marca = 'TVS'")
