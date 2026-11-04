"""Cuentas de usuario al dominio corporativo @sumoto.com.co.

Revision ID: 0019_correos_sumoto
Revises: 0018_persona_desde
Create Date: 2026-10-26

SUMOTO S.A. es la marca principal de la plataforma (Inversiones Pacífico
queda como financiera aliada). Las cuentas sembradas con el dominio
@pacifico.co pasan a @sumoto.com.co conservando id, clave, roles y sede.

- Solo se renombra una cuenta si el correo destino no existe ya
  (la columna `usuario.correo` es UNIQUE).
- El downgrade revierte únicamente las cuentas del seed, para no tocar
  usuarios reales creados después con @sumoto.com.co.
"""

from alembic import op


revision = "0019_correos_sumoto"
down_revision = "0018_persona_desde"
branch_labels = None
depends_on = None

_DOMINIO_ANTERIOR = "@pacifico.co"
_DOMINIO_NUEVO = "@sumoto.com.co"
_CUENTAS_SEED = ("admin", "asesor", "aliado")


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE usuario AS u
        SET correo = REPLACE(u.correo, '{_DOMINIO_ANTERIOR}', '{_DOMINIO_NUEVO}')
        WHERE u.correo LIKE '%{_DOMINIO_ANTERIOR}'
          AND NOT EXISTS (
            SELECT 1 FROM usuario AS otro
            WHERE otro.correo = REPLACE(u.correo, '{_DOMINIO_ANTERIOR}', '{_DOMINIO_NUEVO}')
          )
        """
    )


def downgrade() -> None:
    for cuenta in _CUENTAS_SEED:
        op.execute(
            f"""
            UPDATE usuario
            SET correo = '{cuenta}{_DOMINIO_ANTERIOR}'
            WHERE correo = '{cuenta}{_DOMINIO_NUEVO}'
              AND NOT EXISTS (
                SELECT 1 FROM usuario WHERE correo = '{cuenta}{_DOMINIO_ANTERIOR}'
              )
            """
        )
