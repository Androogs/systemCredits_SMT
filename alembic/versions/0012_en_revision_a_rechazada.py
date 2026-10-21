"""Cierra dos legados de una sola pasada sobre solicitud_credito.

Revision ID: 0012_en_revision_a_rechazada
Revises: 0011_merge_ocr_legal
Create Date: 2026-10-20

1. Backfill: sin comité, las solicitudes rechazadas que el código viejo
   dejó 'en_revision' (causales Estudio / Requiere Codeudor) pasan a
   'rechazada' — el flujo actual solo maneja aprobada/rechazada.
2. Esquema: elimina ruta_firma_manuscrita, columna que pudo quedar
   aplicada en ambientes donde corrió la migración retirada
   '0012_firma_manuscrita' (la firma manuscrita se eliminó del
   producto: la firma vigente es OTP + QR verificable).
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_en_revision_a_rechazada"
down_revision = "0011_merge_ocr_legal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE solicitud_credito SET estado = 'rechazada' "
        "WHERE estado = 'en_revision' AND decision = 'rechazado'"
    )
    op.execute(
        "ALTER TABLE solicitud_credito "
        "DROP COLUMN IF EXISTS ruta_firma_manuscrita"
    )


def downgrade() -> None:
    # Irreversible a nivel fila: no se puede saber cuáles 'rechazada'
    # eran 'en_revision'. La columna se recrea vacía por compatibilidad.
    op.add_column(
        "solicitud_credito",
        sa.Column("ruta_firma_manuscrita", sa.String(length=512), nullable=True),
    )
