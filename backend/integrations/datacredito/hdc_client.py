"""Cliente REST de Historia de Crédito+ (HDC+)."""

from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx

from backend.config import Settings, get_settings
from backend.integrations.datacredito.auth import OktaAuth, get_auth
from backend.integrations.datacredito.parsers.hdc_parser import HDCParser
from backend.integrations.datacredito.resiliencia import llamar_con_resiliencia
from backend.models.buro_models import RespuestaHDC
from backend.models.enums import TipoIdentificacion
from backend.services.motor_exceptions import DataCreditoError
from backend.utils.loggers import get_logger

logger = get_logger("motor_decision.datacredito.hdc")


class HDCRestClient:
    def __init__(self, settings: Settings | None = None, auth: OktaAuth | None = None):
        self.settings = settings or get_settings()
        self.auth = auth or get_auth()
        self.parser = HDCParser()

    def consultar(
        self,
        tipo_id: TipoIdentificacion,
        numero_id: str,
        primer_apellido: str,
    ) -> RespuestaHDC:
        token = self.auth.get_hdc_spla_token(
            username=self.settings.hdc_token_username,
            password=self.settings.hdc_token_password,
            client_id=self.settings.hdc_client_id,
            client_secret=self.settings.hdc_client_secret,
            token_url=self.settings.hdc_token_url,
        )
        headers = {
            "Authorization": f"Bearer {token.access_token}",
            "client_id": self.settings.hdc_client_id,
            "client_secret": self.settings.hdc_client_secret,
            "Content-Type": "application/json",
            "serverIpAddress": self.settings.server_ip_address,
            "ProductId": self.settings.hdc_product_id,
            "InfoAccountType": "1",
        }
        body = {
            "user": self.settings.hdc_username,
            "password": self.settings.hdc_password,
            "identifyingTrx": {
                "requestUUID": str(uuid4()),
                "dateTime": datetime.now(ZoneInfo("America/Bogota")).isoformat(timespec="seconds"),
                "originatorChannelName": "CONEXRED-01",
                "originatorChannelType": "42",
            },
            "identifyingUser": {
                "person": {
                    "personId": {"personIdNumber": numero_id, "personIdType": int(tipo_id.value)},
                    "personLastName": primer_apellido.upper(),
                }
            },
            "parameters": [{"type": "0", "nameParameter": "codigos", "valueParameter": "TOM-001"}],
        }
        url = f"{self.settings.hdc_base_url}/cs/credit-history/v1/hdcplus"

        def llamada() -> httpx.Response:
            try:
                with httpx.Client(
                    timeout=self.settings.timeout_experian_segundos, verify=True
                ) as client:
                    resp = client.post(url, headers=headers, json=body)
            except httpx.RequestError as exc:
                raise DataCreditoError("hdc_rest", None, f"Error de red: {exc}") from exc
            if resp.status_code != 200:
                raise DataCreditoError("hdc_rest", resp.status_code, resp.text[:500])
            return resp

        response = llamar_con_resiliencia("hdc_rest", self.settings, llamada)
        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            raise DataCreditoError("hdc_rest", response.status_code, f"JSON inválido: {exc}") from exc
        logger.info("HDC+ respondió | status=%s", response.status_code)
        return self.parser.parse(payload)
