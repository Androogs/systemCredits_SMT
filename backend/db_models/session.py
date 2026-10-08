"""Motor de base de datos, sesiones y creación de tablas."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.config import get_settings
from backend.db_models.base import Base


def crear_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url or url in ("sqlite://", "sqlite:///"):
            kwargs["poolclass"] = StaticPool
        return create_engine(url, **kwargs)
    return create_engine(url, pool_pre_ping=True)


engine: Engine = crear_engine(get_settings().sqlalchemy_database_url())
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def configurar_engine(url: str) -> None:
    """Reemplaza el engine (pruebas o scripts)."""
    global engine
    engine = crear_engine(url)
    SessionLocal.configure(bind=engine)


def crear_tablas() -> None:
    from backend.db_models import auditoria_models, evidencia_models, models  # noqa: F401  (registra tablas)

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """Dependencia FastAPI: una transacción por request."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
