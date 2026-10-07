"""Solicitudes del esquema SUMOTO: alta, evaluación y ofertas."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.db_models.session import get_db
from backend.models.motor_models import EvaluarSolicitudRequest, ResultadoMotorResponse
from backend.models.solicitud_models import (
    CrearSolicitudRequest,
    CrearSolicitudResponse,
    DesembolsoResponse,
    OfertaResponse,
    RegistrarDesembolsoRequest,
    SeleccionarOfertaRequest,
    SolicitudDetalleResponse,
    SolicitudResumenResponse,
)
from backend.routes.dependencies import get_evaluacion_service
from backend.services.desembolso_service import DesembolsoService
from backend.services.evaluacion_service import EvaluacionService
from backend.services.solicitud_service import SolicitudService

router = APIRouter(prefix="/solicitudes", tags=["solicitudes"])


@router.get("", response_model=list[SolicitudResumenResponse])
def listar(
    estado: str | None = None,
    decision: str | None = None,
    busqueda: str | None = None,
    limite: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[SolicitudResumenResponse]:
    return SolicitudService(db).listar(
        limite=min(limite, 200),
        offset=offset,
        estado=estado,
        decision=decision,
        busqueda=busqueda,
    )


@router.get("/{id_solicitud}", response_model=SolicitudDetalleResponse)
def detalle(
    id_solicitud: uuid.UUID,
    db: Session = Depends(get_db),
) -> SolicitudDetalleResponse:
    return SolicitudService(db).detalle(id_solicitud)


@router.post("", response_model=CrearSolicitudResponse, status_code=status.HTTP_201_CREATED)
def crear(payload: CrearSolicitudRequest, db: Session = Depends(get_db)) -> CrearSolicitudResponse:
    return SolicitudService(db).crear(payload)


@router.post("/{id_solicitud}/evaluar", response_model=ResultadoMotorResponse)
def evaluar(
    id_solicitud: uuid.UUID,
    payload: EvaluarSolicitudRequest,
    servicio: EvaluacionService = Depends(get_evaluacion_service),
) -> ResultadoMotorResponse:
    resultado = servicio.evaluar_solicitud_db(id_solicitud, payload)
    return ResultadoMotorResponse.desde_resultado(resultado, str(id_solicitud))


@router.get("/{id_solicitud}/ofertas", response_model=list[OfertaResponse])
def ofertas(id_solicitud: uuid.UUID, db: Session = Depends(get_db)) -> list[OfertaResponse]:
    return SolicitudService(db).ofertas(id_solicitud)


@router.post("/{id_solicitud}/ofertas/seleccionar", response_model=OfertaResponse)
def seleccionar_oferta(
    id_solicitud: uuid.UUID,
    payload: SeleccionarOfertaRequest,
    db: Session = Depends(get_db),
) -> OfertaResponse:
    return SolicitudService(db).seleccionar_oferta(id_solicitud, payload)


@router.post("/{id_solicitud}/desembolso", response_model=DesembolsoResponse, status_code=status.HTTP_201_CREATED)
def registrar_desembolso(
    id_solicitud: uuid.UUID,
    payload: RegistrarDesembolsoRequest,
    db: Session = Depends(get_db),
) -> DesembolsoResponse:
    """Formaliza el crédito sobre la oferta seleccionada y confirma el
    desembolso a la cuenta de ahorros del cliente. Idempotente: si el
    crédito ya tiene desembolso confirmado devuelve el existente."""
    return DesembolsoService(db).registrar(id_solicitud, payload)
