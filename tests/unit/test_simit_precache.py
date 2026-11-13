"""Precache SIMIT al aceptar el Habeas Data + caché por documento.

El consentimiento Habeas Data es el habilitante para tratar datos
personales: al registrarlo se dispara la consulta al portal SIMIT en
background; el resultado queda en consulta_simit y la evaluación lo
reusa vigente (SIMIT_CACHE_DIAS) en vez de pegarle al portal en
caliente.
"""

import threading
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.services.evaluacion_service as es
from backend.config import Settings
from backend.db_models.auditoria_models import ConsultaSimit
from backend.services.motor_exceptions import DataCreditoError, ValidacionError
from backend.integrations.simit.client import ResultadoSimit
from backend.models.enums import TipoIdentificacion
from backend.services.evaluacion_service import EvaluacionService
from backend.services.solicitud_service import SolicitudService


def _settings(**overrides) -> Settings:
    base = dict(
        environment="produccion",
        simit_habilitado=True,
        simit_proveedor="portal",
        simit_api_key="",
        simit_cache_dias=30,
        simit_requerido=False,
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)


class _ProveedorStub:
    def __init__(self, resultado=None, exc=None):
        self.llamadas = []
        self._res = resultado or ResultadoSimit(True, Decimal(0), 0, "portal")
        self._exc = exc

    def estado_cuenta_transito(self, tipo_id, numero_id):
        self.llamadas.append((tipo_id, numero_id))
        if self._exc:
            raise self._exc
        return self._res


def _sesion_sqlite():
    engine = create_engine("sqlite://")
    ConsultaSimit.__table__.create(engine)
    return sessionmaker(bind=engine)()


def _servicio(db, monkeypatch, proveedor, **settings_overrides):
    monkeypatch.setattr(es, "crear_cliente_simit", lambda s: proveedor)
    return EvaluacionService(db, settings=_settings(**settings_overrides))


class _DbFalsa:
    """Sesión mínima para el hilo de precache: db.get devuelve la
    solicitud sembrada y commit cuenta llamadas."""

    def __init__(self, solicitud):
        self._solicitud = solicitud
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, modelo, pk):
        return self._solicitud

    def commit(self):
        self.commits += 1


class _ThreadCaptura:
    """No corre el hilo: solo registra el target para invocarlo a mano
    y hacer la prueba determinista."""

    hilos = []

    def __init__(self, target=None, daemon=None, name=None):
        _ThreadCaptura.hilos.append(target)

    def start(self):
        pass


def _capturar_hilos(monkeypatch) -> list:
    _ThreadCaptura.hilos = []
    monkeypatch.setattr(threading, "Thread", _ThreadCaptura)
    return _ThreadCaptura.hilos


# ----------------------------------------------------------------------
# consultar_simit_en_linea: proveedor + caché por documento
# ----------------------------------------------------------------------


def test_consulta_en_linea_llama_proveedor_y_persiste(monkeypatch):
    proveedor = _ProveedorStub()
    svc = _servicio(_sesion_sqlite(), monkeypatch, proveedor)

    res = svc.consultar_simit_en_linea(
        TipoIdentificacion.CC, "1006461914", id_solicitud="abc"
    )

    assert res.paz_y_salvo
    assert proveedor.llamadas == [(TipoIdentificacion.CC, "1006461914")]
    filas = svc.db.query(ConsultaSimit).all()
    assert len(filas) == 1
    assert filas[0].numero_id == "1006461914"
    assert filas[0].tipo_id == "1"
    assert filas[0].origen == "portal"
    assert filas[0].id_solicitud == "abc"


def test_consulta_en_linea_reusa_resultado_vigente(monkeypatch):
    proveedor = _ProveedorStub()
    db = _sesion_sqlite()
    svc = _servicio(db, monkeypatch, proveedor)

    svc.consultar_simit_en_linea(TipoIdentificacion.CC, "1006461914")
    res = svc.consultar_simit_en_linea(TipoIdentificacion.CC, "1006461914")

    assert res.paz_y_salvo
    assert len(proveedor.llamadas) == 1  # la segunda salió del caché


def test_consulta_en_linea_sin_cache_cuando_dias_cero(monkeypatch):
    proveedor = _ProveedorStub()
    svc = _servicio(
        _sesion_sqlite(), monkeypatch, proveedor, simit_cache_dias=0
    )

    svc.consultar_simit_en_linea(TipoIdentificacion.CC, "1006461914")
    svc.consultar_simit_en_linea(TipoIdentificacion.CC, "1006461914")

    assert len(proveedor.llamadas) == 2


def test_consulta_en_linea_otra_cedula_no_reusa(monkeypatch):
    proveedor = _ProveedorStub()
    svc = _servicio(_sesion_sqlite(), monkeypatch, proveedor)

    svc.consultar_simit_en_linea(TipoIdentificacion.CC, "1006461914")
    svc.consultar_simit_en_linea(TipoIdentificacion.CE, "1006461914")

    assert len(proveedor.llamadas) == 2


def test_consulta_en_linea_propaga_error_del_portal(monkeypatch):
    proveedor = _ProveedorStub(exc=DataCreditoError("simit", 502, "portal caído"))
    svc = _servicio(_sesion_sqlite(), monkeypatch, proveedor)

    with pytest.raises(DataCreditoError):
        svc.consultar_simit_en_linea(TipoIdentificacion.CC, "1006461914")


# ----------------------------------------------------------------------
# _consultar_simit: el proveedor portal no exige SIMIT_API_KEY
# ----------------------------------------------------------------------


def _solicitud_minima() -> SimpleNamespace:
    return SimpleNamespace(
        tipo_id=TipoIdentificacion.CC,
        numero_id="1006461914",
        tiene_multas_runt=False,
    )


def test_consultar_simit_portal_no_exige_api_key(monkeypatch):
    """Regression: antes del cambio el filtro se saltaba sin
    SIMIT_API_KEY; el portal no usa key."""
    proveedor = _ProveedorStub()
    svc = _servicio(None, monkeypatch, proveedor)

    res = svc._consultar_simit(_solicitud_minima(), True, None)

    assert res is not None and res.paz_y_salvo
    assert len(proveedor.llamadas) == 1


def test_consultar_simit_placapi_sin_key_omite(monkeypatch):
    proveedor = _ProveedorStub()
    svc = _servicio(None, monkeypatch, proveedor, simit_proveedor="placapi")

    assert svc._consultar_simit(_solicitud_minima(), True, None) is None
    assert not proveedor.llamadas


def test_consultar_simit_failopen_con_portal_caido(monkeypatch):
    proveedor = _ProveedorStub(exc=DataCreditoError("simit", 502, "portal caído"))
    svc = _servicio(None, monkeypatch, proveedor)

    assert svc._consultar_simit(_solicitud_minima(), True, None) is None


def test_consultar_simit_requerido_falla_cerrado(monkeypatch):
    proveedor = _ProveedorStub(exc=DataCreditoError("simit", 502, "portal caído"))
    svc = _servicio(None, monkeypatch, proveedor, simit_requerido=True)

    with pytest.raises(ValidacionError):
        svc._consultar_simit(_solicitud_minima(), True, None)


# ----------------------------------------------------------------------
# _precalentar_simit: dispara el hilo solo con consentimiento en producción
# ----------------------------------------------------------------------


def _servicio_solicitud(monkeypatch, **settings_overrides):
    monkeypatch.setattr(
        "backend.services.solicitud_service.get_settings",
        lambda: _settings(**settings_overrides),
    )
    return SolicitudService(MagicMock())


@pytest.mark.parametrize("environment", ["produccion", "demo"])
def test_precache_dispara_hilo_con_proveedor_configurado(
    monkeypatch, environment
):
    """El gate es el proveedor real ('portal' no exige credenciales),
    no el ambiente: el mock solo aplica al motor en demo."""
    hilos = _capturar_hilos(monkeypatch)
    svc = _servicio_solicitud(monkeypatch, environment=environment)

    svc._precalentar_simit(uuid.uuid4())

    assert len(hilos) == 1 and callable(hilos[0])


@pytest.mark.parametrize(
    "overrides",
    [
        {"simit_habilitado": False},
        {"simit_proveedor": "placapi", "simit_api_key": ""},
        {"simit_proveedor": "manual"},
    ],
)
def test_precache_no_dispara_sin_condiciones(monkeypatch, overrides):
    hilos = _capturar_hilos(monkeypatch)
    svc = _servicio_solicitud(monkeypatch, **overrides)

    svc._precalentar_simit(uuid.uuid4())

    assert hilos == []


def test_hilo_precache_consulta_con_documento_del_cliente(monkeypatch):
    """El trabajo en background toma tipo+numero del cliente de la
    solicitud y persiste (commit) el resultado."""
    hilos = _capturar_hilos(monkeypatch)
    svc = _servicio_solicitud(monkeypatch)
    cliente = SimpleNamespace(tipo_documento="1", num_cedula="1006461914")
    solicitud = SimpleNamespace(cliente=cliente)
    dbf = _DbFalsa(solicitud)
    monkeypatch.setattr("backend.db_models.session.SessionLocal", lambda: dbf)
    llamadas = []

    def consulta_falsa(self, tipo, numero, id_solicitud=None, usar_cache=True):
        llamadas.append((tipo, numero, id_solicitud))
        return ResultadoSimit(True, Decimal(0), 0, "portal")

    monkeypatch.setattr(
        EvaluacionService, "consultar_simit_en_linea", consulta_falsa
    )
    id_s = uuid.uuid4()

    svc._precalentar_simit(id_s)
    hilos[0]()

    assert llamadas == [(TipoIdentificacion.CC, "1006461914", id_s)]
    assert dbf.commits == 1


def test_hilo_precache_traga_excepciones(monkeypatch):
    """Best-effort: un fallo del portal no puede tumbar el hilo ni la
    petición que registró el consentimiento."""
    hilos = _capturar_hilos(monkeypatch)
    svc = _servicio_solicitud(monkeypatch)
    monkeypatch.setattr(
        "backend.db_models.session.SessionLocal",
        lambda: (_ for _ in ()).throw(RuntimeError("sin db")),
    )
    svc._precalentar_simit(uuid.uuid4())

    hilos[0]()  # no debe propagar


# ----------------------------------------------------------------------
# registrar_consentimiento: el aceptar el tratamiento dispara el precache
# ----------------------------------------------------------------------


def test_registrar_consentimiento_dispara_precache(monkeypatch):
    llamadas = []
    monkeypatch.setattr(
        SolicitudService,
        "_precalentar_simit",
        lambda self, id_s: llamadas.append(id_s),
    )
    db = MagicMock()
    svc = SolicitudService(db)
    id_s = uuid.uuid4()

    consentimiento = svc.registrar_consentimiento(id_s, "web_asesor", "1.2.3.4")

    assert llamadas == [id_s]
    assert consentimiento.id_solicitud == id_s
    db.add.assert_called_once()
    db.flush.assert_called_once()
