"""Pruebas de parámetros: valores V4, validación de coherencia y almacenamiento."""

import json
from decimal import Decimal

import pytest

from backend.services.motor_exceptions import ParametrosError
from backend.services.motor_parametros import PARAMETROS_DEFAULT, MotorParametros, ParametrosStore


def test_defaults_ppt_v4():
    p = MotorParametros()
    assert (p.score_ep_1, p.score_ep_2, p.score_ep_3, p.score_ep_4) == (750, 680, 600, 500)
    assert (p.score_if_1, p.score_if_2, p.score_if_3, p.score_if_4) == (770, 700, 620, 520)
    assert (p.ingreso_e_1, p.ingreso_e_2, p.ingreso_e_3) == (Decimal("1.6"), Decimal("1.4"), Decimal("1.0"))
    assert (p.ingreso_i_1, p.ingreso_i_2, p.ingreso_i_3, p.ingreso_i_4) == (
        Decimal("2.5"),
        Decimal("2.0"),
        Decimal("1.6"),
        Decimal("1.4"),
    )
    assert (p.meses_cont_1, p.meses_cont_2) == (5, 10)
    assert (p.anios_cam_1, p.anios_cam_2, p.anios_cam_3, p.anios_cam_4) == (1, 2, 3, 4)
    assert (p.edad_minima_be, p.edad_maxima_be) == (18, 66)
    assert (p.endeu_1, p.endeu_2) == (90, 86)
    assert (p.gastos_personales_pct_bajo, p.gastos_personales_pct_medio, p.gastos_personales_pct_alto) == (50, 45, 40)
    assert p.capacidad_pago_pct == 70
    assert p.saldo_mora_be == 300000
    assert (p.cupo_sugerido_tasa_pct, p.cupo_sugerido_plazo_meses, p.cupo_sugerido_tope) == (2, 24, 20000000)
    assert p.scores_exclusion == [0, 4]
    assert p.calificaciones_negativas == ["C", "D", "E", "K"]


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
