"""Tabla consulta_simit: resultados del estado de cuenta de tránsito.

Revision ID: 0024_consulta_simit
Revises: 0023_cuota_inicial
Create Date: 2026-11-12

El proveedor "portal" del SIMIT es gratis pero frágil (PoW captcha,
cambios del portal, límites por IP): guardar el resultado por documento
durante SIMIT_CACHE_DIAS evita repetir la consulta en cada re-evaluación
o retoma, acota la carga sobre el portal y permite que el precache que
corre en background al aceptar el Habeas Data deje el resultado listo
para la evaluación. La llave es (tipo_id, numero_id), igual que
consulta_runt y consulta_buro. resultado_json solo guarda el detalle
normalizado (paz_y_salvo, total_deuda, total_items, origen), no la
respuesta cruda del portal.

Idempotente por CREATE TABLE IF NOT EXISTS.
"""

from alembic import op


revision = "0024_consulta_simit"
down_revision = "0019_correos_sumoto"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS consulta_simit (
            id_consulta BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            tipo_id VARCHAR(2) NOT NULL,
            numero_id VARCHAR(20) NOT NULL,
            id_solicitud UUID REFERENCES solicitud_credito(id_solicitud),
            fecha_consulta TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            origen VARCHAR(30) NOT NULL,
            resultado_json TEXT NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_consulta_simit_persona "
        "ON consulta_simit(tipo_id, numero_id, fecha_consulta DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS consulta_simit")
