"""Archivos planos RNGM del cargue masivo RUNTPRO (guía GM Fase II).

Revision ID: 0035_rngm_archivo_lote
Revises: 0034_usuario_sede
Create Date: 2026-11-10

El cargue masivo a RUNTPRO usa un .txt ``<NIT>RGM<consecutivo><AAAAMMDD>``
cuyo consecutivo de 3 dígitos reinicia cada fecha. Esta tabla da el
consecutivo y audita cada archivo generado (prendas, registros,
advertencias, quién lo sacó).
"""

import sqlalchemy as sa
from alembic import op


revision = "0035_rngm_archivo_lote"
down_revision = "0034_usuario_sede"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rngm_archivo_lote",
        sa.Column("id_lote", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("fecha_corte", sa.Date(), nullable=False),
        sa.Column("consecutivo", sa.SmallInteger(), nullable=False),
        sa.Column("nombre_archivo", sa.String(40), nullable=False, unique=True),
        sa.Column("tipo_novedad", sa.String(1), nullable=False, server_default="R"),
        sa.Column("n_garantias", sa.Integer(), nullable=False),
        sa.Column("n_registros", sa.Integer(), nullable=False),
        sa.Column("n_advertencias", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generado_por", sa.String(180), nullable=True),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("fecha_corte", "consecutivo", name="uq_rngm_fecha_consecutivo"),
    )


def downgrade() -> None:
    op.drop_table("rngm_archivo_lote")
