"""Fixtures de integración: API con SQLite en memoria y parámetros temporales."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

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


def _configurar_entorno(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("DB_CREAR_TABLAS", "true")
    monkeypatch.setenv("PARAMETROS_PATH", str(tmp_path / "parametros.json"))
    monkeypatch.setenv("ENVIRONMENT", "demo")
    monkeypatch.setenv("SMMLV", "1300000")
    monkeypatch.setenv("JWT_SECRETO", "secreto-de-pruebas-32-bytes-minimo")
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
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_VERIFY_SID",
        "TWILIO_FROM_NUMBER",
        "TWILIO_MESSAGING_SERVICE_SID",
        "SMTP_HOST",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "SMTP_DESDE",
    ):
        monkeypatch.setenv(nombre, "")
    get_settings.cache_clear()
    get_store.cache_clear()
    db_session.configurar_engine("sqlite://")


def _app_client():
    from backend.main import app

    app.dependency_overrides[get_tasa_mercado_service] = _TasaMercadoStub
    return TestClient(app, raise_server_exceptions=False)


def _cerrar_app(app) -> None:
    app.dependency_overrides.pop(get_tasa_mercado_service, None)
    get_settings.cache_clear()
    get_store.cache_clear()


@pytest.fixture
def client(tmp_path, monkeypatch):
    _configurar_entorno(tmp_path, monkeypatch)
    app_client = _app_client()
    with app_client as c:
        _sembrar_identidad()
        c.headers["Authorization"] = f"Bearer {_token_rol('admin')}"
        yield c
    _cerrar_app(app_client.app)


@pytest.fixture
def client_sin_auth(tmp_path, monkeypatch):
    """Cliente sin sesión: prueba los 401 del perímetro."""
    _configurar_entorno(tmp_path, monkeypatch)
    app_client = _app_client()
    with app_client as c:
        _sembrar_identidad()
        yield c
    _cerrar_app(app_client.app)


@pytest.fixture
def client_asesor(tmp_path, monkeypatch):
    _configurar_entorno(tmp_path, monkeypatch)
    app_client = _app_client()
    with app_client as c:
        _sembrar_identidad()
        c.headers["Authorization"] = f"Bearer {_token_rol('asesor')}"
        yield c
    _cerrar_app(app_client.app)


@pytest.fixture
def client_aliado(tmp_path, monkeypatch):
    _configurar_entorno(tmp_path, monkeypatch)
    app_client = _app_client()
    with app_client as c:
        _sembrar_identidad()
        c.headers["Authorization"] = f"Bearer {_token_rol('aliado')}"
        yield c
    _cerrar_app(app_client.app)


@pytest.fixture
def client_concesionario(tmp_path, monkeypatch):
    _configurar_entorno(tmp_path, monkeypatch)
    app_client = _app_client()
    with app_client as c:
        _sembrar_identidad()
        c.headers["Authorization"] = f"Bearer {_token_rol('concesionario')}"
        yield c
    _cerrar_app(app_client.app)


_HASHES_USUARIOS = {
    "admin": "$2b$12$5XYg0Klh2zHX6SEkGB9aQ.nx.OFj6HgkNLdAXgErT98sYAPGgfxDO",
    "asesor": "$2b$12$kgMN4JFNA8mB9ak/aftAueZ2djG5QcixL5cchV5iolgYo9dkt8fQa",
    "aliado": "$2b$12$TJqL5OAtBDvZCDFacbiepuli3/EmXwD5XZ.B6duwinPLxBTLx2pQa",
    "concesionario": "$2b$12$kgMN4JFNA8mB9ak/aftAueZ2djG5QcixL5cchV5iolgYo9dkt8fQa",
}


def _id_usuario(rol: str) -> str:
    import uuid as _uuid

    return _uuid.uuid5(_uuid.NAMESPACE_DNS, f"{rol}@sumoto.com.co").hex


def _sembrar_identidad() -> None:
    """Siembra roles + los 3 usuarios de plataforma (idempotente)."""
    from backend.db_models.session import SessionLocal

    with SessionLocal() as db:
        db.execute(
            text(
                "INSERT OR IGNORE INTO rol (nombre, descripcion) VALUES "
                "('admin', 'Administrador'), ('asesor', 'Asesor'), "
                "('aliado', 'Aliado comercial'), ('cliente', 'Cliente'), "
                "('contabilidad', 'Contabilidad'), "
                "('concesionario', 'Administrador de sede')"
            )
        )
        # Entidades propias del fixture (nombres distintos a los de los
        # helpers de negocio para no chocar con sus UNIQUE).
        db.execute(
            text(
                "INSERT OR IGNORE INTO concesionario (nombre) VALUES "
                "('CONCESIONARIO AUTH PRUEBA')"
            )
        )
        db.execute(
            text(
                "INSERT OR IGNORE INTO aliado_financiero "
                "(nit, nombre, tipo, es_propio, activo) VALUES "
                "('999000999', 'ALIADO AUTH PRUEBA', 'otro', 1, 1)"
            )
        )
        for rol in ("admin", "asesor", "aliado", "concesionario"):
            db.execute(
                text(
                    "INSERT OR IGNORE INTO usuario (id_usuario, correo, "
                    "hash_contrasena, estado, nombre_completo) VALUES "
                    "(:u, :c, :h, 'activo', :n)"
                ),
                {
                    "u": _id_usuario(rol),
                    "c": f"{rol}@sumoto.com.co",
                    "h": _HASHES_USUARIOS[rol],
                    "n": f"{rol.capitalize()} Prueba",
                },
            )
            db.execute(
                text(
                    "INSERT OR IGNORE INTO usuario_rol (id_usuario, id_rol) "
                    "SELECT :u, id_rol FROM rol WHERE nombre=:r"
                ),
                {"u": _id_usuario(rol), "r": rol},
            )
        # Asesor sin sede asignada: su radicación debe fallar cerrado
        # (422), no quedar huérfana de concesionario.
        db.execute(
            text(
                "INSERT OR IGNORE INTO usuario (id_usuario, correo, "
                "hash_contrasena, estado, nombre_completo) VALUES "
                "(:u, 'asesor_sinsede@sumoto.com.co', :h, 'activo', "
                "'Asesor Sin Sede')"
            ),
            {"u": _id_usuario("asesor_sinsede"), "h": _HASHES_USUARIOS["asesor"]},
        )
        db.execute(
            text(
                "INSERT OR IGNORE INTO usuario_rol (id_usuario, id_rol) "
                "SELECT :u, id_rol FROM rol WHERE nombre='asesor'"
            ),
            {"u": _id_usuario("asesor_sinsede")},
        )
        db.execute(
            text(
                "INSERT OR IGNORE INTO asesor (id_usuario, nombre, "
                "num_cedula, telefono, id_concesionario) SELECT :u, "
                "'Asesor Prueba', '80000001', '3001112233', "
                "id_concesionario FROM concesionario "
                "WHERE nombre='CONCESIONARIO AUTH PRUEBA'"
            ),
            {"u": _id_usuario("asesor")},
        )
        db.execute(
            text(
                "INSERT OR IGNORE INTO aliado_usuario (id_usuario, "
                "id_aliado) SELECT :u, id_aliado FROM aliado_financiero "
                "WHERE nit='999000999'"
            ),
            {"u": _id_usuario("aliado")},
        )
        # Vínculo vigente (sin fechas = siempre activo): el aliado de
        # prueba ve las solicitudes de su concesionario.
        db.execute(
            text(
                "INSERT OR IGNORE INTO aliado_concesionario (id_aliado, "
                "id_concesionario, activo) SELECT a.id_aliado, "
                "c.id_concesionario, 1 FROM aliado_financiero a, "
                "concesionario c WHERE a.nit='999000999' AND "
                "c.nombre='CONCESIONARIO AUTH PRUEBA'"
            )
        )
        # El concesionario administra la sede de prueba: el vínculo vive
        # en `concesionario_usuario` (no en `asesor` — no es radicador).
        db.execute(
            text(
                "INSERT OR IGNORE INTO concesionario_usuario "
                "(id_usuario, id_concesionario) SELECT :u, "
                "id_concesionario FROM concesionario "
                "WHERE nombre='CONCESIONARIO AUTH PRUEBA'"
            ),
            {"u": _id_usuario("concesionario")},
        )
        db.commit()


def _token_rol(rol: str, correo: str | None = None) -> str:
    """JWT directo de JwtService: sin llamada HTTP ni costo bcrypt.
    `correo` permite emitir para usuarios auxiliares (p. ej. el asesor
    sin sede)."""
    import uuid as _uuid

    from backend.services.jwt_service import JwtService

    return JwtService(get_settings()).emitir(
        id_usuario=_uuid.uuid5(
            _uuid.NAMESPACE_DNS, correo or f"{rol}@sumoto.com.co"
        ),
        nombre=f"{rol.capitalize()} Prueba",
        roles=[rol],
    )


@pytest.fixture
def usuarios_prueba(client):
    """Los usuarios ya sembrados por `client`, con sus ids por rol."""
    return {
        "admin": {"id_usuario": _id_usuario("admin")},
        "asesor": {"id_usuario": _id_usuario("asesor")},
        "aliado": {"id_usuario": _id_usuario("aliado")},
    }


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
