"""Fixtures de integración: API con SQLite en memoria y parámetros temporales."""

import pytest
from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.db_models import session as db_session
from backend.routes.dependencies import get_store, get_tasa_mercado_service
from backend.services.tasa_mercado_service import ModalidadTasa, TasasMercado


# Referencia SFC fija para pruebas: la guarda de usura de POST /evaluar
# valida contra estos valores sin depender de datos.gov.co.
_TASAS_STUB = TasasMercado(
    umbral_bajo_monto=6 * 1_300_000,
    fuente="stub de pruebas",
    bajo_monto=ModalidadTasa(
        "CONSUMO BAJO MONTO", 44.44, 3.11, 66.66, 4.3488, "", "", "TEST"
    ),
    ordinario=ModalidadTasa(
        "CONSUMO Y ORDINARIO", 19.06, 1.4645, 28.59, 2.1176, "", "", "TEST"
    ),
)


class _TasaMercadoStub:
    def tasas(self) -> TasasMercado:
        return _TASAS_STUB


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
        # Canales de notificación: vacíos → modo simulado (log), sin
        # depender de las credenciales del .env local.
        "WATI_BASE_URL",
        "WATI_TENANT_ID",
        "WATI_API_TOKEN",
        "WATI_CHANNEL_NUMBER",
        "SMTP_HOST",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "SMTP_DESDE",
    ):
        monkeypatch.setenv(nombre, "")
    get_settings.cache_clear()
    get_store.cache_clear()
    db_session.configurar_engine("sqlite://")

    from backend.main import app

    app.dependency_overrides[get_tasa_mercado_service] = _TasaMercadoStub
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.pop(get_tasa_mercado_service, None)
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
