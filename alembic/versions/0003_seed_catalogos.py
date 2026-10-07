"""Siembra de catálogos mínimos del negocio.

Revision ID: 0003_seed_catalogos
Revises: 0002_motor_decision
Create Date: 2026-10-06

Ejecuta backend/database/insert.sql: roles, aliado/concesionario,
producto financiero (rangos de tasa/plazo/monto), ciudad base y el
catálogo de criterios de evaluación con los códigos canónicos del
motor (R1-R25, RC1-RC4, E1-E9). insert.sql es idempotente
(ON CONFLICT DO NOTHING), así que re-correrla es seguro.
"""

from pathlib import Path

from alembic import op


revision = "0003_seed_catalogos"
down_revision = "0002_motor_decision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    seed_path = (
        Path(__file__).resolve().parents[2]
        / "backend"
        / "database"
        / "insert.sql"
    )
    op.execute(seed_path.read_text(encoding="utf-8"))


def downgrade() -> None:
    # La siembra es de catálogos compartidos por el negocio; no se
    # eliminan en downgrade para no romper filas referenciadas.
    pass
