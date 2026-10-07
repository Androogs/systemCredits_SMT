"""Cliente REST de Valor Ingreso."""

from typing import Any

import httpx

from backend.config import Settings, get_settings
from backend.integrations.datacredito.auth import OktaAuth, get_auth
from backend.integrations.datacredito.parsers.income_parser import IncomeParser
from backend.models.buro_models import RespuestaValorIngreso
from backend.models.enums import TipoIdentificacion
from backend.services.motor_exceptions import DataCreditoError
from backend.utils.loggers import get_logger

logger = get_logger("motor_decision.datacredito.income")


def _nit_suscriptor(username: str) -> str:
    """El usuario de Valor Ingreso tiene la forma '2-<NIT>.<usuario>'."""
    return username.split(".")[0].replace("2-", "")


class IncomeRestClient:
    def __init__(self, settings: Settings | None = None, auth: OktaAuth | None = None):
        self.settings = settings or get_settings()
        self.auth = auth or get_auth()
        self.parser = IncomeParser()

    def consultar(
        self,
        tipo_id_buscar: TipoIdentificacion,
        numero_id_buscar: str,
        ingreso_validar: int = 0,
        producto_id: str = "12",
    ) -> RespuestaValorIngreso:
        token = self.auth.get_token(
            scope=self.settings.income_scope,
            username=self.settings.income_username,
            password=self.settings.income_password,
            client_id=self.settings.income_client_id,
            client_secret=self.settings.income_client_secret,
            token_url=self.settings.income_token_url,
        )
        headers = {
            "access_token": token.access_token,
            "client_id": self.settings.income_client_id,
            "client_secret": self.settings.income_client_secret,
        }
        nit = _nit_suscriptor(self.settings.income_username)
        params = {
            "TipoIdentificacionUsuario": "2",
            "IdentificacionUsuario": nit,
            "TipoIDSuscriptor": "2",
            "NitSuscriptor": nit,
            "NombreSuscriptor": self.settings.income_subscriber_name,
            "TipoIdBuscar": tipo_id_buscar.value,
            "IdentificacionBuscar": numero_id_buscar,
            "IngresoValidar": str(ingreso_validar),
            "ProductoId": producto_id,
            "CanalConsulta": "2",
            "ProductoConsulta": "1",
        }
        url = f"{self.settings.income_base_url}/cs/incomes/v1/income/indicator"
        try:
            with httpx.Client(timeout=self.settings.timeout_experian_segundos, verify=True) as client:
                response = client.get(url, headers=headers, params=params)
        except httpx.RequestError as exc:
            raise DataCreditoError("income_rest", None, f"Error de red: {exc}") from exc
        if response.status_code != 200:
            raise DataCreditoError("income_rest", response.status_code, response.text[:500])
        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            raise DataCreditoError("income_rest", response.status_code, f"JSON inválido: {exc}") from exc
        logger.info("Valor Ingreso respondió | status=%s", response.status_code)
        return self.parser.parse(payload)
