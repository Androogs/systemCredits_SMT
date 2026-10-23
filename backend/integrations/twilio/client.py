"""Cliente Twilio: SMS por Messages API y OTP por Verify API.

Messages API (funciona en cuenta trial): envía un SMS con el texto que
le pasemos — usado hoy para el OTP mientras WATI quedó descartado. En
trial solo llega a números verificados en la consola y los mensajes
llevan el prefijo "Sent from a Twilio trial account".

Verify API (requiere cuenta paga — `twilio_verify_sid` VAxxxx): Twilio
genera, expira y reintenta el código solo; queda implementado para el
día que se habilite el servicio en consola. Un 201 de Messages significa
"encolado", no entregado.
"""

import logging

import httpx

from backend.config import Settings, get_settings
from backend.integrations.wati.client import normalizar_telefono_whatsapp

logger = logging.getLogger(__name__)


class TwilioError(Exception):
    """Transporte fallido o envío rechazado por Twilio."""


def normalizar_telefono_e164(telefono: str | None) -> str | None:
    """Deja el teléfono en E.164 (+573001234567) para Twilio; reutiliza
    la normalización local del cliente WATI y solo antepone '+'."""
    digitos = normalizar_telefono_whatsapp(telefono)
    return f"+{digitos}" if digitos else None


class TwilioClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def configurado(self) -> bool:
        s = self._settings
        return bool(
            s.twilio_account_sid
            and s.twilio_auth_token
            and (s.twilio_from_number or s.twilio_messaging_service_sid)
        )

    @property
    def verify_configurado(self) -> bool:
        s = self._settings
        return bool(
            s.twilio_account_sid and s.twilio_auth_token and s.twilio_verify_sid
        )

    def _post(self, url: str, data: dict) -> dict:
        s = self._settings
        try:
            with httpx.Client(timeout=s.twilio_timeout_segundos) as client:
                resp = client.post(
                    url,
                    data=data,  # la API de Twilio recibe form-urlencoded
                    auth=(s.twilio_account_sid, s.twilio_auth_token),
                )
        except httpx.RequestError as exc:
            raise TwilioError(f"Error de red hacia Twilio: {exc}") from exc
        try:
            payload = resp.json()
        except ValueError as exc:
            raise TwilioError(
                f"Twilio respondió {resp.status_code} sin JSON"
            ) from exc
        if resp.status_code not in (200, 201):
            raise TwilioError(
                f"Twilio respondió {resp.status_code}: "
                f"{payload.get('message') or resp.text[:300]}"
            )
        return payload

    def enviar_sms(self, destino_e164: str, cuerpo: str) -> str:
        """POST /Accounts/{sid}/Messages.json; devuelve el SID del mensaje."""
        s = self._settings
        data: dict = {"To": destino_e164, "Body": cuerpo}
        if s.twilio_messaging_service_sid:
            data["MessagingServiceSid"] = s.twilio_messaging_service_sid
        else:
            data["From"] = s.twilio_from_number
        payload = self._post(
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{s.twilio_account_sid}/Messages.json",
            data,
        )
        return str(payload.get("sid", ""))

    # --- Verify API (cuenta paga; hoy sin servicio en consola) ---------

    def crear_verificacion(self, destino_e164: str, canal: str = "sms") -> str:
        """Twilio genera y envía el código; devuelve el estado ('pending')."""
        payload = self._post(
            f"https://verify.twilio.com/v2/Services/"
            f"{self._settings.twilio_verify_sid}/Verifications",
            {"To": destino_e164, "Channel": canal},
        )
        return str(payload.get("status", ""))

    def chequear_verificacion(self, destino_e164: str, codigo: str) -> bool:
        """True solo si Twilio aprueba el código ingresado."""
        payload = self._post(
            f"https://verify.twilio.com/v2/Services/"
            f"{self._settings.twilio_verify_sid}/VerificationCheck",
            {"To": destino_e164, "Code": codigo},
        )
        return payload.get("status") == "approved"
