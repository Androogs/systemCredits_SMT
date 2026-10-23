"""Pruebas de parámetros: valores V4, validación de coherencia y almacenamiento."""

import json
from decimal import Decimal

import pytest

from backend.services.motor_exceptions import ParametrosError
from backend.services.motor_parametros import PARAMETROS_DEFAULT, MotorParametros, ParametrosStore


def test_defaults_ppt_v4():
    p = MotorParametros()
    assert p.capacidad_pago_pct_empleado == 70
    assert p.capacidad_pago_pct_independiente == 60
    assert p.capacidad_pago_pct_ffmm == 65
    assert p.capacidad_pago_factor_comportamiento == Decimal("1.0")
    assert p.capacidad_pago_limite_ingresos_pct == 85
    assert p.capacidad_pago_factor_macro == Decimal("1.0")
    assert p.capacidad_pago_pct_region_nacional == 70
    assert p.capacidad_pago_pct_region_costa == 68
    assert p.capacidad_pago_pct_region_andina == 72
    assert p.capacidad_pago_pct_region_pacifico == 69
    assert p.saldo_mora_be == 300000
    assert (p.cupo_sugerido_tasa_pct, p.cupo_sugerido_plazo_meses, p.cupo_sugerido_tope) == (2, 24, 20000000)


def test_archivo_parametros_del_proyecto_coincide_con_defaults():
    from backend.config import RAIZ_PROYECTO

    datos = json.loads((RAIZ_PROYECTO / "parametros.json").read_text(encoding="utf-8"))
    assert datos == PARAMETROS_DEFAULT


@pytest.mark.parametrize(
    "cambio",
    [
        {"score_ep_2": 760},  # escalera no descendente
        {"ingreso_i_4": 1.7},  # gris por encima de bajo
        {"anios_cam_1": 5},  # cámara no ascendente
        {"endeu_2": 95},  # estudio >= rechazo
        {"edad_minima_be": 70},  # mínimo >= máximo
        {"capacidad_pago_pct": 120},  # porcentaje fuera de rango
        {"codigos_score": []},
        {"campo_inexistente": 1},
        # Nuevos parámetros v5 que deben ser validados
        {"capacidad_pago_pct_empleado": 120},  # porcentaje fuera de rango
        {"capacidad_pago_pct_independiente": -5},  # negativo
        {"capacidad_pago_pct_ffmm": 101},  # mayor que 100
        {"capacidad_pago_factor_comportamiento": 3.0},  # factor > 2.0
        {"capacidad_pago_limite_ingresos_pct": -10},  # negativo
        {"capacidad_pago_factor_macro": -1.5},  # factor negativo
        {"capacidad_pago_pct_region_costa": 95},  # mayor que 100
        {"capacidad_pago_pct_region_andina": -5},  # negativo
        {"capacidad_pago_pct_region_pacifico": 101},  # mayor que 100
        {"capacidad_pago_factor_macro": 2.5},  # factor > 2.0
        {"capacidad_pago_factor_comportamiento": 0.5},  # factor muy bajo
        {"capacidad_pago_pct_region_costa": 55},  # mínimo no alcanzado
    ],
)
def test_parametros_incoherentes_se_rechazan(tmp_path, cambio):
    store = ParametrosStore(tmp_path / "p.json")
    with pytest.raises(ParametrosError):
        store.actualizar(cambio)
    # El archivo no se modifica si la validación falla
    assert json.loads((tmp_path / "p.json").read_text()) == PARAMETROS_DEFAULT


def test_store_crea_actualiza_y_restablece(tmp_path):
    store = ParametrosStore(tmp_path / "sub" / "p.json")
    assert store.cargar() == MotorParametros()
    actualizado = store.actualizar({"endeu_2": 80})
    assert actualizado.endeu_2 == 80
    assert json.loads((tmp_path / "sub" / "p.json").read_text())["endeu_2"] == 80
    assert store.restablecer().endeu_2 == 86


def test_archivo_parcial_completa_con_defaults(tmp_path):
    ruta = tmp_path / "p.json"
    ruta.write_text(json.dumps({"endeu_1": 88}))
    p = ParametrosStore(ruta).cargar()
    assert p.endeu_1 == 88 and p.score_ep_1 == 750


def test_json_invalido(tmp_path):
    ruta = tmp_path / "p.json"
    ruta.write_text("{no es json")
    with pytest.raises(ParametrosError):
        ParametrosStore(ruta).cargar()


def test_override_por_entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("MOTOR_ENDEU_1", "88")
    monkeypatch.setenv("MOTOR_CODIGOS_SCORE", "Z0, 67")
    monkeypatch.setenv("MOTOR_SCORES_EXCLUSION", "0, 4")
    store = ParametrosStore(tmp_path / "p.json")
    p = store.cargar()
    assert p.endeu_1 == 88
    assert p.codigos_score == ["Z0", "67"]
    assert p.scores_exclusion == [0, 4]
    assert store.campos_bloqueados_por_entorno() == ["codigos_score", "endeu_1", "scores_exclusion"]


def test_snapshot_es_json_numerico():
    snap = MotorParametros().snapshot()
    assert snap["score_ep_1"] == 750 and isinstance(snap["score_ep_1"], int)
    assert snap["ingreso_e_1"] == 1.6
    json.dumps(snap)


def test_huella_estable_y_sensible_a_cambios():
    base = MotorParametros()
    assert base.huella() == MotorParametros().huella()
    assert len(base.huella()) == 16
    assert MotorParametros(endeu_1=base.endeu_1 + 1).huella() != base.huella()
