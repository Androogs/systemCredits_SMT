"""Ficha del asesor + historial de la cuenta — atribución por cédula.

Revision ID: 0017_ficha_asesor_historial
Revises: 0016_rol_concesionario
Create Date: 2026-10-21

El correo corporativo del asesor es permanente, pero la persona puede
cambiar (renuncia, reemplazo). Para que cada solicitud quede atribuida
a quien realmente la radicó:

- `asesor.num_cedula`: cédula de la persona que usa la cuenta hoy.
- `solicitud_credito.asesor_nombre`/`asesor_cedula`: foto del radicador
  en el momento de la creación. El alcance del asesor filtra por cédula
  (NULL = legado, sigue visible para quien herede la cuenta).
- `asesor_historial`: cada edición de la ficha (nombre, cédula, celular,
  sede, estado) deja renglón con antes/después y quién lo hizo.

Backfill: las solicitudes existentes copian el nombre del asesor
vigente; su cédula queda NULL (dato nuevo, no había dónde sacarla).
"""

import sqlalchemy as sa
from alembic import op


revision = "0017_ficha_asesor_historial"
down_revision = "0016_rol_concesionario"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE asesor ADD COLUMN IF NOT EXISTS num_cedula VARCHAR(40)"
    )
    op.execute(
        "ALTER TABLE solicitud_credito "
        "ADD COLUMN IF NOT EXISTS asesor_nombre VARCHAR(180)"
    )
    op.execute(
        "ALTER TABLE solicitud_credito "
        "ADD COLUMN IF NOT EXISTS asesor_cedula VARCHAR(40)"
    )
    op.execute(
        """
        UPDATE solicitud_credito s
        SET asesor_nombre = a.nombre
        FROM asesor a
        WHERE s.id_asesor = a.id_asesor AND s.asesor_nombre IS NULL
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS asesor_historial (
            id_historial BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            id_asesor BIGINT NOT NULL REFERENCES asesor(id_asesor),
            id_usuario_cambio UUID NOT NULL REFERENCES usuario(id_usuario),
            fecha TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            cambios JSONB NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_asesor_historial_asesor "
        "ON asesor_historial(id_asesor)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS asesor_historial")
    op.execute("ALTER TABLE solicitud_credito DROP COLUMN IF EXISTS asesor_cedula")
    op.execute("ALTER TABLE solicitud_credito DROP COLUMN IF EXISTS asesor_nombre")
    op.execute("ALTER TABLE asesor DROP COLUMN IF EXISTS num_cedula")
