"""Tablas de captura remota de evidencias documentales.

Revision ID: 0005_evidencias
Revises: 0004_auditoria_parametros
Create Date: 2026-10-07

sesion_captura: link temporal con token para que el cliente suba la
cédula (frontal/reverso) y el video de prueba de vida desde su celular.
documento_evidencia: cada archivo subido, con ruta en disco y hash de
integridad. La sesión se enlaza a la solicitud cuando esta se crea.
"""

from alembic import op


revision = "0005_evidencias"
down_revision = "0004_auditoria_parametros"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS: la baseline (0001) ejecuta el schema.sql actual, que ya
    # incluye estas tablas; en bases antiguas sí crean las tablas.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sesion_captura (
            id_sesion    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            token        VARCHAR(64)  NOT NULL UNIQUE,
            estado       VARCHAR(20)  NOT NULL DEFAULT 'pendiente',
            id_solicitud UUID         REFERENCES solicitud_credito (id_solicitud),
            expira_en    TIMESTAMPTZ  NOT NULL,
            creado_en    TIMESTAMPTZ  NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS documento_evidencia (
            id_evidencia    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            id_sesion       UUID         NOT NULL REFERENCES sesion_captura (id_sesion) ON DELETE CASCADE,
            id_solicitud    UUID         REFERENCES solicitud_credito (id_solicitud),
            tipo            VARCHAR(20)  NOT NULL,
            ruta            VARCHAR(255) NOT NULL,
            nombre_original VARCHAR(255),
            mime            VARCHAR(60)  NOT NULL,
            tamano_bytes    BIGINT       NOT NULL,
            hash_sha256     VARCHAR(64)  NOT NULL,
            creado_en       TIMESTAMPTZ  NOT NULL DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS ix_sesion_captura_estado    ON sesion_captura (estado);
        CREATE INDEX IF NOT EXISTS ix_sesion_captura_solicitud ON sesion_captura (id_solicitud);
        CREATE INDEX IF NOT EXISTS ix_evidencia_sesion         ON documento_evidencia (id_sesion);
        CREATE INDEX IF NOT EXISTS ix_evidencia_solicitud      ON documento_evidencia (id_solicitud);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS documento_evidencia")
    op.execute("DROP TABLE IF EXISTS sesion_captura")
