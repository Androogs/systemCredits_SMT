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
from backend.db_models.session import crear_tablas_engine

INSERT_SQL = Path(__file__).with_name("insert.sql")


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else get_settings().sqlalchemy_database_url()
    if "://" not in url:
        url = f"sqlite:///{url}"
    engine = create_engine(url)
    crear_tablas_engine(engine)
    sql = INSERT_SQL.read_text(encoding="utf-8")
    if engine.dialect.name == "sqlite":
        with engine.connect() as conn:
            conn.connection.executescript(sql)
            conn.commit()
    else:
        # psycopg3 raw: soporta multi-statement sin binding de params;
        # exec_driver_sql intentaría bindear y los '%' de comentarios romperían.
        raw = engine.raw_connection()
        try:
            raw.cursor().execute(sql)
            raw.commit()
        finally:
            raw.close()
    print(f"Catálogos sembrados en {url}")


if __name__ == "__main__":
    main()
