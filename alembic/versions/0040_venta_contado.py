"""Liquidación y facturación de la venta de contado.

Revision ID: 0040_venta_contado
Revises: 0039_evidencia_tipo
Create Date: 2026-11-13

El cierre de una venta de contado captura la liquidación de la hoja de
negocio (anticipo, retoma, otros gastos, ciudad de matrícula) y a quién
se expide la factura, que puede ser distinto del cliente
(facturar a 1 / 2, asesor externo, observaciones).
"""

import sqlalchemy as sa
from alembic import op


revision = "0040_venta_contado"
down_revision = "0039_evidencia_tipo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "producto_vehiculo",
        sa.Column("anticipo", sa.Numeric(18, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "producto_vehiculo",
        sa.Column("retoma_valor", sa.Numeric(18, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "producto_vehiculo",
        sa.Column("otros_gastos", sa.Numeric(18, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "producto_vehiculo",
        sa.Column("ciudad_matricula", sa.String(120), nullable=True),
    )
    op.add_column(
        "solicitud_credito",
        sa.Column("facturar_a_documento", sa.String(30), nullable=True),
    )
    op.add_column(
        "solicitud_credito",
        sa.Column("facturar_a_nombre", sa.String(180), nullable=True),
    )
    op.add_column(
        "solicitud_credito",
        sa.Column("facturar_a2_documento", sa.String(30), nullable=True),
    )
    op.add_column(
        "solicitud_credito",
        sa.Column("facturar_a2_nombre", sa.String(180), nullable=True),
    )
    op.add_column(
        "solicitud_credito",
        sa.Column("asesor_externo", sa.String(180), nullable=True),
    )
    op.add_column(
        "solicitud_credito",
        sa.Column("observaciones_venta", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("solicitud_credito", "observaciones_venta")
    op.drop_column("solicitud_credito", "asesor_externo")
    op.drop_column("solicitud_credito", "facturar_a2_nombre")
    op.drop_column("solicitud_credito", "facturar_a2_documento")
    op.drop_column("solicitud_credito", "facturar_a_nombre")
    op.drop_column("solicitud_credito", "facturar_a_documento")
    op.drop_column("producto_vehiculo", "ciudad_matricula")
    op.drop_column("producto_vehiculo", "otros_gastos")
    op.drop_column("producto_vehiculo", "retoma_valor")
    op.drop_column("producto_vehiculo", "anticipo")
