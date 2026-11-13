"""Concesionarios = las 7 marcas aliadas con sus puntos de venta.

Revision ID: 0037_concesionario_marcas
Revises: 0036_marca_vehiculo
Create Date: 2026-11-10

SUMOTO S.A queda como la matriz (``marca`` NULL). Cada marca tiene una
fila por sede comercial: ``nombre`` sigue el patrón '<MARCA> <SEDE>' y
``sede`` guarda la etiqueta corta que se muestra en Ajustes.
"""

import sqlalchemy as sa
from alembic import op


revision = "0037_concesionario_marcas"
down_revision = "0036_marca_vehiculo"
branch_labels = None
depends_on = None


# (marca, sede, ciudad). 'Principal'/'Centro' no son ciudades: quedan sin
# id_ciudad. Honda y Fratelli aún no tienen sede física: fila de marca.
SEDES = [
    ("AKT", ["Principal", "Centro", "Cali", "Buga", "Yumbo", "Candelaria", "Pradera"]),
    ("Auteco", ["Cali"]),
    ("Bajaj", ["Palmira", "Pradera", "Florida"]),
    ("Fratelli", []),
    ("Hero", ["Palmira", "Cali", "Florida"]),
    ("Honda", []),
    ("Suzuki", ["Principal", "Centro", "El Cerrito", "Candelaria", "Florida", "Pradera"]),
]

CIUDAD_DE_SEDE = {
    "Palmira": "PALMIRA",
    "Cali": "CALI",
    "Buga": "BUGA",
    "Yumbo": "YUMBO",
    "Candelaria": "CANDELARIA",
    "Pradera": "PRADERA",
    "El Cerrito": "EL CERRITO",
    "Florida": "FLORIDA",
}


def _id_ciudad(conn, nombre_ciudad: str | None) -> int | None:
    if nombre_ciudad is None:
        return None
    row = conn.execute(
        sa.text(
            "SELECT id_ciudad FROM ciudad WHERE upper(nombre) = :n "
            "ORDER BY id_ciudad LIMIT 1"
        ),
        {"n": nombre_ciudad},
    ).first()
    if row is None:
        row = conn.execute(
            sa.text(
                "INSERT INTO ciudad (nombre, departamento) "
                "VALUES (:n, 'VALLE DEL CAUCA') RETURNING id_ciudad"
            ),
            {"n": nombre_ciudad},
        ).first()
    return row[0]


def upgrade() -> None:
    op.add_column("concesionario", sa.Column("marca", sa.String(60), nullable=True))
    op.add_column("concesionario", sa.Column("sede", sa.String(120), nullable=True))
    conn = op.get_bind()
    for marca, sedes in SEDES:
        if not sedes:
            conn.execute(
                sa.text(
                    "INSERT INTO concesionario (nombre, marca) VALUES (:n, :m) "
                    "ON CONFLICT (nombre) DO NOTHING"
                ),
                {"n": marca.upper(), "m": marca},
            )
            continue
        for sede in sedes:
            conn.execute(
                sa.text(
                    "INSERT INTO concesionario (nombre, marca, sede, id_ciudad) "
                    "VALUES (:n, :m, :s, :c) ON CONFLICT (nombre) DO NOTHING"
                ),
                {
                    "n": f"{marca.upper()} {sede.upper()}",
                    "m": marca,
                    "s": sede,
                    "c": _id_ciudad(conn, CIUDAD_DE_SEDE.get(sede)),
                },
            )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM concesionario WHERE marca IS NOT NULL")
    )
    op.drop_column("concesionario", "sede")
    op.drop_column("concesionario", "marca")
