"""documento_evidencia.mime: 60 -> 120 caracteres.

Revision ID: 0006_evidencia_mime
Revises: 0005_evidencias
Create Date: 2026-10-13

El MIME de los DOCX del paquete de legalización
('application/vnd.openxmlformats-officedocument.wordprocessingml.document',
72 caracteres) no cabía en VARCHAR(60) y rompía la generación del
paquete tras la firma OTP.
"""

from alembic import op


revision = "0006_evidencia_mime"
down_revision = "0005_evidencias"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE documento_evidencia "
        "ALTER COLUMN mime TYPE VARCHAR(120)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE documento_evidencia "
        "ALTER COLUMN mime TYPE VARCHAR(60)"
    )
