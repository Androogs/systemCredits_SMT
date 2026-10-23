"""Pruebas del pre-filtro SIMIT. Ejecutar: pytest backend/tests/test_simit.py -q"""
import importlib

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'prueba.db'}")
    monkeypatch.delenv("SIMIT_API_KEY", raising=False)
    monkeypatch.delenv("SIMIT_MOCK_ESCENARIO", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    from backend.integrations.simit import simit_guard
    simit_guard.reiniciar_conexion()
    from backend.routes import simit_routes
    importlib.reload(simit_routes)
    aplicacion = FastAPI()
    aplicacion.include_router(simit_routes.router)
    return aplicacion


def consultar(cliente, cedula):
    return cliente.post("/api/simit/consultar", json={
        "tipo_documento": "CC", "numero_documento": cedula,
        "fecha_autorizacion": "2026-10-21T10:30:00",
    })


def test_cedula_con_multas_bloquea(app):
    from backend.integrations.simit.simit_guard import exigir_simit_paz_y_salvo
    r = consultar(TestClient(app), "1112230495")
    assert r.status_code == 200
    assert r.json() == {"paz_y_salvo": False, "total_deuda": "850000", "total_items": 2,
                        "origen": "mock:simit_multas"}
    with pytest.raises(HTTPException) as e:
        exigir_simit_paz_y_salvo("1112230495")
    assert e.value.status_code == 403


def test_cedula_sin_multas_continua(app):
    from backend.integrations.simit.simit_guard import exigir_simit_paz_y_salvo
    r = consultar(TestClient(app), "1006308061")
    assert r.status_code == 200 and r.json()["paz_y_salvo"] is True
    consulta = exigir_simit_paz_y_salvo("1006308061")
    assert consulta.fecha_autorizacion_datos is not None  # habeas data registrado


def test_cualquier_cedula_valida_se_puede_consultar(app):
    for cedula in ["1032448900", "79845123", "1.234.567", "52 345 678"]:
        assert consultar(TestClient(app), cedula).status_code == 200


def test_cedula_invalida(app):
    for cedula in ["12AB", "123", "12345678901"]:
        assert consultar(TestClient(app), cedula).status_code == 422


def test_sin_consulta_previa_bloquea_ocr(app):
    from backend.integrations.simit.simit_guard import exigir_simit_paz_y_salvo
    with pytest.raises(HTTPException) as e:
        exigir_simit_paz_y_salvo("1098765432")
    assert e.value.status_code == 428


def test_produccion_sin_clave_no_usa_mock(app, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    r = consultar(TestClient(app), "1006308061")
    assert r.status_code == 503
    assert r.json()["detail"]["codigo"] == "SIMIT_NO_DISPONIBLE"


def test_escenario_forzado(app, monkeypatch):
    monkeypatch.setenv("SIMIT_MOCK_ESCENARIO", "simit_multas")
    r = consultar(TestClient(app), "1006308061")
    assert r.json()["paz_y_salvo"] is False


def test_pago_posterior_desbloquea(app):
    """Si una consulta nueva sale limpia, prevalece sobre la anterior."""
    from backend.integrations.simit import simit_guard
    simit_guard.registrar_consulta("1077777777", {"paz_y_salvo": False, "total_deuda": "100", "total_items": 1, "origen": "x"})
    simit_guard.registrar_consulta("1077777777", {"paz_y_salvo": True, "total_deuda": "0", "total_items": 0, "origen": "x"})
    assert simit_guard.exigir_simit_paz_y_salvo("1077777777").paz_y_salvo is True
