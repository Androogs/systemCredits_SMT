"""Columna fecha_vigencia en oferta_credito.

Revision ID: 0008_vigencia_ofertas
Revises: 0007_datos_formalizacion
Create Date: 2026-10-15

Una oferta aprobada no debe poder seleccionarse indefinidamente: las
condiciones (tasa, capacidad de pago, cupo) pueden quedar obsoletas.
fecha_vigencia marca hasta cuándo es seleccionable; los días se
configuran con OFERTA_VIGENCIA_DIAS (por defecto 15).

Ofertas generadas antes de esta columna quedan con vigencia derivada de
su fecha_generacion para que no se vuelvan inmortales.

Idempotente por ADD COLUMN IF NOT EXISTS.
"""

from alembic import op


revision = "0008_vigencia_ofertas"
down_revision = "0007_datos_formalizacion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE oferta_credito "
        "ADD COLUMN IF NOT EXISTS fecha_vigencia TIMESTAMPTZ"
    )
    op.execute(
        "UPDATE oferta_credito "
        "SET fecha_vigencia = fecha_generacion + INTERVAL '15 days' "
        "WHERE fecha_vigencia IS NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE oferta_credito DROP COLUMN IF EXISTS fecha_vigencia")
