"""Procedencia de la solicitud: flujo normal vs cargue histórico.

Revision ID: 0032_origen_solicitud
Revises: 0031_garantia_runt_exportacion
Create Date: 2026-11-14

La analítica de campañas separa las solicitudes radicadas en el canal
digital ('flujo') de las importadas del log de transacciones histórico
('cargue_historico', ver backend/database/cargue_log_historico.py).
La columna permite etiquetar ese cargue sin adivinar por heurística
(asesor, num_solicitud u origen_evaluacion) y sin mezclar métricas.
"""

import sqlalchemy as sa
from alembic import op


revision = "0032_origen_solicitud"
down_revision = "0031_garantia_runt_exportacion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "solicitud_credito",
        sa.Column(
            "origen",
            sa.String(30),
            nullable=False,
            server_default="flujo",
        ),
    )


def downgrade() -> None:
    op.drop_column("solicitud_credito", "origen")
