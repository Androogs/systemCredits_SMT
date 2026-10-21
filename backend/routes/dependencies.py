"""Dependencias compartidas de las rutas."""

from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db_models.session import get_db
from backend.services.evaluacion_service import EvaluacionService
from backend.services.motor_parametros import ParametrosStore
from backend.services.tasa_mercado_service import (
    TasaMercadoService,
    crear_servicio_tasa_mercado,
)


@lru_cache
def get_store() -> ParametrosStore:
    return ParametrosStore(get_settings().parametros_path)


@lru_cache
def get_tasa_mercado_service() -> TasaMercadoService:
    """Una instancia por proceso para que el caché en memoria sirva."""
    return crear_servicio_tasa_mercado(get_settings())


def get_evaluacion_service(
    db: Session = Depends(get_db),
    store: ParametrosStore = Depends(get_store),
) -> EvaluacionService:
    return EvaluacionService(db=db, settings=get_settings(), store=store)
