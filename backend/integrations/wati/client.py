"""Cliente WATI: envío de mensajes plantilla por WhatsApp (API v1).

El OTP viaja como plantilla de autenticación aprobada por Meta: WhatsApp
no admite mensajes libres fuera de la ventana de 24 h del cliente, así
que el código solo puede enviarse con `sendTemplateMessage`. Los
`parameters` son posicionales y deben coincidir con los placeholders
aprobados en el dashboard de WATI (hoy: {{1}} = código; si la plantilla
declara más placeholders, extender `_parametros_whatsapp` en
NotificacionService). Un 200 de WATI significa "aceptado", no entregado.
"""

import logging
import re

import httpx

from backend.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Indicativo de Colombia: el teléfono de contacto se captura como celular
# local de 10 dígitos y aquí se normaliza al formato internacional.
CODIGO_PAIS_CO = "57"


class WatiError(Exception):
    """Transporte fallido o envío rechazado por WATI."""


def normalizar_telefono_whatsapp(telefono: str | None) -> str | None:
    """Deja el teléfono en formato internacional sin '+' (573001234567).

    Acepta el celular local de 10 dígitos (se antepone 57) o un número ya
    internacional. Devuelve None cuando no hay dígitos suficientes.
    """
    if not telefono:
        return None
    digitos = re.sub(r"\D", "", telefono)
    if digitos.startswith("00"):
        digitos = digitos[2:]  # prefijo internacional 00
    if len(digitos) == 10:
        digitos = CODIGO_PAIS_CO + digitos
    if len(digitos) < 11:
        return None
    return digitos


class WatiClient:
    """POST /{tenant}/api/v1/sendTemplateMessage contra el servidor WATI."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def configurado(self) -> bool:
        s = self._settings
        return bool(s.wati_base_url and s.wati_tenant_id and s.wati_api_token)

    def enviar_plantilla(
        self,
        whatsapp_number: str,
        template_name: str,
        parametros: list[str],
        *,
        broadcast_name: str,
    ) -> None:
        """Encola la plantilla; WatiError si WATI no la acepta."""
        s = self._settings
        url = (
            f"{s.wati_base_url.rstrip('/')}/{s.wati_tenant_id}"
            "/api/v1/sendTemplateMessage"
        )
        body: dict = {
            "template_name": template_name,
            "broadcast_name": broadcast_name,
            "parameters": [
                {"name": str(i + 1), "value": valor}
                for i, valor in enumerate(parametros)
            ],
        }
        if s.wati_channel_number:
            body["channel_number"] = s.wati_channel_number
        try:
            with httpx.Client(timeout=s.wati_timeout_segundos) as client:
                resp = client.post(
                    url,
                    params={"whatsappNumber": whatsapp_number},
                    json=body,
                    headers={"Authorization": f"Bearer {s.wati_api_token}"},
                )
        except httpx.RequestError as exc:
            raise WatiError(f"Error de red hacia WATI: {exc}") from exc
        if resp.status_code != 200:
            raise WatiError(
                f"WATI respondió {resp.status_code}: {resp.text[:300]}"
            )
        try:
            payload = resp.json()
        except ValueError as exc:
            raise WatiError("La respuesta de WATI no es JSON") from exc
        if not payload.get("result"):
            raise WatiError(f"WATI rechazó el envío: {payload.get('info')}")
