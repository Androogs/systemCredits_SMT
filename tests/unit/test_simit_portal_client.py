"""Cliente portal SIMIT (fcm.org.co): contrato de la API interna
descubierta del frontend Quipux (PoW captcha + /estadocuenta/consulta).
"""

import json
from decimal import Decimal

import httpx
import pytest

from backend.config import Settings
from backend.integrations.simit import portal_client
from backend.integrations.simit.client import crear_cliente_simit
from backend.integrations.simit.portal_client import PortalSimitClient
from backend.models.enums import TipoIdentificacion
from backend.services.motor_exceptions import DataCreditoError

REAL_CLIENT = httpx.Client

_CAPTCHA_URL = "https://qxcaptcha.fcm.org.co/api.php"
_CONSULTA_URL = (
    "https://consultasimit.fcm.org.co"
    "/simit/microservices/estado-cuenta-simit/estadocuenta/consulta"
)

# Basada en la respuesta real del portal: pazSalvo llega true AUNQUE
# hay multas pendientes — el flag no es confiable.
RESPUESTA_CON_DEUDA = {
    "multas": [
        {"infractor": {"tipoDocumento": "Cédula", "numeroDocumento": "1006461914"},
         "placa": "DVT08H", "valor": 633111, "valorPagar": 675311,
         "estadoComparendo": "Pendiente",
         "infracciones": [{"codigoInfraccion": "C35"}]},
        {"infractor": {"tipoDocumento": "Cédula", "numeroDocumento": "1006461914"},
         "placa": "DVT08H", "valor": 1266222, "valorPagar": 1308422,
         "estadoComparendo": "Pendiente",
         "infracciones": [{"codigoInfraccion": "D02"}]},
    ],
    "resoluciones": [],
    "comparendos": [],
    "acuerdosPago": [],
    "personasMismoDocumento": [],
    "pazSalvo": True,
    "totalGeneral": 1983733,
    "totalMultas": 1983733,
    "totalAp": 0,
    "cancelada": False,
    "suspendida": False,
}

RESPUESTA_SIN_DEUDA = {
    "multas": [], "resoluciones": [], "comparendos": [],
    "acuerdosPago": [], "personasMismoDocumento": [],
    "pazSalvo": True, "totalGeneral": 0, "totalMultas": 0,
    "totalAp": 0, "cancelada": False, "suspendida": False,
}


def _settings(**kwargs) -> Settings:
    return Settings(experian_reintentos=0, **kwargs)


def _stub(monkeypatch, consulta_payload, consulta_status: int = 200):
    """HTTP simulado: resuelve api.php (captcha) y /consulta."""
    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(_CAPTCHA_URL):
            return httpx.Response(
                200,
                json={"error": False,
                      "data": {"question": "a" * 32,
                               "recommended_difficulty": 2}},
            )
        capturado["url"] = url
        capturado["body"] = request.read()
        return httpx.Response(consulta_status, json=consulta_payload)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        portal_client.httpx,
        "Client",
        lambda **kw: REAL_CLIENT(transport=transport, **kw),
    )
    # El PoW real tarda ~1-3 s de CPU; el algoritmo se cubre aparte.
    monkeypatch.setattr(portal_client, "_resolver_pow", lambda q, t: 104729)
    return capturado


def test_consulta_envia_filtro_y_captcha(monkeypatch):
    capturado = _stub(monkeypatch, RESPUESTA_SIN_DEUDA)
    PortalSimitClient(_settings()).estado_cuenta_transito(
        TipoIdentificacion.CC, "1020304050"
    )
    assert capturado["url"] == _CONSULTA_URL
    body = json.loads(capturado["body"])
    assert body["filtro"] == "1020304050"
    verif = json.loads(body["reCaptchaDTO"]["response"])
    assert verif[0]["question"] == "a" * 32
    assert verif[0]["nonce"] == 104729
    assert body["reCaptchaDTO"]["consumidor"] == "1"


def test_deuda_real_aunque_pazsalvo_diga_true(monkeypatch):
    """Regresión: el portal responde pazSalvo=true con multas
    pendientes — el resultado debe derivarse del total y el conteo."""
    _stub(monkeypatch, RESPUESTA_CON_DEUDA)
    r = PortalSimitClient(_settings()).estado_cuenta_transito(
        TipoIdentificacion.CC, "1006461914"
    )
    assert not r.paz_y_salvo
    assert r.total_deuda == Decimal("1983733")
    assert r.total_items == 2
    assert r.origen == "portal"


def test_sin_deuda_es_paz_y_salvo(monkeypatch):
    _stub(monkeypatch, RESPUESTA_SIN_DEUDA)
    r = PortalSimitClient(_settings()).estado_cuenta_transito(
        TipoIdentificacion.CC, "1020304050"
    )
    assert r.paz_y_salvo and r.total_deuda == 0 and r.total_items == 0


def test_respuesta_sin_totalgeneral_falla(monkeypatch):
    _stub(monkeypatch, {"error": "bad request"})
    with pytest.raises(DataCreditoError, match="inesperado"):
        PortalSimitClient(_settings()).estado_cuenta_transito(
            TipoIdentificacion.CC, "1020304050"
        )


def test_error_http_es_error_de_servicio(monkeypatch):
    _stub(monkeypatch, {"error": "boom"}, consulta_status=500)
    with pytest.raises(DataCreditoError):
        PortalSimitClient(_settings()).estado_cuenta_transito(
            TipoIdentificacion.CC, "1020304050"
        )


def test_factory_devuelve_portal_cuando_se_configura():
    cliente = crear_cliente_simit(Settings(simit_proveedor="portal"))
    assert isinstance(cliente, PortalSimitClient)


def test_pow_encuentra_nonce_primo():
    """El algoritmo real: sha256 del JSON compacto empieza en 0000 y
    el nonce es primo (réplica de captcha-worker.js)."""
    import hashlib
    import json as _json

    nonce = portal_client._resolver_pow("a" * 32, 1700000000)
    payload = _json.dumps(
        {"question": "a" * 32, "time": 1700000000, "nonce": nonce},
        separators=(",", ":"),
    )
    assert hashlib.sha256(payload.encode()).hexdigest().startswith("0000")
    assert portal_client._es_primo(nonce)
