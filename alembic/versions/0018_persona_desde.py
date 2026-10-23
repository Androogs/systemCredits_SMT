"""asesor.persona_desde — corte de atribución al cambiar el titular.

Revision ID: 0018_persona_desde
Revises: 0017_ficha_asesor_historial
Create Date: 2026-10-23

La foto `asesor_cedula` de las solicitudes llega NULL para todo lo
radicado antes de 0017. Ese NULL se trataba como "legado visible para
quien herede la cuenta", así que al cambiar la persona detrás de la
cuenta el sucesor seguía viendo las solicitudes del predecesor.

`asesor.persona_desde` marca desde cuándo el titular actual maneja la
cuenta (se actualiza al cambiar la cédula entre personas, o al llegar
cédula nueva junto con nombre nuevo). El alcance del asesor admite la
foto NULL solo en solicitudes radicadas DESPUÉS de ese corte.
"""

import sqlalchemy as sa
from alembic import op


revision = "0018_persona_desde"
down_revision = "0017_ficha_asesor_historial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE asesor ADD COLUMN IF NOT EXISTS persona_desde TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE asesor DROP COLUMN IF EXISTS persona_desde")
