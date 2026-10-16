"""Solicitudes del esquema SUMOTO: alta, evaluación y ofertas."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db_models.session import get_db
from backend.models.motor_models import EvaluarSolicitudRequest, ResultadoMotorResponse
from backend.models.solicitud_models import (
    CancelarSolicitudRequest,
    CrearSolicitudRequest,
    CrearSolicitudResponse,
    DatosFormalizacionRequest,
    DesembolsoResponse,
    GenerarOtpRequest,
    GenerarOtpResponse,
    OfertaResponse,
    RegistrarDesembolsoRequest,
    SeleccionarOfertaRequest,
    SolicitudDetalleResponse,
    SolicitudResumenResponse,
    VerificarOtpRequest,
    VerificarOtpResponse,
)
from backend.repositories.solicitud_repository import SolicitudRepository
from backend.routes.dependencies import get_evaluacion_service
from backend.services.desembolso_service import DesembolsoService
from backend.services.documento_service import DocumentoService
from backend.services.evaluacion_service import EvaluacionService
from backend.services.notificacion_service import NotificacionService
from backend.services.otp_service import OtpError, OtpService
from backend.services.solicitud_service import SolicitudService

router = APIRouter(prefix="/solicitudes", tags=["solicitudes"])


def _paquete_legalizacion(db: Session, id_solicitud: uuid.UUID) -> None:
    """Genera el paquete de documentos y lo envía al correo del cliente.

    Best-effort: la firma quedó registrada aunque la generación o el
    envío fallen; el asesor puede regenerarlo desde el detalle.
    """
    from pathlib import Path

    try:
        docs = DocumentoService(db).generar_paquete(id_solicitud)
        if not docs:
            return
        settings = get_settings()
        adjuntos = [Path(settings.evidencias_dir) / d.ruta for d in docs]
        solicitud = SolicitudRepository(db).obtener_detalle(id_solicitud)
        if solicitud is not None:
            NotificacionService().notificar(
                "legalizacion", solicitud, adjuntos=adjuntos
            )
    except Exception:  # noqa: BLE001
        import logging

        # La sesión quedó con la transacción en error: rollback para que
        # el commit final de get_db (firma/OTP ya commitados, pero la
        # sesión sigue abierta) no falle.
        db.rollback()
        logging.getLogger(__name__).exception(
            "No se pudo generar el paquete de legalización de %s", id_solicitud
        )


def _notificar(db: Session, id_solicitud: uuid.UUID, evento: str, datos: dict | None = None) -> None:
    """Notificación best-effort: nunca bloquea la operación principal."""
    try:
        solicitud = SolicitudRepository(db).obtener_detalle(id_solicitud)
        if solicitud is not None:
            NotificacionService().notificar(evento, solicitud, datos=datos)
    except Exception:  # noqa: BLE001
        pass


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
def crear(
    payload: CrearSolicitudRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> CrearSolicitudResponse:
    return SolicitudService(db).crear(
        payload, ip=request.client.host if request.client else None
    )


@router.post("/{id_solicitud}/evaluar", response_model=ResultadoMotorResponse)
def evaluar(
    id_solicitud: uuid.UUID,
    payload: EvaluarSolicitudRequest,
    servicio: EvaluacionService = Depends(get_evaluacion_service),
    db: Session = Depends(get_db),
) -> ResultadoMotorResponse:
    resultado = servicio.evaluar_solicitud_db(id_solicitud, payload)
    respuesta = ResultadoMotorResponse.desde_resultado(resultado, str(id_solicitud))
    aprobado = getattr(resultado.decision, "value", resultado.decision) == "Aprobado"
    _notificar(
        db,
        id_solicitud,
        "resultado_aprobado" if aprobado else "resultado_rechazado",
        datos={
            "monto": f"{float(getattr(resultado, 'cupo_sugerido', 0) or 0):,.0f}".replace(",", ".")
        },
    )
    return respuesta


@router.get("/{id_solicitud}/ofertas", response_model=list[OfertaResponse])
def ofertas(id_solicitud: uuid.UUID, db: Session = Depends(get_db)) -> list[OfertaResponse]:
    return SolicitudService(db).ofertas(id_solicitud)


@router.post("/{id_solicitud}/ofertas/seleccionar", response_model=OfertaResponse)
def seleccionar_oferta(
    id_solicitud: uuid.UUID,
    payload: SeleccionarOfertaRequest,
    db: Session = Depends(get_db),
) -> OfertaResponse:
    oferta = SolicitudService(db).seleccionar_oferta(id_solicitud, payload)
    _notificar(
        db,
        id_solicitud,
        "oferta",
        datos={
            "monto": f"{float(oferta.monto_aprobado or 0):,.0f}".replace(",", "."),
            "plazo": oferta.plazo_ofrecido or 0,
            "cuota": f"{float(oferta.cuota_mensual or 0):,.0f}".replace(",", "."),
        },
    )
    return oferta


@router.post("/{id_solicitud}/cancelar", response_model=SolicitudResumenResponse)
def cancelar(
    id_solicitud: uuid.UUID,
    payload: CancelarSolicitudRequest,
    db: Session = Depends(get_db),
) -> SolicitudResumenResponse:
    """Anula la solicitud con motivo obligatorio. 409 si ya está
    desembolsada o cancelada; el historial lo escribe el trigger de BD."""
    return SolicitudService(db).cancelar(id_solicitud, payload.motivo)


@router.put("/{id_solicitud}/datos-formalizacion", status_code=status.HTTP_204_NO_CONTENT)
def datos_formalizacion(
    id_solicitud: uuid.UUID,
    payload: DatosFormalizacionRequest,
    db: Session = Depends(get_db),
) -> None:
    """Información adicional del cliente (residencia, personal, financiera
    y laboral) capturada en la formalización, antes de la firma OTP."""
    SolicitudService(db).guardar_datos_formalizacion(id_solicitud, payload)


@router.post("/{id_solicitud}/otp", response_model=GenerarOtpResponse, status_code=status.HTTP_201_CREATED)
def generar_otp(
    id_solicitud: uuid.UUID,
    payload: GenerarOtpRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> GenerarOtpResponse:
    """Emite un OTP por el canal pedido (tabla `otp`, solo hash)."""
    solicitud = SolicitudRepository(db).obtener_detalle(id_solicitud)
    if solicitud is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Solicitud no encontrada")
    settings = get_settings()
    otp, codigo = OtpService(db).generar(
        id_solicitud,
        payload.accion,
        ip=request.client.host if request.client else None,
    )
    envio = NotificacionService().notificar(
        "otp",
        solicitud,
        datos={"codigo": codigo, "minutos": settings.otp_ttl_minutos},
        canal=payload.canal,
    )
    # El canal por el que realmente salió el código queda en el OTP para
    # sellar la firma con la autenticación correcta (otp_whatsapp/email).
    otp.autenticacion = envio["canal"]
    return GenerarOtpResponse(
        id_otp=otp.id_otp,
        expira_en_segundos=settings.otp_ttl_minutos * 60,
        canal=envio["canal"],
        destino=envio["destino"],
        estado_envio=envio["estado"],
        codigo_demo=codigo if settings.environment == "demo" else None,
    )


@router.post("/{id_solicitud}/otp/verificar", response_model=VerificarOtpResponse)
def verificar_otp(
    id_solicitud: uuid.UUID,
    payload: VerificarOtpRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> VerificarOtpResponse:
    """Valida el OTP; al aprobar la acción 'firma_pagare' firma la solicitud."""
    try:
        otp = OtpService(db).verificar(id_solicitud, payload.accion, payload.codigo)
    except OtpError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    uuid_firma = None
    if payload.accion == "firma_pagare":
        solicitud = SolicitudRepository(db).obtener_detalle(id_solicitud)
        if solicitud is not None:
            uuid_firma = uuid.uuid4()
            solicitud.uuid_firma = uuid_firma
            solicitud.fecha_hora_firma = datetime.now(UTC)
            # Sella con el canal por el que salió el código (otp_whatsapp
            # u otp_email, según haya resuelto el envío).
            solicitud.autenticacion = f"otp_{otp.autenticacion or 'email'}"
            # La firma OTP también sella el consentimiento Habeas Data:
            # qué texto aceptó (versión + hash) y desde dónde firmó.
            SolicitudService(db).registrar_consentimiento(
                id_solicitud,
                "otp_firma",
                ip=request.client.host if request.client else None,
            )
        # La firma se persiste ANTES de generar el paquete: si la
        # generación falla, la firma queda sellada y el paquete se
        # puede regenerar sin repetir el OTP.
        db.commit()
        _paquete_legalizacion(db, id_solicitud)
    return VerificarOtpResponse(verificado=True, uuid_firma=uuid_firma)


@router.post("/{id_solicitud}/desembolso", response_model=DesembolsoResponse, status_code=status.HTTP_201_CREATED)
def registrar_desembolso(
    id_solicitud: uuid.UUID,
    payload: RegistrarDesembolsoRequest,
    db: Session = Depends(get_db),
) -> DesembolsoResponse:
    """Formaliza el crédito sobre la oferta seleccionada y confirma el
    desembolso a la cuenta de ahorros del cliente. Idempotente: si el
    crédito ya tiene desembolso confirmado devuelve el existente."""
    desembolso = DesembolsoService(db).registrar(id_solicitud, payload)
    _notificar(db, id_solicitud, "desembolso")
    return desembolso
