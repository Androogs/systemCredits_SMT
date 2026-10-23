"""Dependencias compartidas de las rutas."""

from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db_models.session import get_db
from backend.services.evaluacion_service import EvaluacionService
from backend.services.motor_parametros import ParametrosStore


@lru_cache
def get_store() -> ParametrosStore:
    return ParametrosStore(get_settings().parametros_path)


def get_evaluacion_service(
    db: Session = Depends(get_db),
    store: ParametrosStore = Depends(get_store),
) -> EvaluacionService:
    return EvaluacionService(db=db, settings=get_settings(), store=store)
