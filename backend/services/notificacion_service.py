"""Notificaciones al cliente: SMS (Twilio), WhatsApp (WATI) y email SMTP.

El OTP va primero por SMS vía Twilio cuando está configurado (WATI quedó
descartado en la práctica), luego WhatsApp como plantilla de autenticación
y por último email. Sin credenciales el envío se registra en log y se
reporta como 'simulado'. Si no hay teléfono válido o el envío falla, se
cae al siguiente canal.
"""

import logging
import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path

from backend.config import get_settings
from backend.db_models.models import SolicitudCredito
from backend.integrations.twilio.client import (
    TwilioClient,
    TwilioError,
    normalizar_telefono_e164,
)
from backend.integrations.wati.client import (
    WatiClient,
    WatiError,
    normalizar_telefono_whatsapp,
)

logger = logging.getLogger(__name__)

PLANTILLAS = {
    "otp": (
        "Código de verificación - Inversiones Pacífico",
        "Tu código de verificación es {codigo}. Vence en {minutos} minutos. "
        "Si no solicitaste este código, ignora este mensaje.",
    ),
    "resultado_aprobado": (
        "Tu crédito fue aprobado - Inversiones Pacífico",
        "{nombre}, tu solicitud {numero} fue aprobada con un cupo de ${monto}. "
        "Tu asesor te contactará para continuar con la formalización.",
    ),
    "resultado_rechazado": (
        "Resultado de tu solicitud - Inversiones Pacífico",
        "{nombre}, tu solicitud {numero} no fue aprobada en esta oportunidad. "
        "Puedes acercarte al concesionario para revisar alternativas.",
    ),
    "oferta": (
        "Oferta de crédito confirmada - Inversiones Pacífico",
        "{nombre}, confirmamos la oferta de tu solicitud {numero}: "
        "${monto} a {plazo} meses, cuota aproximada de ${cuota}.",
    ),
    "desembolso": (
        "Desembolso realizado - Inversiones Pacífico",
        "{nombre}, el desembolso de tu crédito {numero} fue registrado. "
        "La entrega del vehículo se coordina en el concesionario.",
    ),
    # Recuperación de clave (D124): va al correo del usuario de la
    # plataforma, no al cliente — `notificar` la usa con `destino` y sin
    # solicitud asociada.
    "recuperacion_clave": (
        "Restablece tu contraseña - Inversiones Pacífico",
        "{nombre}, recibimos una solicitud para restablecer tu "
        "contraseña. Ingresa a {enlace} para definir una nueva. "
        "El enlace vence en {minutos} minutos y solo se puede usar una "
        "vez. Si no fuiste tú, ignora este correo.",
    ),
    "legalizacion": (
        "Documentos de tu crédito - Inversiones Pacífico",
        "{nombre}, tu crédito {numero} quedó firmado. Adjuntamos el "
        "paquete de documentos legales (autorización de centrales, carta "
        "de aprobación, pagaré, carta de instrucciones, prenda, "
        "declaración de asegurabilidad y compromiso de pago).",
    ),
}


class NotificacionService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._wati = WatiClient(self._settings)
        self._twilio = TwilioClient(self._settings)

    def _contexto(
        self, solicitud: SolicitudCredito | None, datos: dict
    ) -> dict:
        return {
            "nombre": (
                solicitud.cliente.nombre_completo.split(" ")[0]
                if solicitud and solicitud.cliente
                else "Cliente"
            ),
            "numero": (
                f"#{solicitud.num_solicitud:06d}"
                if solicitud and solicitud.num_solicitud
                else ""
            ),
            **datos,
        }

    def _intentar_sms(
        self,
        evento: str,
        solicitud: SolicitudCredito | None,
        datos: dict,
    ) -> dict | None:
        """SMS vía Twilio Messages API. None = continuar por otro canal."""
        if not self._twilio.configurado:
            return None
        contacto = solicitud.contacto_vivienda if solicitud else None
        telefono = normalizar_telefono_e164(
            contacto.telefono if contacto else None
        )
        if not telefono:
            logger.info(
                "[sms %s] sin teléfono válido del cliente; cae a email",
                evento,
            )
            return None
        _, plantilla = PLANTILLAS[evento]
        try:
            cuerpo = plantilla.format(**self._contexto(solicitud, datos))
        except KeyError:
            cuerpo = plantilla
        try:
            self._twilio.enviar_sms(telefono, cuerpo)
        except TwilioError:
            logger.exception(
                "Falló el envío SMS a %s; cae a email", telefono
            )
            return None
        return {"canal": "sms", "estado": "enviado", "destino": telefono}

    def _plantilla_whatsapp(
        self, evento: str, datos: dict
    ) -> tuple[str, list[str]] | None:
        """Plantilla WATI y parámetros posicionales del evento.

        None = el evento no tiene canal WhatsApp. Para sumar otro evento
        (oferta, desembolso, …) basta una rama aquí y su plantilla
        aprobada en WATI.
        """
        if evento == "otp":
            # La plantilla de autenticación solo declara {{1}} = código;
            # el aviso de vencimiento es texto fijo aprobado por Meta.
            return self._settings.wati_plantilla_otp, [str(datos["codigo"])]
        return None

    def _intentar_whatsapp(
        self,
        evento: str,
        solicitud: SolicitudCredito | None,
        datos: dict,
    ) -> dict | None:
        """Envío por WhatsApp vía WATI. None = continuar por email."""
        plantilla = self._plantilla_whatsapp(evento, datos)
        if plantilla is None:
            return None
        contacto = solicitud.contacto_vivienda if solicitud else None
        telefono = normalizar_telefono_whatsapp(
            contacto.telefono if contacto else None
        )
        if not telefono:
            logger.info(
                "[whatsapp %s] sin teléfono válido del cliente; cae a email",
                evento,
            )
            return None
        nombre_plantilla, parametros = plantilla
        if not self._wati.configurado:
            logger.info(
                "[whatsapp simulado] a=%s plantilla=%s",
                telefono,
                nombre_plantilla,
            )
            return {
                "canal": "whatsapp",
                "estado": "simulado",
                "destino": telefono,
            }
        try:
            self._wati.enviar_plantilla(
                telefono,
                nombre_plantilla,
                parametros,
                broadcast_name=evento,
            )
        except WatiError:
            logger.exception(
                "Falló el envío WhatsApp a %s; cae a email", telefono
            )
            return None
        return {"canal": "whatsapp", "estado": "enviado", "destino": telefono}

    @property
    def _smtp_configurado(self) -> bool:
        return bool(self._settings.smtp_host and self._settings.smtp_desde)

    def _enviar_email(
        self,
        destino: str,
        asunto: str,
        cuerpo: str,
        adjuntos: list[Path] | None = None,
    ) -> str:
        """Envía por SMTP; sin configuración, simula con log."""
        if not self._smtp_configurado:
            logger.info(
                "[notificación simulada] a=%s asunto=%s adjuntos=%d",
                destino,
                asunto,
                len(adjuntos or []),
            )
            return "simulado"
        mensaje = EmailMessage()
        mensaje["From"] = self._settings.smtp_desde
        mensaje["To"] = destino
        mensaje["Subject"] = asunto
        mensaje.set_content(cuerpo)
        for adjunto in adjuntos or []:
            mime = mimetypes.guess_type(adjunto.name)[0]
            maintype, subtype = (mime or "application/octet-stream").split("/", 1)
            mensaje.add_attachment(
                adjunto.read_bytes(),
                maintype=maintype,
                subtype=subtype,
                filename=adjunto.name,
            )
        try:
            with smtplib.SMTP(
                self._settings.smtp_host, self._settings.smtp_port, timeout=15
            ) as smtp:
                if self._settings.smtp_tls:
                    smtp.starttls()
                if self._settings.smtp_user:
                    smtp.login(
                        self._settings.smtp_user, self._settings.smtp_password
                    )
                smtp.send_message(mensaje)
            return "enviado"
        except OSError:
            logger.exception("Falló el envío SMTP a %s", destino)
            return "fallido"

    def notificar(
        self,
        evento: str,
        solicitud: SolicitudCredito | None = None,
        *,
        destino: str | None = None,
        datos: dict | None = None,
        adjuntos: list[Path] | None = None,
        canal: str = "email",
    ) -> dict:
        """Envía la notificación del evento al cliente.

        Devuelve {canal, estado, destino}; sin contacto registrado el
        evento queda 'sin_destino' y no bloquea la operación principal.
        Con canal='sms' intenta Twilio y cae a email. Con canal='whatsapp'
        intenta primero SMS (Twilio es el canal OTP vigente), luego WATI
        y por último email; en ambos casos se cae a email cuando el
        teléfono no es válido o el envío falla.
        """
        datos = datos or {}
        if canal == "sms":
            envio = self._intentar_sms(evento, solicitud, datos)
            if envio is not None:
                return envio
        elif canal == "whatsapp":
            envio = self._intentar_sms(evento, solicitud, datos)
            if envio is None:
                envio = self._intentar_whatsapp(evento, solicitud, datos)
            if envio is not None:
                return envio
        if solicitud is not None and destino is None:
            contacto = solicitud.contacto_vivienda
            destino = contacto.correo if contacto else None
        if not destino:
            logger.info("[notificación %s] sin correo del cliente", evento)
            return {"canal": "email", "estado": "sin_destino", "destino": None}
        asunto, plantilla = PLANTILLAS[evento]
        contexto = self._contexto(solicitud, datos)
        try:
            cuerpo = plantilla.format(**contexto)
        except KeyError:
            cuerpo = plantilla
        estado = self._enviar_email(destino, asunto, cuerpo, adjuntos)
        return {"canal": "email", "estado": estado, "destino": destino}
