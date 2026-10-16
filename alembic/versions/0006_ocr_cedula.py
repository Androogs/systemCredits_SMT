"""OCR de cédula: columnas de datos esperados y resultado en sesion_captura.

Revision ID: 0006_ocr_cedula
Revises: 0005_evidencias
Create Date: 2026-10-13

Guarda, junto a la sesión de captura, los datos que el asesor capturó en el
paso 1 y el resultado del OCR de la cédula frontal. Así el frontend puede
advertir cuando los datos leídos no coinciden con los capturados.
"""

from alembic import op

revision = "0006_ocr_cedula"
down_revision = "0005_evidencias"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS: la baseline (0001) ejecuta el schema.sql actual, que ya
    # trae las columnas; en bases antiguas sí las agrega.
    op.execute(
        """
        ALTER TABLE sesion_captura
            ADD COLUMN IF NOT EXISTS datos_esperados JSONB,
            ADD COLUMN IF NOT EXISTS resultado_ocr   JSONB;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE sesion_captura
            DROP COLUMN IF EXISTS resultado_ocr,
            DROP COLUMN IF EXISTS datos_esperados;
        """
    )