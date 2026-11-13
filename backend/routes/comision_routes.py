"""Consulta de comisiones del asesor (D134)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.auth.dependencies import UsuarioActual, requiere_roles
from backend.db_models.session import get_db
from backend.models.comision_models import ComisionesResponse
from backend.services.comision_service import ComisionService

router = APIRouter(prefix="/comisiones", tags=["comisiones"])


@router.get("/mias", response_model=ComisionesResponse)
def mis_comisiones(
    usuario: UsuarioActual = Depends(requiere_roles("asesor", "admin")),
    db: Session = Depends(get_db),
) -> ComisionesResponse:
    """Comisiones sobre desembolsos confirmados (capital, base sin
    gastos administrativos y comisión) con totales por mes.

    El asesor ve solo su producción; el admin ve la de todos — cada
    fila lleva el nombre del radicador."""
    return ComisionService(db).resumen(usuario)
