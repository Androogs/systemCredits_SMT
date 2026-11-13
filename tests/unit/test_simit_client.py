"""Cliente PlacApi (SIMIT por cédula): contrato de la respuesta real
documentada en placapi.com/docs/estado-de-cuenta-de-transito.
"""

from decimal import Decimal

import httpx
import pytest

from backend.config import Settings
from backend.integrations.simit import client as simit_client
from backend.integrations.simit.client import PlacApiClient, crear_cliente_simit
from backend.models.enums import TipoIdentificacion
from backend.services.motor_exceptions import DataCreditoError

REAL_CLIENT = httpx.Client

# Respuesta de ejemplo de la documentación oficial (2 créditos).
RESPUESTA_DOC = {
    "source": "multas",
    "status": "danger",
    "data": {
        "documentNumber": "1020304050",
        "totalDeuda": 1860416,
        "pazSalvo": False,
        "totalComparendos": 1,
        "deudaComparendos": 522700,
        "comparendos": [{"comparendoId": "1", "valor": 522700}],
        "totalResoluciones": 1,
        "deudaResoluciones": 837716,
        "resoluciones": [{"comparendoId": "2", "valor": 837716}],
        "totalAcuerdos": 1,
        "pendienteAcuerdos": 500000,
        "acuerdos": [{"resolucion": "324", "pendiente": 500000}],
    },
    "mode": "live",
    "cost": 2,
}


def _settings(**kwargs) -> Settings:
    return Settings(simit_api_key="pk_live_test", experian_reintentos=0, **kwargs)


def _stub(monkeypatch, payload, status: int = 200):
    """HTTP simulado: responde `payload` y captura request (URL/body/headers)."""
    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["url"] = str(request.url)
        capturado["api_key"] = request.headers.get("x-api-key")
        capturado["body"] = request.read()
        return httpx.Response(status, json=payload)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        simit_client.httpx,
        "Client",
        lambda **kw: REAL_CLIENT(transport=transport, **kw),
    )
    return capturado


def test_consulta_envia_documento_y_api_key(monkeypatch):
    capturado = _stub(monkeypatch, RESPUESTA_DOC)
    PlacApiClient(_settings()).estado_cuenta_transito(
        TipoIdentificacion.CC, "1020304050"
    )
    assert capturado["url"].endswith("/api/estado-cuenta-transito")
    assert capturado["api_key"] == "pk_live_test"
    assert b'"docType": "CC"' in capturado["body"].replace(b" ", b"") or b'"docType":"CC"' in capturado["body"]
    assert b'"docNumber":"1020304050"' in capturado["body"].replace(b" ", b"")


def test_respuesta_real_agrega_los_tres_bloques(monkeypatch):
    """`acuerdos` es el nombre real del bloque (no `acuerdosPago`): con
    el campo equivocado los acuerdos de pago no se contaban."""
    _stub(monkeypatch, RESPUESTA_DOC)
    r = PlacApiClient(_settings()).estado_cuenta_transito(
        TipoIdentificacion.CC, "1020304050"
    )
    assert not r.paz_y_salvo
    assert r.total_deuda == Decimal("1860416")
    assert r.total_items == 3  # 1 comparendo + 1 resolución + 1 acuerdo
    assert r.origen == "placapi"


def test_respuesta_sin_envoltura_data(monkeypatch):
    _stub(monkeypatch, {"pazSalvo": True, "totalDeuda": 0})
    r = PlacApiClient(_settings()).estado_cuenta_transito(
        TipoIdentificacion.CC, "1020304050"
    )
    assert r.paz_y_salvo and r.total_items == 0


def test_paz_salvo_sin_items(monkeypatch):
    _stub(monkeypatch, {"data": {"pazSalvo": True, "totalDeuda": 0}})
    r = PlacApiClient(_settings()).estado_cuenta_transito(
        TipoIdentificacion.CC, "1020304050"
    )
    assert r.paz_y_salvo and r.total_deuda == 0


def test_doc_type_no_soportado_falla_sin_llamar(monkeypatch):
    """PlacApi solo acepta CC·CE·NIT·PA·TI·CD·PPT·RC; mandar PJE/DNI/PEP
    desperdicia la llamada (y el crédito de validación)."""
    capturado = _stub(monkeypatch, RESPUESTA_DOC)
    with pytest.raises(DataCreditoError, match="docType|documento"):
        PlacApiClient(_settings()).estado_cuenta_transito(
            TipoIdentificacion.PJE, "1020304050"
        )
    assert "url" not in capturado


def test_error_http_es_error_de_servicio(monkeypatch):
    _stub(monkeypatch, {"error": "invalid api key"}, status=401)
    with pytest.raises(DataCreditoError):
        PlacApiClient(_settings()).estado_cuenta_transito(
            TipoIdentificacion.CC, "1020304050"
        )


def test_factory_devuelve_portal_por_defecto():
    from backend.integrations.simit.portal_client import PortalSimitClient

    assert isinstance(
        crear_cliente_simit(Settings(_env_file=None)), PortalSimitClient
    )


def test_factory_devuelve_placapi_cuando_se_configura():
    assert isinstance(
        crear_cliente_simit(
            Settings(_env_file=None, simit_proveedor="placapi")
        ),
        PlacApiClient,
    )


def test_factory_proveedor_desconocido_falla():
    with pytest.raises(DataCreditoError, match="no soportado"):
        crear_cliente_simit(Settings(simit_proveedor="otro"))
