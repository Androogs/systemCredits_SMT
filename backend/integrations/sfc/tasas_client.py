"""Cliente del dataset TIBC (Interés Bancario Corriente) de la SFC.

El dataset `pare-7x5i` del portal datos.gov.co publica, por modalidad
de crédito y resolución, la tasa corriente certificada en % efectivo
anual con su vigencia. Se actualiza cada mes; la tasa de usura es
1.5 veces la corriente (art. 305 Código Penal). Es una API Socrata
pública: no requiere llave y soporta SoQL.
"""

from typing import Any, Sequence

import httpx

from backend.config import Settings, get_settings
from backend.services.motor_exceptions import DataCreditoError

_SERVICIO = "sfc_tasas"
_DATASET = "pare-7x5i"


class TasasSfcClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def tasas_vigentes(self, modalidades: Sequence[str]) -> list[dict[str, Any]]:
        """Última fila certificada por cada modalidad pedida.

        El dataset trae una fila por resolución; ordenado por
        `vigencia_desde` descendente, la primera fila vista por
        modalidad es la vigente.
        """
        base = self.settings.sfc_tasas_base_url.rstrip("/")
        params = {
            "$where": "modalidad in ("
            + ",".join(f"'{m}'" for m in modalidades)
            + ")",
            "$order": "vigencia_desde DESC",
            "$limit": str(len(modalidades) * 4),
        }
        try:
            with httpx.Client(
                timeout=self.settings.sfc_tasas_timeout_segundos, verify=True
            ) as client:
                resp = client.get(f"{base}/resource/{_DATASET}.json", params=params)
        except httpx.RequestError as exc:
            raise DataCreditoError(
                _SERVICIO, None, f"Error de red: {exc}"
            ) from exc
        if resp.status_code != 200:
            raise DataCreditoError(
                _SERVICIO, resp.status_code, resp.text[:500]
            )
        try:
            filas = resp.json()
        except ValueError as exc:
            raise DataCreditoError(
                _SERVICIO, resp.status_code, f"JSON inválido: {exc}"
            ) from exc
        if not isinstance(filas, list):
            raise DataCreditoError(
                _SERVICIO, resp.status_code, "Respuesta sin lista de filas"
            )
        return filas
