"""Reintentos y circuit breaker de los clientes de DataCrédito (D56)."""

import time
from unittest.mock import MagicMock

import pytest

from backend.config import Settings
from backend.integrations.datacredito.resiliencia import llamar_con_resiliencia
from backend.services.motor_exceptions import DataCreditoError


def _settings(**kw) -> Settings:
    base = dict(
        experian_reintentos=2,
        experian_espera_reintento_seg=0,
        experian_circuito_fallos=2,
        experian_circuito_espera_seg=0.05,
    )
    base.update(kw)
    return Settings(**base)


def test_reintenta_fallo_de_red_y_recupera():
    llamada = MagicMock(side_effect=[DataCreditoError("t1", None, "timeout"), "ok"])
    assert llamar_con_resiliencia("t1", _settings(), llamada) == "ok"
    assert llamada.call_count == 2


def test_reintenta_5xx():
    llamada = MagicMock(side_effect=[DataCreditoError("t2", 503, "down"), "ok"])
    assert llamar_con_resiliencia("t2", _settings(), llamada) == "ok"
    assert llamada.call_count == 2


def test_no_reintenta_4xx():
    llamada = MagicMock(side_effect=DataCreditoError("t3", 400, "bad request"))
    with pytest.raises(DataCreditoError):
        llamar_con_resiliencia("t3", _settings(), llamada)
    assert llamada.call_count == 1


def test_agota_reintentos_y_propaga():
    llamada = MagicMock(side_effect=DataCreditoError("t4", 503, "down"))
    with pytest.raises(DataCreditoError):
        llamar_con_resiliencia("t4", _settings(), llamada)
    assert llamada.call_count == 3  # 1 + 2 reintentos


def test_circuito_abre_tras_fallos_consecutivos():
    s = _settings()
    falla = MagicMock(side_effect=DataCreditoError("t5", 503, "down"))
    for _ in range(2):  # umbral: 2 llamadas fallidas
        with pytest.raises(DataCreditoError):
            llamar_con_resiliencia("t5", s, falla)
    falla.reset_mock()
    with pytest.raises(DataCreditoError, match="Circuit breaker abierto"):
        llamar_con_resiliencia("t5", s, falla)
    falla.assert_not_called()  # ni siquiera intenta la llamada


def test_circuito_se_cierra_tras_la_espera():
    s = _settings()
    falla = MagicMock(side_effect=DataCreditoError("t6", 503, "down"))
    for _ in range(2):
        with pytest.raises(DataCreditoError):
            llamar_con_resiliencia("t6", s, falla)
    time.sleep(0.06)  # espera_segundos=0.05
    ok = MagicMock(return_value="ok")
    assert llamar_con_resiliencia("t6", s, ok) == "ok"
