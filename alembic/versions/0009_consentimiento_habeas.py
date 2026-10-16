"""Tabla consentimiento_habeas: prueba versionada del consentimiento.

Revision ID: 0009_consentimiento_habeas
Revises: 0008_vigencia_ofertas
Create Date: 2026-10-15

La Ley 1581 de 2012 exige poder demostrar que el titular autorizó el
tratamiento de sus datos: qué texto aceptó (version_texto + hash SHA-256
del cuerpo exacto), por qué canal, desde qué IP y cuándo. Una solicitud
acumula consentimientos: el del paso 2 (registrado por el asesor frente
al cliente, canal web_asesor) y el de la firma OTP (canal otp_firma).

Idempotente por CREATE TABLE IF NOT EXISTS.
"""

from alembic import op


revision = "0009_consentimiento_habeas"
down_revision = "0008_vigencia_ofertas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS consentimiento_habeas (
            id_consentimiento BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            id_solicitud UUID NOT NULL REFERENCES solicitud_credito(id_solicitud) ON DELETE CASCADE,
            version_texto VARCHAR(20) NOT NULL,
            hash_texto CHAR(64) NOT NULL,
            canal VARCHAR(20) NOT NULL,
            ip VARCHAR(45),
            fecha_aceptacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT ck_consentimiento_canal CHECK (
                canal IN ('web_asesor', 'otp_firma')
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_consentimiento_solicitud "
        "ON consentimiento_habeas(id_solicitud)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS consentimiento_habeas")
