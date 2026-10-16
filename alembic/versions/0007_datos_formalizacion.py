"""Columnas de datos de formalización en contacto_vivienda y datos_laborales.

Revision ID: 0007_datos_formalizacion
Revises: 0006_evidencia_mime
Create Date: 2026-10-14

La información adicional del cliente (residencia, personal, financiera y
laboral) se captura en la formalización, después del vehículo y antes de
la firma OTP. Las columnas ya existen en schema.sql; este script las crea
en bases que se hayan inicializado con una versión anterior del esquema.
Idempotente por ADD COLUMN IF NOT EXISTS.
"""

from alembic import op


revision = "0007_datos_formalizacion"
down_revision = "0006_evidencia_mime"
branch_labels = None
depends_on = None

_CONTACTO_COLUMNAS = (
    "ADD COLUMN IF NOT EXISTS zona_rural BOOLEAN",
    "ADD COLUMN IF NOT EXISTS estado_civil VARCHAR(40)",
    "ADD COLUMN IF NOT EXISTS num_hijos SMALLINT",
    "ADD COLUMN IF NOT EXISTS es_cabeza_familia BOOLEAN",
    "ADD COLUMN IF NOT EXISTS cuenta_bienes_raices BOOLEAN",
    "ADD COLUMN IF NOT EXISTS cuenta_vehiculo BOOLEAN",
    "ADD COLUMN IF NOT EXISTS tiene_moto BOOLEAN",
    "ADD COLUMN IF NOT EXISTS tiene_carro BOOLEAN",
    "ADD COLUMN IF NOT EXISTS primera_moto BOOLEAN",
    "ADD COLUMN IF NOT EXISTS estoy_financiando BOOLEAN",
)

_LABORALES_COLUMNAS = (
    "ADD COLUMN IF NOT EXISTS nombre_empresa VARCHAR(200)",
    "ADD COLUMN IF NOT EXISTS id_ciudad_empresa BIGINT REFERENCES ciudad(id_ciudad)",
    "ADD COLUMN IF NOT EXISTS fecha_ingreso DATE",
    "ADD COLUMN IF NOT EXISTS nivel_educativo VARCHAR(100)",
    "ADD COLUMN IF NOT EXISTS profesion VARCHAR(120)",
    "ADD COLUMN IF NOT EXISTS cargo VARCHAR(120)",
    "ADD COLUMN IF NOT EXISTS actividad_comercial VARCHAR(180)",
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE solicitud_contacto_vivienda " + ", ".join(_CONTACTO_COLUMNAS)
    )
    op.execute(
        "ALTER TABLE datos_laborales " + ", ".join(_LABORALES_COLUMNAS)
    )


def downgrade() -> None:
    contacto = (
        "zona_rural",
        "estado_civil",
        "num_hijos",
        "es_cabeza_familia",
        "cuenta_bienes_raices",
        "cuenta_vehiculo",
        "tiene_moto",
        "tiene_carro",
        "primera_moto",
        "estoy_financiando",
    )
    laborales = (
        "nombre_empresa",
        "id_ciudad_empresa",
        "fecha_ingreso",
        "nivel_educativo",
        "profesion",
        "cargo",
        "actividad_comercial",
    )
    op.execute(
        "ALTER TABLE solicitud_contacto_vivienda "
        + ", ".join(f"DROP COLUMN IF EXISTS {c}" for c in contacto)
    )
    op.execute(
        "ALTER TABLE datos_laborales "
        + ", ".join(f"DROP COLUMN IF EXISTS {c}" for c in laborales)
    )
