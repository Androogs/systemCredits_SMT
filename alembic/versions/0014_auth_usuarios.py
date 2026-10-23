"""Auth real: nombre de usuario, asesor→concesionario y backfill de sede.

Revision ID: 0014_auth_usuarios
Revises: 0013_consulta_buro
Create Date: 2026-10-21

Habilita la autenticación JWT con alcance por concesionario:

- `usuario.nombre_completo`: el nombre para cabeceras y auditoría (el
  esquema no tenía ningún campo de nombre en usuario).
- `asesor.id_concesionario`: la sede donde opera el asesor — es la
  llave del alcance "las solicitudes de su concesionario".
- Backfill de `solicitud_credito.id_concesionario`: las radicaciones
  históricas nunca guardaron sede; con alcance activo quedarían
  invisibles para asesor y aliado. Se asignan al concesionario por
  defecto (SUMOTO SA PALMIRA — ajustar el nombre abajo si la operación
  arranca en otra sede). admin las ve siempre (sin filtro).

Idempotente por IF NOT EXISTS / WHERE … IS NULL.
"""

import sqlalchemy as sa
from alembic import op


revision = "0014_auth_usuarios"
down_revision = "0013_consulta_buro"
branch_labels = None
depends_on = None

# Concesionario por defecto para las solicitudes históricas sin sede.
_CONCESIONARIO_BACKFILL = "SUMOTO SA PALMIRA"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE usuario ADD COLUMN IF NOT EXISTS "
        "nombre_completo VARCHAR(180)"
    )
    op.execute(
        "ALTER TABLE asesor ADD COLUMN IF NOT EXISTS "
        "id_concesionario BIGINT REFERENCES concesionario(id_concesionario)"
    )
    op.get_bind().execute(
        sa.text(
            """
            UPDATE solicitud_credito
            SET id_concesionario = (
                SELECT c.id_concesionario FROM concesionario c
                WHERE c.nombre = :nombre
            )
            WHERE id_concesionario IS NULL
              AND EXISTS (
                  SELECT 1 FROM concesionario c WHERE c.nombre = :nombre
              )
            """
        ),
        {"nombre": _CONCESIONARIO_BACKFILL},
    )


def downgrade() -> None:
    op.execute("ALTER TABLE asesor DROP COLUMN IF EXISTS id_concesionario")
    op.execute("ALTER TABLE usuario DROP COLUMN IF EXISTS nombre_completo")
