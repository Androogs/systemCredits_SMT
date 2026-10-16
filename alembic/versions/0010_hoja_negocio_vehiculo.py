"""Desglose de la hoja de negocio del vehículo financiado.

Revision ID: 0010_hoja_negocio_vehiculo
Revises: 0009_consentimiento_habeas
Create Date: 2026-10-15

El documento "7. Solicitud de crédito" imprime la hoja de negocio
completa (descuento, accesorios, matrícula, SOAT, impuestos, fondo de
garantía). Esos valores viajaban en SeleccionarOfertaRequest.vehiculo
pero solo quedaban trazados como texto en descripcion_estado; ahora se
persisten como columnas para poder reconstruir el documento y auditar
la composición del saldo financiado.

aval_pct se captura en producto_vehiculo (momento de la selección) y se
propaga a credito_financiacion cuando el crédito se crea en el
desembolso — posición canónica ya declarada en schema.sql.

Idempotente por ADD COLUMN IF NOT EXISTS.
"""

from alembic import op


revision = "0010_hoja_negocio_vehiculo"
down_revision = "0009_consentimiento_habeas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE producto_vehiculo
            ADD COLUMN IF NOT EXISTS descuento_pesos NUMERIC(18,2) NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS descuento_pct NUMERIC(8,4) NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS accesorios NUMERIC(18,2) NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS matricula NUMERIC(18,2) NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS soat NUMERIC(18,2) NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS impuestos NUMERIC(18,2) NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS aval_pct NUMERIC(8,4)
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_vehiculo_descuento_pct'
            ) THEN
                ALTER TABLE producto_vehiculo
                    ADD CONSTRAINT ck_vehiculo_descuento_pct
                    CHECK (descuento_pct BETWEEN 0 AND 100);
            END IF;
        END $$
        """
    )
    op.execute(
        "ALTER TABLE credito_financiacion "
        "ADD COLUMN IF NOT EXISTS aval_pct NUMERIC(8,4)"
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE producto_vehiculo
            DROP CONSTRAINT IF EXISTS ck_vehiculo_descuento_pct,
            DROP COLUMN IF EXISTS aval_pct,
            DROP COLUMN IF EXISTS impuestos,
            DROP COLUMN IF EXISTS soat,
            DROP COLUMN IF EXISTS matricula,
            DROP COLUMN IF EXISTS accesorios,
            DROP COLUMN IF EXISTS descuento_pct,
            DROP COLUMN IF EXISTS descuento_pesos
        """
    )
    op.execute(
        "ALTER TABLE credito_financiacion DROP COLUMN IF EXISTS aval_pct"
    )
