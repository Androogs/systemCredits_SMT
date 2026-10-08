"""Columna parametros_huella en motor_evaluacion_auditoria.

Revision ID: 0004_auditoria_parametros
Revises: 0003_seed_catalogos
Create Date: 2026-10-07

Persiste en cada evaluación auditada el sha256 corto del juego de
parámetros vigente, para reconstruir el contexto exacto de una decisión
cuando PUT /api/parametros modifique los cortes en el tiempo.
"""

from alembic import op


revision = "0004_auditoria_parametros"
down_revision = "0003_seed_catalogos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS: la baseline (0001) ejecuta el schema.sql actual, que ya
    # incluye esta columna; en bases antiguas sí aplica el ALTER.
    op.execute(
        "ALTER TABLE motor_evaluacion_auditoria "
        "ADD COLUMN IF NOT EXISTS parametros_huella VARCHAR(16)"
    )


def downgrade() -> None:
    op.drop_column("motor_evaluacion_auditoria", "parametros_huella")
