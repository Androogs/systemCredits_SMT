"""Factura del vehículo y datos de la prenda.

Revision ID: 0025_factura_vehiculo
Revises: 0024_consulta_simit
Create Date: 2026-11-06

El concesionario emite la factura una vez el pagaré está firmado por OTP;
su carga mueve el ciclo comercial aprobada → facturada → desembolsada.

- `ALTER TYPE estado_solicitud ADD VALUE 'facturada'`: el ciclo gana el
  estado entre 'aprobada' y 'desembolsada' (SQLite no tiene la DDL enum;
  el ALTER es no-op ahí — las tablas de prueba se crean del ORM).
- `solicitud_credito.factura_*`: metadatos del archivo (ruta relativa
  bajo el dir de evidencias, nombre original, mime, sha256, quién/cuándo)
  y `factura_verificacion` JSONB con el resultado persistido del parseo
  + verificación (el detalle se re-renderiza sin releer el PDF).
- `producto_vehiculo.numero_motor/numero_chasis/vin`: la identificación
  de la moto prendada no se captura en originación — llega con la
  factura o se confirma a mano antes del desembolso.

Idempotente: IF NOT EXISTS en todo.
"""

import sqlalchemy as sa
from alembic import op


revision = "0025_factura_vehiculo"
down_revision = "0024_consulta_simit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres exige commit del ADD VALUE antes de usarlo — fuera de la
    # transacción de la migración vía autocommit.
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE estado_solicitud ADD VALUE IF NOT EXISTS 'facturada'"
        )
    for columna in (
        "factura_ruta VARCHAR(512)",
        "factura_nombre VARCHAR(255)",
        "factura_mime VARCHAR(120)",
        "factura_hash VARCHAR(64)",
        "factura_cargada_en TIMESTAMPTZ",
        "factura_cargada_por VARCHAR(180)",
        "factura_verificacion JSONB",
    ):
        op.execute(
            f"ALTER TABLE solicitud_credito ADD COLUMN IF NOT EXISTS {columna}"
        )
    for columna in (
        "numero_motor VARCHAR(60)",
        "numero_chasis VARCHAR(60)",
        "vin VARCHAR(30)",
    ):
        op.execute(
            f"ALTER TABLE producto_vehiculo ADD COLUMN IF NOT EXISTS {columna}"
        )


def downgrade() -> None:
    for columna in ("numero_motor", "numero_chasis", "vin"):
        op.execute(
            f"ALTER TABLE producto_vehiculo DROP COLUMN IF EXISTS {columna}"
        )
    for columna in (
        "factura_ruta",
        "factura_nombre",
        "factura_mime",
        "factura_hash",
        "factura_cargada_en",
        "factura_cargada_por",
        "factura_verificacion",
    ):
        op.execute(
            f"ALTER TABLE solicitud_credito DROP COLUMN IF EXISTS {columna}"
        )
    # Postgres no permite quitar un valor de un ENUM; 'facturada' queda
    # declarado pero sin filas que lo usen.
