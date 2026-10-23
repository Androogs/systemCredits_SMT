"""Rol `concesionario` (administrador de sede) — D122.

Revision ID: 0016_rol_concesionario
Revises: 0015_sesiones_recuperacion
Create Date: 2026-10-21

Modelo aprobado: el concesionario ve y opera TODAS las solicitudes de
su sede (radica a nombre de un asesor propio, evalúa, OTP, desembolsa)
y gestiona los usuarios-asesor de esa sede. No hereda `asesor`: el
vínculo vive en `concesionario_usuario` para no contaminar el catálogo
de radicadores que usan los filtros del panel y del aliado.

- `ALTER TYPE rol_usuario ADD VALUE`: el ENUM de Postgres no admite
  el rol nuevo sin esto (SQLite lo ignora — la DDL enum no existe ahí).
- `concesionario_usuario`: un usuario administra a lo sumo una sede;
  una sede puede tener varios administradores.

Idempotente: IF NOT EXISTS / ON CONFLICT.
"""

import sqlalchemy as sa
from alembic import op


revision = "0016_rol_concesionario"
down_revision = "0015_sesiones_recuperacion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... IF NOT EXISTS no acepta bind params; el valor es
    # constante del código (no entrada de usuario). Postgres exige
    # commit del ADD VALUE antes de usarlo — fuera de la transacción
    # de la migración vía autocommit.
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE rol_usuario ADD VALUE IF NOT EXISTS 'concesionario'"
        )
    op.execute(
        sa.text(
            "INSERT INTO rol (nombre, descripcion) VALUES "
            "('concesionario', 'Administrador de sede: ve y opera todas "
            "las solicitudes de su concesionario y gestiona sus asesores') "
            "ON CONFLICT (nombre) DO NOTHING"
        )
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS concesionario_usuario (
            id_usuario UUID PRIMARY KEY REFERENCES usuario(id_usuario),
            id_concesionario BIGINT NOT NULL
                REFERENCES concesionario(id_concesionario)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_concesionario_usuario_sede "
        "ON concesionario_usuario(id_concesionario)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS concesionario_usuario")
    op.execute(
        sa.text("DELETE FROM rol WHERE nombre = 'concesionario'")
    )
    # Postgres no permite quitar un valor de un ENUM; el valor queda
    # declarado pero sin filas que lo usen.
