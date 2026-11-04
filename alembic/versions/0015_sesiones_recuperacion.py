"""Sesiones persistidas + recuperación de clave + backfill de asesor.

Revision ID: 0015_sesiones_recuperacion
Revises: 0014_auth_usuarios
Create Date: 2026-10-21

D125 — `refresh_token`: sesión revocable en servidor. Solo se guarda el
hash SHA-256 del token opaco; la rotación encadena cada token con el que
lo reemplaza (`reemplazado_por`) para detectar reuso.

D124 — `token_recuperacion`: enlace de "olvidé mi clave" de un solo uso
y ventana corta (`recuperacion_token_minutos`, 30 por defecto). También
solo el hash.

D126 — backfill: las solicitudes históricas con `id_asesor` NULL (146,
todas de SUMOTO SA PALMIRA) pasan al asesor de la sede decidido por
negocio: el usuario asesor@sumoto.com.co ("Asesor de Prueba"). El UPDATE
está acotado a esa sede y es idempotente (solo toca filas NULL); si el
asesor o la sede no existen en el entorno, no hace nada.

Idempotente por IF NOT EXISTS / guardas EXISTS.
"""

import sqlalchemy as sa
from alembic import op


revision = "0015_sesiones_recuperacion"
down_revision = "0014_auth_usuarios"
branch_labels = None
depends_on = None

# Decisión de negocio aprobada: todas las heredadas sin radicador van a
# un único asesor de la sede donde se originaron.
_CORREO_ASESOR_BACKFILL = "asesor@sumoto.com.co"
_CONCESIONARIO_BACKFILL = "SUMOTO SA PALMIRA"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS refresh_token (
            id_refresh BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            id_usuario UUID NOT NULL REFERENCES usuario(id_usuario),
            token_hash CHAR(64) NOT NULL UNIQUE,
            expira_en TIMESTAMPTZ NOT NULL,
            revocado BOOLEAN NOT NULL DEFAULT FALSE,
            ip VARCHAR(45),
            fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fecha_revocacion TIMESTAMPTZ,
            reemplazado_por BIGINT REFERENCES refresh_token(id_refresh)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_refresh_token_usuario "
        "ON refresh_token(id_usuario)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS token_recuperacion (
            id_token BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            id_usuario UUID NOT NULL REFERENCES usuario(id_usuario),
            token_hash CHAR(64) NOT NULL,
            expira_en TIMESTAMPTZ NOT NULL,
            usado BOOLEAN NOT NULL DEFAULT FALSE,
            ip VARCHAR(45),
            fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fecha_uso TIMESTAMPTZ
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_recuperacion_hash "
        "ON token_recuperacion(token_hash)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_recuperacion_usuario "
        "ON token_recuperacion(id_usuario)"
    )

    # D126: hereda las solicitudes sin radicador al asesor elegido de la
    # sede. El EXISTS final evita tocar filas si el asesor/sede no están
    # en este entorno (p. ej. una base de pruebas limpia).
    op.get_bind().execute(
        sa.text(
            """
            UPDATE solicitud_credito
            SET id_asesor = (
                SELECT a.id_asesor
                FROM asesor a
                JOIN usuario u ON u.id_usuario = a.id_usuario
                WHERE lower(u.correo) = :correo
            )
            WHERE id_asesor IS NULL
              AND id_concesionario = (
                  SELECT c.id_concesionario FROM concesionario c
                  WHERE c.nombre = :sede
              )
              AND EXISTS (
                  SELECT 1
                  FROM asesor a
                  JOIN usuario u ON u.id_usuario = a.id_usuario
                  WHERE lower(u.correo) = :correo
              )
              AND EXISTS (
                  SELECT 1 FROM concesionario c
                  WHERE c.nombre = :sede
              )
            """
        ),
        {
            "correo": _CORREO_ASESOR_BACKFILL,
            "sede": _CONCESIONARIO_BACKFILL,
        },
    )


def downgrade() -> None:
    # El backfill es una decisión de negocio (no hay cómo distinguir las
    # 146 filas heredadas de asignaciones posteriores legítimas): se
    # revierte solo el esquema.
    op.execute("DROP TABLE IF EXISTS token_recuperacion")
    op.execute("DROP TABLE IF EXISTS refresh_token")
