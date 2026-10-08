"""Siembra idempotente de catálogos base (insert.sql) sobre la BD configurada.

Sirve para desarrollo local, demos y E2E: crea las tablas que falten y
ejecuta backend/database/insert.sql, que es idempotente
(ON CONFLICT DO NOTHING), así que re-correrlo es seguro.

Uso:
    python -m backend.database.seed_demo            # usa DATABASE_URL del entorno
    python -m backend.database.seed_demo ruta.db    # SQLite explícito
"""

import sys
from pathlib import Path

from sqlalchemy import create_engine

from backend.config import get_settings
from backend.db_models.models import Base

INSERT_SQL = Path(__file__).with_name("insert.sql")

# Tablas del esquema SUMOTO sin modelo ORM que insert.sql necesita.
# En Postgres existen vía schema.sql; en SQLite (E2E/desarrollo) hay
# que crearlas a mano porque create_all solo conoce los modelos.
_SQLITE_SCHEMA_EXTRA = """
CREATE TABLE IF NOT EXISTS rol (
    id_rol INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre VARCHAR(30) NOT NULL UNIQUE,
    descripcion VARCHAR(200)
);
CREATE TABLE IF NOT EXISTS concesionario (
    id_concesionario INTEGER PRIMARY KEY AUTOINCREMENT,
    nit VARCHAR(30) UNIQUE,
    nombre VARCHAR(180) NOT NULL UNIQUE,
    id_ciudad INTEGER
);
CREATE TABLE IF NOT EXISTS aliado_concesionario (
    id_aliado INTEGER NOT NULL REFERENCES aliado_financiero(id_aliado),
    id_concesionario INTEGER NOT NULL REFERENCES concesionario(id_concesionario),
    comision_pct NUMERIC(8,4),
    activo BOOLEAN NOT NULL DEFAULT 1,
    fecha_inicio DATE,
    fecha_fin DATE,
    PRIMARY KEY (id_aliado, id_concesionario)
);
"""


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else get_settings().sqlalchemy_database_url()
    if "://" not in url:
        url = f"sqlite:///{url}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    sql = INSERT_SQL.read_text(encoding="utf-8")
    with engine.connect() as conn:
        if engine.dialect.name == "sqlite":
            conn.connection.executescript(_SQLITE_SCHEMA_EXTRA + sql)
        else:
            conn.connection.execute(sql)
        conn.commit()
    print(f"Catálogos sembrados en {url}")


if __name__ == "__main__":
    main()
