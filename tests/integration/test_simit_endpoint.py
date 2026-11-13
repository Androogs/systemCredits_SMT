"""POST /api/solicitudes/simit: la 'puerta SIMIT' del paso 3.

El endpoint consulta el estado de cuenta por documento (el popup
manual al portal queda de respaldo cuando el proveedor no responde).
Requiere la autorización Habeas Data del paso 1.
"""

from decimal import Decimal

import backend.services.evaluacion_service as es
from backend.config import get_settings
from backend.integrations.simit.client import ResultadoSimit
from backend.services.motor_exceptions import DataCreditoError

PAYLOAD = {
    "tipo_documento": "1",
    "num_cedula": "1006461914",
    "autorizo_habeas": True,
}


class _ProveedorStub:
    def __init__(self, resultado=None, exc=None):
        self._res = resultado
        self._exc = exc
        self.llamadas = []

    def estado_cuenta_transito(self, tipo_id, numero_id):
        self.llamadas.append((tipo_id, numero_id))
        if self._exc:
            raise self._exc
        return self._res


def _stub(monkeypatch, resultado=None, exc=None):
    proveedor = _ProveedorStub(resultado, exc)
    monkeypatch.setattr(es, "crear_cliente_simit", lambda s: proveedor)
    return proveedor


def test_simit_devuelve_deuda_real(client, monkeypatch):
    proveedor = _stub(
        monkeypatch, ResultadoSimit(False, Decimal("1983733"), 2, "portal")
    )

    r = client.post("/api/solicitudes/simit", json=PAYLOAD)

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["habilitado"] is True
    assert data["tiene_multas"] is True
    assert data["total_items"] == 2
    assert proveedor.llamadas


def test_simit_paz_y_salvo(client, monkeypatch):
    _stub(monkeypatch, ResultadoSimit(True, Decimal(0), 0, "portal"))

    r = client.post("/api/solicitudes/simit", json=PAYLOAD)

    assert r.status_code == 200, r.text
    assert r.json()["tiene_multas"] is False


def test_simit_sin_autorizacion_habeas_rechaza(client):
    r = client.post(
        "/api/solicitudes/simit",
        json={**PAYLOAD, "autorizo_habeas": False},
    )
    assert r.status_code == 422


def test_simit_proveedor_caido_deja_tiene_multas_vacio(client, monkeypatch):
    """El frontend interpreta tiene_multas=None como 'verificación
    manual' y vuelve al popup del portal."""
    _stub(monkeypatch, exc=DataCreditoError("simit", 502, "portal caído"))

    r = client.post("/api/solicitudes/simit", json=PAYLOAD)

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["habilitado"] is True
    assert data.get("tiene_multas") is None


def test_simit_deshabilitado(client, monkeypatch):
    monkeypatch.setenv("SIMIT_HABILITADO", "false")
    get_settings.cache_clear()
    try:
        r = client.post("/api/solicitudes/simit", json=PAYLOAD)
        assert r.status_code == 200, r.text
        assert r.json()["habilitado"] is False
    finally:
        get_settings.cache_clear()


def test_simit_resultado_queda_cacheado(client, monkeypatch):
    """La segunda consulta del mismo documento sale del caché."""
    proveedor = _stub(monkeypatch, ResultadoSimit(True, Decimal(0), 0, "portal"))

    client.post("/api/solicitudes/simit", json=PAYLOAD)
    r = client.post("/api/solicitudes/simit", json=PAYLOAD)

    assert r.status_code == 200
    assert len(proveedor.llamadas) == 1
