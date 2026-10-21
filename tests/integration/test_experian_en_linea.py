"""Flujo en línea con Experian simulado a nivel HTTP (respx)."""

import json
from pathlib import Path

import httpx
import pytest
import respx

from backend.config import get_settings
from backend.integrations.datacredito import auth as auth_mod
from tests.integration.conftest import PAYLOAD

FIXTURES = Path(__file__).parent / "fixtures"
HDC_URL = "https://hdc.ficticio/cs/credit-history/v1/hdcplus"
INCOME_URL = "https://income.ficticio/cs/incomes/v1/income/indicator"
TOKEN_HDC = "https://token-hdc.ficticio/token"
TOKEN_INCOME = "https://token-income.ficticio/token"


@pytest.fixture
def credenciales(monkeypatch):
    valores = {
        "HDC_USERNAME": "u",
        "HDC_PASSWORD": "p",
        "HDC_TOKEN_USERNAME": "tu",
        "HDC_TOKEN_PASSWORD": "tp",
        "HDC_CLIENT_ID": "cid",
        "HDC_CLIENT_SECRET": "cs",
        "HDC_BASE_URL_DEMO": "https://hdc.ficticio",
        "HDC_TOKEN_URL_DEMO": TOKEN_HDC,
        "SERVER_IP_ADDRESS": "10.0.0.1",
        "INCOME_USERNAME": "2-900000000.usuario",
        "INCOME_PASSWORD": "p",
        "INCOME_CLIENT_ID": "icid",
        "INCOME_CLIENT_SECRET": "ics",
        "INCOME_BASE_URL_DEMO": "https://income.ficticio",
        "INCOME_TOKEN_URL_DEMO": TOKEN_INCOME,
        "INCOME_SUBSCRIBER_NAME": "SUSCRIPTOR FICTICIO",
    }
    for k, v in valores.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    auth_mod._auth_compartido = None
    yield
    auth_mod._auth_compartido = None


def _hdc_payload(**cambios):
    data = json.loads((FIXTURES / "hdc_response_example.json").read_text(encoding="utf-8"))
    root = data["ReportHDCplus"]
    root["location"]["nationalNatural"]["age"] = {"min": 30, "max": 40}
    for k, v in cambios.items():
        root[k] = v
    return data


def _income_payload():
    data = json.loads((FIXTURES / "income_response_example.json").read_text(encoding="utf-8"))
    data["numero_identificacion_persona_natural"] = "1000000001"
    return data


def _mock_tokens():
    respx.post(TOKEN_HDC).mock(return_value=httpx.Response(200, json={"access_token": "t1", "expires_in": 1800}))
    respx.post(TOKEN_INCOME).mock(return_value=httpx.Response(200, json={"access_token": "t2", "expires_in": 1800}))


@respx.mock
def test_consulta_en_linea_completa(client, credenciales):
    _mock_tokens()
    hdc = respx.post(HDC_URL).mock(return_value=httpx.Response(200, json=_hdc_payload()))
    income = respx.get(INCOME_URL).mock(return_value=httpx.Response(200, json=_income_payload()))
    r = client.post("/api/motor/evaluar", json={**PAYLOAD, "consultar_experian": True})
    assert r.status_code == 200, r.text
    assert hdc.called and income.called
    assert income.calls.last.request.url.params["NitSuscriptor"] == "900000000"
    data = r.json()
    assert data["score_consultado"] == "700"
    assert data["valor_ingreso"] == "1000000.00"
    assert client.get("/api/auditoria").json()[0]["origen_datos"] == "experian"


@respx.mock
def test_rechazo_en_hdc_no_consume_valor_ingreso(client, credenciales):
    _mock_tokens()
    cuenta_embargada = [{"account": {"accountNumber": "1"}, "status": {"businessAccountStatus": "06"}}]
    respx.post(HDC_URL).mock(return_value=httpx.Response(200, json=_hdc_payload(savings=cuenta_embargada)))
    income = respx.get(INCOME_URL).mock(return_value=httpx.Response(200, json=_income_payload()))
    data = client.post("/api/motor/evaluar", json={**PAYLOAD, "consultar_experian": True}).json()
    assert not income.called
    assert data["causales"][0]["codigo"] == "R2"
    assert any("Valor Ingreso no consultado" in a for a in data["advertencias"])


@respx.mock
def test_hdc_sin_reporte_evaluable(client, credenciales):
    _mock_tokens()
    payload = _hdc_payload()
    payload["ReportHDCplus"]["productResult"]["responseCode"] = "10"
    respx.post(HDC_URL).mock(return_value=httpx.Response(200, json=payload))
    r = client.post("/api/motor/evaluar", json={**PAYLOAD, "consultar_experian": True})
    assert r.status_code == 422
    assert r.json()["error"] == "reporte_buro_no_evaluable"


@respx.mock
def test_hdc_fallecido_se_evalua_como_rechazo_sin_consultar_ingreso(client, credenciales):
    _mock_tokens()
    payload = _hdc_payload()
    payload["ReportHDCplus"]["productResult"]["responseCode"] = "14"
    payload["ReportHDCplus"]["models"][0]["scoreValue"] = "3"
    respx.post(HDC_URL).mock(return_value=httpx.Response(200, json=payload))
    income = respx.get(INCOME_URL).mock(return_value=httpx.Response(200, json=_income_payload()))

    r = client.post("/api/motor/evaluar", json={**PAYLOAD, "consultar_experian": True})

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["decision"] == "Rechazado"
    assert data["causales"][0]["codigo"] == "R1"
    assert not income.called
    assert any("fallecido" in advertencia for advertencia in data["advertencias"])


@respx.mock
def test_hdc_de_otra_persona_detiene(client, credenciales):
    _mock_tokens()
    respx.post(HDC_URL).mock(return_value=httpx.Response(200, json=_hdc_payload()))
    r = client.post("/api/motor/evaluar", json={**PAYLOAD, "numero_id": "999", "consultar_experian": True})
    assert r.status_code == 422 and "no coincide" in r.json()["detail"]


@respx.mock
def test_error_http_y_token(client, credenciales):
    respx.post(TOKEN_HDC).mock(return_value=httpx.Response(401, text="credenciales inválidas"))
    r = client.post("/api/motor/evaluar", json={**PAYLOAD, "consultar_experian": True})
    assert r.status_code == 502 and r.json()["error"] == "error_datacredito"


@respx.mock
def test_segunda_evaluacion_reusa_consulta_vigente(client, credenciales):
    """La consulta de centrales se paga una vez por persona: dentro del
    período de vigencia la re-evaluación corre el motor con el reporte
    almacenado — no vuelve a Experian."""
    _mock_tokens()
    hdc = respx.post(HDC_URL).mock(return_value=httpx.Response(200, json=_hdc_payload()))
    income = respx.get(INCOME_URL).mock(return_value=httpx.Response(200, json=_income_payload()))
    assert client.post(
        "/api/motor/evaluar", json={**PAYLOAD, "consultar_experian": True}
    ).status_code == 200
    r = client.post("/api/motor/evaluar", json={**PAYLOAD, "consultar_experian": True})
    assert r.status_code == 200, r.text
    assert hdc.call_count == 1
    assert income.call_count == 1
    auditorias = client.get("/api/auditoria").json()
    assert auditorias[1]["origen_datos"] == "experian"
    assert auditorias[0]["origen_datos"].startswith("cache:experian")


@respx.mock
def test_cache_deshabilitado_consulta_de_nuevo(client, credenciales, monkeypatch):
    """BURO_CACHE_HABILITADO=false: cada evaluación consulta en línea."""
    monkeypatch.setenv("BURO_CACHE_HABILITADO", "false")
    get_settings.cache_clear()
    _mock_tokens()
    hdc = respx.post(HDC_URL).mock(return_value=httpx.Response(200, json=_hdc_payload()))
    respx.get(INCOME_URL).mock(return_value=httpx.Response(200, json=_income_payload()))
    for _ in range(2):
        client.post("/api/motor/evaluar", json={**PAYLOAD, "consultar_experian": True})
    assert hdc.call_count == 2


def test_repositorio_consulta_buro_vigencia(client):
    """La vigencia la controla BURO_CACHE_DIAS: 0 días = siempre vencida;
    la llave es la persona (tipo_id + numero_id), no la solicitud."""
    from backend.db_models import session as db_session
    from backend.db_models.auditoria_models import ConsultaBuro  # noqa: F401
    from backend.integrations.datacredito.mock_buro import crear_escenario
    from backend.models.enums import TipoIdentificacion
    from backend.repositories.consulta_buro_repository import ConsultaBuroRepository

    hdc, vi = crear_escenario(
        "aprobado", TipoIdentificacion.CC, "1000000001", "Ficticio", 1_300_000
    )
    db = db_session.SessionLocal()
    try:
        repo = ConsultaBuroRepository(db)
        repo.registrar("1", "1000000001", None, hdc, vi)
        db.commit()
        assert repo.ultima_vigente("1", "1000000001", dias=30) is not None
        assert repo.ultima_vigente("1", "1000000001", dias=0) is None
        assert repo.ultima_vigente("1", "999999", dias=30) is None
        reusada = repo.ultima_vigente("1", "1000000001", dias=30)
        hdc_re, vi_re = reusada.a_reportes()
        assert hdc_re.scores and vi_re.aportantes
    finally:
        db.close()


def test_produccion_no_permite_mock(client, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "produccion")
    get_settings.cache_clear()
    r = client.post("/api/motor/evaluar", json={**PAYLOAD, "escenario_mock": "aprobado"})
    assert r.status_code == 422


def test_token_se_reutiliza_en_cache():
    auth = auth_mod.OktaAuth()
    with respx.mock:
        ruta = respx.post(TOKEN_HDC).mock(
            return_value=httpx.Response(200, json={"access_token": "x", "expires_in": 1800})
        )
        auth.get_hdc_spla_token("u", "p", "c", "s", TOKEN_HDC)
        auth.get_hdc_spla_token("u", "p", "c", "s", TOKEN_HDC)
        assert ruta.call_count == 1
