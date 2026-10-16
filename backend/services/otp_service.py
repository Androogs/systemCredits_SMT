"""OTP de un solo uso ligado a una solicitud y una acción.

El código viaja al correo del cliente vía NotificacionService; en la
base de datos solo queda su hash. Un OTP aprobado valida la firma del
pagaré (accion='firma_pagare').
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db_models.models import Otp


class OtpError(Exception):
    """OTP inválido, vencido o sin intentos disponibles."""


def _ahora() -> datetime:
    return datetime.now(UTC)


def _hash(codigo: str, id_solicitud: uuid.UUID) -> str:
    return hashlib.sha256(f"{codigo}:{id_solicitud}".encode()).hexdigest()


class OtpService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._settings = get_settings()

    def generar(
        self,
        id_solicitud: uuid.UUID,
        accion: str,
        *,
        ip: str | None = None,
        autenticacion: str = "email",
    ) -> tuple[Otp, str]:
        """Crea un OTP nuevo, invalidando los pendientes de la acción."""
        anteriores = (
            self._db.query(Otp)
            .filter(
                Otp.id_solicitud == id_solicitud,
                Otp.accion == accion,
                Otp.estado == "pendiente",
            )
            .all()
        )
        for anterior in anteriores:
            anterior.estado = "expirado"

        codigo = f"{secrets.randbelow(1_000_000):06d}"
        otp = Otp(
            id_solicitud=id_solicitud,
            codigo_otp_hash=_hash(codigo, id_solicitud),
            fecha_expiracion=_ahora()
            + timedelta(minutes=self._settings.otp_ttl_minutos),
            intentos_fallidos=0,
            ip_solicitud=ip,
            autenticacion=autenticacion,
            accion=accion,
            estado="pendiente",
        )
        self._db.add(otp)
        self._db.flush()
        return otp, codigo

    def verificar(
        self, id_solicitud: uuid.UUID, accion: str, codigo: str
    ) -> Otp:
        otp = (
            self._db.query(Otp)
            .filter(
                Otp.id_solicitud == id_solicitud,
                Otp.accion == accion,
                Otp.estado == "pendiente",
            )
            .order_by(Otp.id_otp.desc())
            .first()
        )
        if otp is None:
            raise OtpError("No hay un código vigente para esta acción.")
        ahora = _ahora()
        expira = otp.fecha_expiracion
        if expira.tzinfo is None:
            expira = expira.replace(tzinfo=UTC)
        if ahora > expira:
            otp.estado = "expirado"
            raise OtpError("El código venció; solicita uno nuevo.")
        if not secrets.compare_digest(
            otp.codigo_otp_hash, _hash(codigo, id_solicitud)
        ):
            otp.intentos_fallidos += 1
            if otp.intentos_fallidos >= self._settings.otp_max_intentos:
                otp.estado = "fallido"
            restantes = max(
                self._settings.otp_max_intentos - otp.intentos_fallidos, 0
            )
            raise OtpError(
                f"Código incorrecto; quedan {restantes} intentos."
            )
        otp.estado = "aprobado"
        otp.otp_aprobacion = ahora
        otp.fecha_hora_otp_aprobacion = ahora
        self._db.flush()
        return otp
