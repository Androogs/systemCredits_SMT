"""Motor de decisión: columnas del motor, auditoría y datos de solicitud.

Revision ID: 0002_motor_decision
Revises: 0001_baseline
Create Date: 2026-10-05

Alinea el esquema con lo que necesita el motor de decisión propio
(BRD-IMPL-111350 / PPT v4):

- cliente.primer_apellido: HDC+ exige el primer apellido para consultar.
- datos_laborales.anios_camara_comercio: renombra la columna base
  (anos_camara_comercio) al nombre que usa el motor.
- evaluacion_credito: renombra quanto_3_medio -> quanto3_medio y agrega
  calificacion, reportado_fallecido, score_codigo_exclusion, perfil_score,
  perfil_ingreso y decision_interna.
- solicitud_credito: linea_credito, destino_credito y plazo_deseado_meses
  (el cliente no declara monto: el motor sugiere el cupo).
- motor_evaluacion_auditoria: una fila por evaluación, sin las respuestas
  completas del buró (datos personales de terceros).

Idempotente: todas las operaciones verifican existencia previa.
"""

from alembic import op


revision = "0002_motor_decision"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- Renombres para reutilizar columnas existentes (no duplicar) -----
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'datos_laborales'
                  AND column_name = 'anos_camara_comercio'
            ) THEN
                ALTER TABLE datos_laborales
                    RENAME COLUMN anos_camara_comercio TO anios_camara_comercio;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'evaluacion_credito'
                  AND column_name = 'quanto_3_medio'
            ) THEN
                ALTER TABLE evaluacion_credito
                    RENAME COLUMN quanto_3_medio TO quanto3_medio;
            END IF;
        END
        $$;
        """
    )

    # -- Columnas nuevas ------------------------------------------------
    op.execute(
        """
        ALTER TABLE cliente
            ADD COLUMN IF NOT EXISTS primer_apellido VARCHAR(60);

        ALTER TABLE datos_laborales
            ADD COLUMN IF NOT EXISTS anios_camara_comercio NUMERIC(6,2);

        ALTER TABLE evaluacion_credito
            ADD COLUMN IF NOT EXISTS quanto3_medio NUMERIC(18,2),
            ADD COLUMN IF NOT EXISTS calificacion VARCHAR(5),
            ADD COLUMN IF NOT EXISTS reportado_fallecido BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS score_codigo_exclusion VARCHAR(5),
            ADD COLUMN IF NOT EXISTS perfil_score VARCHAR(10),
            ADD COLUMN IF NOT EXISTS perfil_ingreso VARCHAR(10),
            ADD COLUMN IF NOT EXISTS decision_interna VARCHAR(30);

        ALTER TABLE solicitud_credito
            ADD COLUMN IF NOT EXISTS linea_credito VARCHAR(60),
            ADD COLUMN IF NOT EXISTS destino_credito VARCHAR(80),
            ADD COLUMN IF NOT EXISTS plazo_deseado_meses SMALLINT;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_solicitud_plazo_deseado'
            ) THEN
                ALTER TABLE solicitud_credito
                    ADD CONSTRAINT ck_solicitud_plazo_deseado
                    CHECK (plazo_deseado_meses IS NULL OR plazo_deseado_meses > 0);
            END IF;
        END
        $$;
        """
    )

    # -- Auditoría del motor ---------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS motor_evaluacion_auditoria (
            id               SERIAL PRIMARY KEY,
            evaluacion_id    VARCHAR(36)  NOT NULL UNIQUE,
            fecha_evaluacion TIMESTAMPTZ  NOT NULL DEFAULT now(),
            ambiente         VARCHAR(20)  NOT NULL,
            origen_datos     VARCHAR(40)  NOT NULL,
            id_solicitud     VARCHAR(36),
            tipo_id          VARCHAR(2)   NOT NULL,
            numero_id        VARCHAR(20)  NOT NULL,
            ocupacion        VARCHAR(30)  NOT NULL,
            edad             INTEGER      NOT NULL,
            decision         VARCHAR(20)  NOT NULL,
            decision_interna VARCHAR(30)  NOT NULL,
            causales         TEXT         NOT NULL,
            tiempo_ms        INTEGER      NOT NULL DEFAULT 0,
            request_json     TEXT         NOT NULL,
            resultado_json   TEXT         NOT NULL
        );

        CREATE INDEX IF NOT EXISTS ix_motor_auditoria_fecha
            ON motor_evaluacion_auditoria (fecha_evaluacion);
        CREATE INDEX IF NOT EXISTS ix_motor_auditoria_numero_id
            ON motor_evaluacion_auditoria (numero_id);
        CREATE INDEX IF NOT EXISTS ix_motor_auditoria_decision
            ON motor_evaluacion_auditoria (decision);
        CREATE INDEX IF NOT EXISTS ix_motor_auditoria_solicitud
            ON motor_evaluacion_auditoria (id_solicitud);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS motor_evaluacion_auditoria;

        ALTER TABLE solicitud_credito
            DROP CONSTRAINT IF EXISTS ck_solicitud_plazo_deseado,
            DROP COLUMN IF EXISTS linea_credito,
            DROP COLUMN IF EXISTS destino_credito,
            DROP COLUMN IF EXISTS plazo_deseado_meses;

        ALTER TABLE evaluacion_credito
            DROP COLUMN IF EXISTS calificacion,
            DROP COLUMN IF EXISTS reportado_fallecido,
            DROP COLUMN IF EXISTS score_codigo_exclusion,
            DROP COLUMN IF EXISTS perfil_score,
            DROP COLUMN IF EXISTS perfil_ingreso,
            DROP COLUMN IF EXISTS decision_interna;

        ALTER TABLE cliente
            DROP COLUMN IF EXISTS primer_apellido;
        """
    )
    # Los renombres se restauran solo si la columna nueva existe y la
    # original no (escenario post-upgrade sobre baseline 0001).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'datos_laborales'
                  AND column_name = 'anios_camara_comercio'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'datos_laborales'
                  AND column_name = 'anos_camara_comercio'
            ) THEN
                ALTER TABLE datos_laborales
                    RENAME COLUMN anios_camara_comercio TO anos_camara_comercio;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'evaluacion_credito'
                  AND column_name = 'quanto3_medio'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'evaluacion_credito'
                  AND column_name = 'quanto_3_medio'
            ) THEN
                ALTER TABLE evaluacion_credito
                    RENAME COLUMN quanto3_medio TO quanto_3_medio;
            END IF;
        END
        $$;
        """
    )
