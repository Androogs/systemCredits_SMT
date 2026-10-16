"""Merge de las ramas 0006_ocr_cedula y 0010_hoja_negocio_vehiculo.

Revision ID: 0011_merge_ocr_legal
Revises: 0006_ocr_cedula, 0010_hoja_negocio_vehiculo
Create Date: 2026-10-16

Dos líneas de trabajo crearon migraciones en paralelo sobre
0005_evidencias: OCR de cédula (remoto) y el paquete legal/consentimiento
(local). Esta revisión une los dos heads sin reescribir migraciones ya
aplicadas.
"""

from alembic import op

revision = "0011_merge_ocr_legal"
down_revision = ("0006_ocr_cedula", "0010_hoja_negocio_vehiculo")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
