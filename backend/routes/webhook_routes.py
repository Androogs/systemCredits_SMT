"""Webhook de confirmación asíncrona del desembolso.

POST /webhook/desembolso — lo llama el emisor (tesorería del aliado
financiero propio o el core bancario) durante el ciclo del giro:
`en_transito` anuncia que la transferencia salió (desembolso
pendiente), `confirmado` la acredita y `rechazado` reporta el fallo,
sin que un operador tenga que registrar el desembolso a mano.

Es un endpoint público: no hay sesión. La autenticación es la firma
HMAC-SHA256 del cuerpo crudo con el secreto compartido
(`webhook_secreto`), enviada en `X-Signature: sha256=<hex>`, más el
`X-Timestamp` unix dentro de la ventana configurada (anti-replay).

El evento queda trazado en el log estructurado `creditos.webhook`
(payload, firma verificada y resultado) y la confirmación reusa
`DesembolsoService.registrar`, que ya es idempotente y replica las
validaciones del trigger de Postgres.
"""

import hashlib
import hmac
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db_models.models import (
    CreditoFinanciacion,
    Desembolso,
    SolicitudCredito,
)
from backend.db_models.session import get_db
from backend.models.solicitud_models import RegistrarDesembolsoRequest
from backend.models.webhook_models import WebhookDesembolsoRequest
from backend.services.desembolso_service import DesembolsoService
from backend.services.motor_exceptions import (
    ConflictoEstadoError,
    SolicitudNoEncontradaError,
    ValidacionError,
)

router = APIRouter(prefix="/webhook", tags=["webhook"])
logger = logging.getLogger("creditos.webhook")


def _verificar_firma(body: bytes, request: Request) -> None:
    """HMAC-SHA256 del body con el secreto + timestamp en ventana."""
    settings = get_settings()
    if not settings.webhook_secreto:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Webhook deshabilitado: falta WEBHOOK_SECRETO en el entorno.",
        )
    firma = request.headers.get("X-Signature", "")
    ts = request.headers.get("X-Timestamp", "")
    if not firma.startswith("sha256=") or not ts:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Faltan los headers X-Signature (sha256=…) y X-Timestamp.",
        )
    try:
        edad = abs(time.time() - int(ts))
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "X-Timestamp inválido.")
    if edad > settings.webhook_ventana_segundos:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Firma expirada: el timestamp sale de la ventana permitida.",
        )
    esperado = hmac.new(
        settings.webhook_secreto.encode(),
        ts.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(esperado, firma.removeprefix("sha256=")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Firma no válida.")


def _resolver_solicitud(db: Session, payload: WebhookDesembolsoRequest) -> SolicitudCredito:
    consulta = db.query(SolicitudCredito)
    solicitud = (
        consulta.filter(SolicitudCredito.id_solicitud == payload.id_solicitud).one_or_none()
        if payload.id_solicitud is not None
        else consulta.filter(SolicitudCredito.num_solicitud == payload.num_solicitud).one_or_none()
    )
    if solicitud is None:
        raise SolicitudNoEncontradaError(
            f"El webhook referencia una solicitud inexistente "
            f"(id_solicitud={payload.id_solicitud}, num_solicitud={payload.num_solicitud})."
        )
    return solicitud


def _confirmar(
    db: Session,
    solicitud: SolicitudCredito,
    payload: WebhookDesembolsoRequest,
    estado_desembolso: str = "confirmado",
):
    req = RegistrarDesembolsoRequest(
        codigo_ach_banco=payload.codigo_ach_banco or "",
        numero_cuenta_cliente=payload.numero_cuenta_cliente or "",
        titular_cuenta=payload.titular_cuenta,
        referencia_pago=payload.referencia_pago or payload.id_evento,
    )
    return DesembolsoService(db).registrar(
        solicitud.id_solicitud, req, estado_desembolso=estado_desembolso
    )


def _rechazar(db: Session, solicitud: SolicitudCredito, payload: WebhookDesembolsoRequest):
    """El giro falló en el emisor: marca el desembolso pendiente como
    rechazado; no se permite rechazar lo que no estaba en tránsito."""
    credito = (
        db.query(CreditoFinanciacion)
        .filter(CreditoFinanciacion.id_solicitud == solicitud.id_solicitud)
        .one_or_none()
    )
    desembolso = (
        db.query(Desembolso)
        .filter(Desembolso.id_credito == credito.id_credito)
        .one_or_none()
        if credito is not None
        else None
    )
    if desembolso is None:
        raise ConflictoEstadoError(
            f"La solicitud {solicitud.id_solicitud} no tiene desembolso en tránsito que rechazar."
        )
    if desembolso.estado != "pendiente":
        raise ConflictoEstadoError(
            f"El desembolso {desembolso.num_desembolso} ya está {desembolso.estado}; no se puede rechazar."
        )
    desembolso.estado = "rechazado"
    db.flush()
    return desembolso


@router.post("/desembolso", status_code=status.HTTP_200_OK)
async def webhook_desembolso(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    _verificar_firma(body, request)
    try:
        payload = WebhookDesembolsoRequest.model_validate_json(body)
    except Exception as exc:  # noqa: BLE001
        raise ValidacionError(f"Cuerpo de webhook inválido: {exc}") from exc

    solicitud = _resolver_solicitud(db, payload)
    if payload.estado == "en_transito":
        resultado = _confirmar(db, solicitud, payload, estado_desembolso="pendiente")
    elif payload.estado == "confirmado":
        resultado = _confirmar(db, solicitud, payload)
    else:
        resultado = _rechazar(db, solicitud, payload)

    logger.info(
        "webhook desembolso | solicitud=%s | estado=%s | id_evento=%s | referencia=%s | motivo=%s",
        solicitud.id_solicitud,
        payload.estado,
        payload.id_evento,
        payload.referencia_pago,
        payload.motivo,
    )
    return {
        "id_solicitud": str(solicitud.id_solicitud),
        "num_solicitud": solicitud.num_solicitud,
        "estado": getattr(resultado, "estado", payload.estado),
        "num_desembolso": getattr(resultado, "num_desembolso", None),
        "referencia_pago": getattr(resultado, "referencia_pago", None),
    }
