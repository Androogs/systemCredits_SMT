"""Ancho de documento_evidencia.tipo para los tipos doc_* largos.

Revision ID: 0039_evidencia_tipo
Revises: 0038_usuario_marcas
Create Date: 2026-11-12

El tipo más largo del paquete de legalización (``doc_autorizacion_datos``)
tiene 22 caracteres y no cabía en VARCHAR(20): el registro del documento
generado se rechazaba y el paquete quedaba parcial. Se amplía a 40.
"""

import sqlalchemy as sa
from alembic import op


revision = "0039_evidencia_tipo"
down_revision = "0038_usuario_marcas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "documento_evidencia",
        "tipo",
        existing_type=sa.String(20),
        type_=sa.String(40),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "documento_evidencia",
        "tipo",
        existing_type=sa.String(40),
        type_=sa.String(20),
        existing_nullable=False,
    )
