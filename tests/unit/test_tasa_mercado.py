"""Tasa de mercado: conversión EA→m.v., modalidad por monto,
parseo del dataset TIBC y caché con degradado del servicio."""

import pytest

from backend.services.motor_exceptions import DataCreditoError
from backend.services.tasa_mercado_service import (
    MODALIDAD_BAJO_MONTO,
    MODALIDAD_ORDINARIO,
    TasaMercadoService,
    ea_a_mv,
    modalidad_por_monto,
)

SMMLV = 1_750_905
UMBRAL = 6 * SMMLV  # 10.505.430

FILAS = [
    {
        "resolucion": "1472",
        "vigencia_desde": "2026-10-01T00:00:00.000",
        "vigencia_hasta": "2026-10-31T00:00:00.000",
        "interes_bancario_corriente": "44.44%",
        "modalidad": MODALIDAD_BAJO_MONTO,
    },
    {
        "resolucion": "1472",
        "vigencia_desde": "2026-10-01T00:00:00.000",
        "vigencia_hasta": "2026-10-31T00:00:00.000",
        "interes_bancario_corriente": "19.06%",
        "modalidad": MODALIDAD_ORDINARIO,
    },
]


class ClienteFalso:
    """Cliente SFC simulado: devuelve filas o falla, cuenta llamadas."""

    def __init__(self, filas=None, error=None):
        self.filas = FILAS if filas is None else filas
        self.error = error
        self.llamadas = 0

    def tasas_vigentes(self, modalidades):
        self.llamadas += 1
        if self.error:
            raise self.error
        return [f for f in self.filas if f["modalidad"] in modalidades]


class SettingsFalso:
    smmlv = SMMLV
    sfc_tasas_cache_segundos = 21_600.0


def servicio(cliente=None):
    return TasaMercadoService(cliente or ClienteFalso(), SettingsFalso())


def test_ea_a_mv_convierte_tasa_efectiva_anual():
    # (1 + 44.44%)^(1/12) - 1 = 3.1115% m.v.; (1 + 19.06%)^(1/12) - 1 = 1.4643%
    assert ea_a_mv(44.44) == pytest.approx(3.1115, abs=0.001)
    assert ea_a_mv(19.06) == pytest.approx(1.4643, abs=0.001)


def test_modalidad_bajo_monto_hasta_seis_smmlv():
    assert modalidad_por_monto(6_000_000, SMMLV) == MODALIDAD_BAJO_MONTO
    # El tope es inclusivo: 6 SMMLV exactos siguen siendo bajo monto.
    assert modalidad_por_monto(UMBRAL, SMMLV) == MODALIDAD_BAJO_MONTO
    assert modalidad_por_monto(None, SMMLV) == MODALIDAD_BAJO_MONTO


def test_modalidad_ordinario_sobre_el_umbral():
    assert modalidad_por_monto(UMBRAL + 1, SMMLV) == MODALIDAD_ORDINARIO
    assert modalidad_por_monto(20_000_000, SMMLV) == MODALIDAD_ORDINARIO


def test_respuesta_incluye_modalidades_convertidas_y_usura():
    datos = servicio().tasas()
    assert datos.umbral_bajo_monto == UMBRAL
    bajo = datos.bajo_monto
    assert bajo.modalidad == MODALIDAD_BAJO_MONTO
    assert bajo.tasa_ea == pytest.approx(44.44)
    assert bajo.tasa_mv == pytest.approx(3.1115, abs=0.001)
    # Usura = 1.5x el interés corriente (art. 305 Código Penal).
    assert bajo.usura_ea == pytest.approx(66.66)
    assert bajo.vigencia_hasta == "2026-10-31"
    assert bajo.resolucion == "1472"
    assert datos.ordinario.tasa_ea == pytest.approx(19.06)
    assert datos.ordinario.tasa_mv == pytest.approx(1.4643, abs=0.001)


def test_cache_evita_llamadas_repetidas_a_datos_gov():
    cliente = ClienteFalso()
    svc = servicio(cliente)
    svc.tasas()
    svc.tasas()
    assert cliente.llamadas == 1


def test_degradado_devuelve_cache_expirada_si_la_fuente_falla():
    cliente = ClienteFalso()
    svc = servicio(cliente)
    datos = svc.tasas()
    # Expira la cache y la fuente empieza a fallar: se sigue sirviendo
    # la última lectura conocida en vez de tumbar el endpoint.
    svc._cache = (0.0, datos)
    cliente.error = DataCreditoError("sfc_tasas", 500, "caído")
    assert svc.tasas() is datos


def test_sin_cache_y_fuente_caida_propaga_error():
    svc = servicio(
        ClienteFalso(error=DataCreditoError("sfc_tasas", 500, "caído"))
    )
    with pytest.raises(DataCreditoError):
        svc.tasas()


def test_filas_sin_la_modalidad_pedida_se_ignoran():
    filas = FILAS + [
        {
            "resolucion": "1472",
            "vigencia_desde": "2026-10-01T00:00:00.000",
            "vigencia_hasta": "2026-10-31T00:00:00.000",
            "interes_bancario_corriente": "27.50%",
            "modalidad": "CREDITO PRODUCTIVO MAYOR MONTO",
        }
    ]
    datos = servicio(ClienteFalso(filas=filas)).tasas()
    assert datos.bajo_monto.tasa_ea == pytest.approx(44.44)
    assert datos.ordinario.tasa_ea == pytest.approx(19.06)


def test_modalidad_faltante_en_respuesta_es_error():
    svc = servicio(ClienteFalso(filas=[FILAS[0]]))
    with pytest.raises(DataCreditoError):
        svc.tasas()
