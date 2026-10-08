"""Fixtures de integración: API con SQLite en memoria y parámetros temporales."""

import pytest
from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.db_models import session as db_session
from backend.routes.dependencies import get_store


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("DB_CREAR_TABLAS", "true")
    monkeypatch.setenv("PARAMETROS_PATH", str(tmp_path / "parametros.json"))
    monkeypatch.setenv("ENVIRONMENT", "demo")
    monkeypatch.setenv("SMMLV", "1300000")
    for nombre in (
        "HDC_USERNAME",
        "HDC_PASSWORD",
        "HDC_TOKEN_USERNAME",
        "HDC_TOKEN_PASSWORD",
        "HDC_CLIENT_ID",
        "HDC_CLIENT_SECRET",
        "HDC_BASE_URL_DEMO",
        "HDC_TOKEN_URL_DEMO",
        "SERVER_IP_ADDRESS",
        "INCOME_USERNAME",
        "INCOME_PASSWORD",
        "INCOME_CLIENT_ID",
        "INCOME_CLIENT_SECRET",
        "INCOME_BASE_URL_DEMO",
        "INCOME_TOKEN_URL_DEMO",
        "INCOME_SUBSCRIBER_NAME",
    ):
        monkeypatch.setenv(nombre, "")
    get_settings.cache_clear()
    get_store.cache_clear()
    db_session.configurar_engine("sqlite://")

    from backend.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    get_settings.cache_clear()
    get_store.cache_clear()


PAYLOAD = {
    "tipo_id": "1",
    "numero_id": "1000000001",
    "primer_apellido": "Ficticio",
    "ocupacion": "Empleado",
    "tipo_contrato": "Indefinido",
    "fecha_nacimiento": "1990-05-15",
    "ingresos_mensuales": 5000000,
    "saldo_financiar": 10000000,
    "plazo": 36,
    "tasa": 2,
}
