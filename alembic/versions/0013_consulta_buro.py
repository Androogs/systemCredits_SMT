"""Tabla consulta_buro: reportes crudos de centrales reutilizables.

Revision ID: 0013_consulta_buro
Revises: 0012_en_revision_a_rechazada
Create Date: 2026-10-21

La consulta a Experian es un recurso pago por persona: si una persona ya
fue consultada y el reporte sigue vigente (BURO_CACHE_DIAS), la
re-evaluación corre el motor con esos datos en vez de consumir otra
llamada. La llave es (tipo_id, numero_id) — el reporte es reutilizable
entre solicitudes y retomas. fecha_consulta documenta cuándo se
consultó: cada evaluación que reusa el dato queda trazada con
origen_datos 'cache:experian' en la auditoría.

Idempotente por CREATE TABLE IF NOT EXISTS.
"""

from alembic import op


revision = "0013_consulta_buro"
down_revision = "0012_en_revision_a_rechazada"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS consulta_buro (
            id_consulta BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            tipo_id VARCHAR(2) NOT NULL,
            numero_id VARCHAR(20) NOT NULL,
            id_solicitud UUID REFERENCES solicitud_credito(id_solicitud),
            fecha_consulta TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            origen VARCHAR(30) NOT NULL,
            hdc_json TEXT NOT NULL,
            valor_ingreso_json TEXT
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_consulta_buro_persona "
        "ON consulta_buro(tipo_id, numero_id, fecha_consulta DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS consulta_buro")
