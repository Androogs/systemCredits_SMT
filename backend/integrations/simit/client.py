"""Cliente REST de PlacaPi — estado de cuenta de tránsito (SIMIT).

POST /api/estado-cuenta-transito con la cédula de la persona devuelve
`pazSalvo`, `totalDeuda` y los tres bloques de deuda (comparendos,
resoluciones y acuerdos de pago). Es el pre-filtro de originación: el
SIMIT no expone API oficial y el scrapeo directo del portal no es base
para un proceso productivo.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

import httpx

from backend.config import Settings, get_settings
from backend.integrations.datacredito.resiliencia import llamar_con_resiliencia
from backend.models.enums import TipoIdentificacion
from backend.services.motor_exceptions import DataCreditoError
from backend.utils.loggers import get_logger

logger = get_logger("motor_decision.simit")

_SERVICIO = "simit_estado_cuenta"


@dataclass
class ResultadoSimit:
    """Estado de cuenta de tránsito de la persona, ya normalizado."""

    paz_y_salvo: bool
    total_deuda: Decimal
    total_items: int
    origen: str = "placapi"


def resultado_a_json(resultado: ResultadoSimit) -> dict[str, Any]:
    """Serializa el resultado para persistirlo en consulta_simit."""
    return {
        "paz_y_salvo": resultado.paz_y_salvo,
        "total_deuda": str(resultado.total_deuda),
        "total_items": resultado.total_items,
        "origen": resultado.origen,
    }


def resultado_desde_crudo(data: dict[str, Any]) -> ResultadoSimit:
    """Reconstruye el resultado desde el JSON guardado en consulta_simit."""
    return ResultadoSimit(
        paz_y_salvo=bool(data.get("paz_y_salvo")),
        total_deuda=_decimal(data.get("total_deuda")),
        total_items=_entero(data.get("total_items")),
        origen=str(data.get("origen") or ""),
    )


def _entero(valor: Any) -> int:
    try:
        return int(valor or 0)
    except (TypeError, ValueError):
        return 0


def _decimal(valor: Any) -> Decimal:
    try:
        return Decimal(str(valor or 0))
    except (InvalidOperation, ValueError):
        return Decimal(0)


def _items(bloque: Any) -> int:
    """Conteo de un bloque del estado de cuenta: puede venir como lista
    de ítems o como dict con `conteo`/`total`."""
    if isinstance(bloque, list):
        return len(bloque)
    if isinstance(bloque, dict):
        for clave in ("conteo", "total", "totalMultas"):
            if clave in bloque:
                return _entero(bloque[clave])
        return len(bloque.get("items") or bloque.get("multas") or [])
    return 0


# docTypes que acepta PlacApi (CC·CE·NIT·PA·TI·CD·PPT·RC), mapeados
# desde TipoIdentificacion.name. PAS se manda ya como su canónico PA.
_DOC_TYPES = {
    "CC": "CC",
    "CE": "CE",
    "NIT": "NIT",
    "TI": "TI",
    "PPT": "PPT",
    "PAS": "PA",
}


def _doc_type(tipo_id: TipoIdentificacion) -> str:
    doc = _DOC_TYPES.get(tipo_id.name)
    if doc is None:
        raise DataCreditoError(
            _SERVICIO,
            None,
            f"docType {tipo_id.name} no soportado por PlacApi "
            "(acepta CC·CE·NIT·PA·TI·CD·PPT·RC)",
        )
    return doc


class PlacApiClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def estado_cuenta_transito(
        self,
        tipo_id: TipoIdentificacion,
        numero_id: str,
    ) -> ResultadoSimit:
        """Deuda SIMIT de la persona por documento. Cubre comparendos,
        resoluciones en firme y acuerdos de pago — `pazSalvo` solo es
        true cuando el total es cero."""
        url = (
            f"{self.settings.simit_base_url.rstrip('/')}"
            "/api/estado-cuenta-transito"
        )
        headers = {
            "x-api-key": self.settings.simit_api_key,
            "Content-Type": "application/json",
        }
        body = {"docType": _doc_type(tipo_id), "docNumber": numero_id}

        def llamada() -> httpx.Response:
            try:
                with httpx.Client(
                    timeout=self.settings.simit_timeout_segundos, verify=True
                ) as client:
                    resp = client.post(url, headers=headers, json=body)
            except httpx.RequestError as exc:
                raise DataCreditoError(
                    _SERVICIO, None, f"Error de red: {exc}"
                ) from exc
            if resp.status_code != 200:
                raise DataCreditoError(
                    _SERVICIO, resp.status_code, resp.text[:500]
                )
            return resp

        response = llamar_con_resiliencia(_SERVICIO, self.settings, llamada)
        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            raise DataCreditoError(
                _SERVICIO, response.status_code, f"JSON inválido: {exc}"
            ) from exc

        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        deuda = _decimal(data.get("totalDeuda"))
        # La respuesta trae el conteo por bloque (totalComparendos,
        # totalResoluciones, totalAcuerdos) y el detalle como listas
        # (comparendos, resoluciones, acuerdos): se prefieren los
        # totales y las listas quedan de respaldo.
        items = sum(
            _entero(data.get(k))
            for k in ("totalComparendos", "totalResoluciones", "totalAcuerdos")
        ) or sum(
            _items(data.get(b))
            for b in ("comparendos", "resoluciones", "acuerdos")
        )
        paz_salvo = bool(data.get("pazSalvo", deuda == 0 and items == 0))
        logger.info(
            "SIMIT %s/%s | paz_salvo=%s deuda=%s items=%s",
            tipo_id.name,
            numero_id,
            paz_salvo,
            deuda,
            items,
        )
        return ResultadoSimit(
            paz_y_salvo=paz_salvo, total_deuda=deuda, total_items=items
        )


class ClienteSimit(Protocol):
    """Contrato del pre-filtro SIMIT: sí/no de deuda por documento."""

    def estado_cuenta_transito(
        self, tipo_id: TipoIdentificacion, numero_id: str
    ) -> ResultadoSimit: ...


def crear_cliente_simit(settings: Settings | None = None) -> ClienteSimit:
    """Proveedor configurado vía SIMIT_PROVEEDOR.

    `placapi` es el agregador pago; `portal` scrapea la API interna del
    portal ciudadano fcm.org.co/simit (PoW captcha, sin SLA — ver
    portal_client.py). Cuando el convenio de consulta masiva con la FCM
    (Resolución 35 de 2016 — se solicita por PQRSD o ventanilla virtual
    en fcm.org.co) entregue el servicio oficial, se agrega la rama
    `fcm` con su adaptador: el resto del flujo no cambia porque el
    contrato es ResultadoSimit.
    """
    settings = settings or get_settings()
    proveedor = (settings.simit_proveedor or "placapi").lower()
    if proveedor == "placapi":
        return PlacApiClient(settings)
    if proveedor == "portal":
        from backend.integrations.simit.portal_client import (
            PortalSimitClient,
        )

        return PortalSimitClient(settings)
    raise DataCreditoError(
        _SERVICIO,
        None,
        f"Proveedor SIMIT no soportado: {proveedor!r} "
        "(disponibles: 'placapi', 'portal')",
    )
