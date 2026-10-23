"""Dependencias compartidas de las rutas."""

from functools import lru_cache

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.auth.dependencies import UsuarioActual
from backend.config import get_settings
from backend.db_models.session import get_db
from backend.repositories.usuario_repository import UsuarioRepository
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


def auditar_acceso(
    db: Session,
    usuario: UsuarioActual,
    accion: str,
    descripcion: str,
    request: Request,
) -> None:
    """Registra en `auditoria_usuario` el acceso a datos sensibles
    (detalle de solicitud, contenido de evidencias, paquete legal)."""
    UsuarioRepository(db).auditar(
        id_usuario=usuario.id_usuario,
        accion=accion,
        descripcion=descripcion[:500],
        ip=request.client.host if request.client else None,
    )
