"""Parámetros del motor editables en caliente (se validan antes de guardar)."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, create_model

from backend.auth.dependencies import requiere_roles
from backend.routes.dependencies import get_store
from backend.services.motor_exceptions import ValidacionError
from backend.services.motor_parametros import MotorParametros, ParametrosStore

router = APIRouter(
    prefix="/parametros",
    tags=["parametros"],
    dependencies=[Depends(requiere_roles("admin"))],
)

# Modelo parcial: todos los campos de MotorParametros como opcionales.
ParametrosUpdate: type[BaseModel] = create_model(  # type: ignore[call-overload]
    "ParametrosUpdate",
    __config__={"extra": "forbid"},
    **{nombre: (campo.annotation | None, None) for nombre, campo in MotorParametros.model_fields.items()},
)


def _respuesta(store: ParametrosStore, params: MotorParametros) -> dict[str, Any]:
    return {"parametros": params.snapshot(), "bloqueados_por_entorno": store.campos_bloqueados_por_entorno()}


@router.get("")
def obtener(store: ParametrosStore = Depends(get_store)) -> dict[str, Any]:
    return _respuesta(store, store.cargar())


@router.put("")
def actualizar(payload: ParametrosUpdate, store: ParametrosStore = Depends(get_store)) -> dict[str, Any]:  # type: ignore[valid-type]
    cambios = payload.model_dump(exclude_none=True)
    if not cambios:
        raise ValidacionError("No se enviaron cambios.")
    return _respuesta(store, store.actualizar(cambios))


@router.post("/reset")
def restablecer(store: ParametrosStore = Depends(get_store)) -> dict[str, Any]:
    return _respuesta(store, store.restablecer())
