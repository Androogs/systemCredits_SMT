"""Pruebas de extremo a extremo del motor puro (MotorDecision)."""

from datetime import date
from decimal import Decimal

import pytest

from backend.models.buro_models import CuentaAhorro, CuentaCartera, Quanto, Score
from backend.models.enums import Causal, Decision, DecisionFinal, Ocupacion
from backend.services.motor_decision_service import MotorDecision, extraer_score, ordenar_causales
from backend.services.motor_exceptions import ValidacionError
from tests.conftest import SMMLV_PRUEBAS, crear_valor_ingreso


@pytest.fixture
def motor():
    return MotorDecision(smmlv=SMMLV_PRUEBAS)


def _eval(motor, s, hdc, vi, p):
    return motor.evaluar(s, hdc, vi, p, fecha_evaluacion=date(2026, 9, 30))


def test_aprobado_limpio(motor, solicitud_empleado, hdc_basico, vi_con_continuidad, parametros_demo):
    r = _eval(motor, solicitud_empleado, hdc_basico, vi_con_continuidad, parametros_demo)
    assert r.decision == DecisionFinal.APROBADO
    assert r.decision_interna == Decision.APROBADO
    assert r.causales == []
    assert r.fuente_ingreso_final == "valor_ingreso"
    assert r.perfil_score.value == "A" and r.perfil_ingreso.value == "ALTO"
    assert [p.etapa for p in r.trazabilidad] == [
        "filtros_duros",
        "ingreso_final",
        "perfil_score",
        "perfil_ingreso",
        "matriz_decision",
        "capacidad_pago",
    ]
    assert r.parametros_usados["score_ep_1"] == 770


def test_perfil_bajo_aprueba_con_causal_de_trazabilidad(motor, solicitud_empleado, hdc_basico, parametros_demo):
    """Empleado + BAJO aprueba; E4 queda en causales solo como trazabilidad."""
    vi = crear_valor_ingreso(Decimal(SMMLV_PRUEBAS) * Decimal("1.2"))  # perfil BAJO
    r = _eval(motor, solicitud_empleado, hdc_basico, vi, parametros_demo)
    assert r.decision == DecisionFinal.APROBADO
    assert r.decision_interna == Decision.APROBADO
    assert r.causales == [Causal.E4]


def test_cuota_moto_sobre_capacidad_aprueba_con_cupo_real(
    motor, solicitud_empleado, hdc_basico, vi_con_continuidad, parametros_demo
):
    """E9 no rechaza: el cupo que gobierna la oferta sale de los datos de
    centrales; la cuota del saldo referencial queda como trazabilidad."""
    s = solicitud_empleado.model_copy(update={"saldo_financiar": Decimal("100000000")})
    r = _eval(motor, s, hdc_basico, vi_con_continuidad, parametros_demo)
    assert r.decision == DecisionFinal.APROBADO
    assert r.causales == [Causal.E9]


def test_causales_ordenadas_por_prioridad(motor, solicitud_empleado, hdc_basico, parametros_demo):
    hdc_basico.cuentas_cartera = [CuentaCartera(comportamiento="1" + "N" * 20, estado_pago="17", calidad_deudor="00")]
    hdc_basico.cuentas_ahorro = [CuentaAhorro(estado="06")]
    r = _eval(motor, solicitud_empleado, hdc_basico, crear_valor_ingreso(), parametros_demo)
    assert r.causales[0] == Causal.R2
    assert Causal.E2 in r.causales
    assert r.decision_interna == Decision.RECHAZADO


def test_ordenar_causales_deduplica():
    # D185: todas las causales son tipo Rechazo — el sort estable
    # conserva el orden de llegada (y deduplica).
    assert ordenar_causales([Causal.E4, Causal.RC2, Causal.R2, Causal.E4, Causal.R14]) == [
        Causal.E4,
        Causal.RC2,
        Causal.R2,
        Causal.R14,
    ]


@pytest.mark.parametrize(
    "ingreso,causal,tipo",
    [
        (Decimal("5000000"), Causal.E7, Decision.RECHAZADO),  # >= 1.6 SMMLV (ALTO)
        # D185: las RC (antes "Requiere Codeudor") rechazan directo.
        (Decimal("1300000"), Causal.RC3, Decision.RECHAZADO),
    ],
)
def test_exclusion_score_depende_del_ingreso(
    motor, solicitud_empleado, hdc_basico, parametros_demo, ingreso, causal, tipo
):
    hdc_basico.scores = [Score(tipo="67", puntaje=Decimal("0"))]
    r = _eval(motor, solicitud_empleado, hdc_basico, crear_valor_ingreso(ingreso), parametros_demo)
    assert r.causales == [causal]
    assert r.decision_interna == tipo
    assert r.perfil_score is None
    assert r.indicadores_buro["score_codigo_exclusion"] == 0


def test_exclusion_independiente_usa_umbral_ingreso_i_1(motor, solicitud_empleado, hdc_basico, parametros_demo):
    s = solicitud_empleado.model_copy(update={"ocupacion": Ocupacion.INDEPENDIENTE})
    hdc_basico.scores = [Score(tipo="67", puntaje=Decimal("4"))]
    vi = crear_valor_ingreso(Decimal(SMMLV_PRUEBAS) * Decimal("1.8"))  # >= 1.4 pero < 2.0
    r = _eval(motor, s, hdc_basico, vi, parametros_demo)
    assert r.causales == [Causal.RC3]


def test_fallecido(motor, solicitud_empleado, hdc_basico, vi_con_continuidad, parametros_demo):
    hdc_basico.scores = [Score(tipo="67", puntaje=Decimal("3"))]
    r = _eval(motor, solicitud_empleado, hdc_basico, vi_con_continuidad, parametros_demo)
    assert r.causales[0] == Causal.R1
    assert r.indicadores_buro["reportado_fallecido"] is True


def test_sin_score_contratado_no_aprueba(motor, solicitud_empleado, hdc_basico, vi_con_continuidad, parametros_demo):
    hdc_basico.scores = [Score(tipo="XX", puntaje=Decimal("900"))]
    r = _eval(motor, solicitud_empleado, hdc_basico, vi_con_continuidad, parametros_demo)
    assert r.decision == DecisionFinal.RECHAZADO
    assert r.causales == [Causal.R20]
    assert r.score_consultado is None
    assert any("score" in a for a in r.advertencias)


def test_extraer_score_respeta_orden_de_preferencia(hdc_basico, parametros_demo):
    hdc_basico.scores = [Score(tipo="Z0", puntaje=Decimal("650")), Score(tipo="67", puntaje=Decimal("800"))]
    assert extraer_score(hdc_basico, parametros_demo) == (Decimal("800"), "67")


def test_sin_ningun_ingreso(motor, solicitud_empleado, hdc_basico, parametros_demo):
    s = solicitud_empleado.model_copy(update={"ingresos_mensuales": Decimal(0)})
    hdc_basico.quanto = Quanto(producto="62", valor_medio=Decimal(0))
    r = _eval(motor, s, hdc_basico, None, parametros_demo)
    assert Causal.E3 in r.causales and Causal.R15 in r.causales
    assert r.fuente_ingreso_final == "ninguna"


def test_ingreso_por_quanto_en_pesos(motor, solicitud_empleado, hdc_basico, parametros_demo):
    # FFMM siempre toma Quanto 3 Medio (PPT v4: no tienen Valor Ingreso).
    s = solicitud_empleado.model_copy(update={"ocupacion": Ocupacion.FUERZAS_MILITARES})
    r = _eval(motor, s, hdc_basico, None, parametros_demo)
    assert r.fuente_ingreso_final == "quanto3_medio"
    assert r.ingreso_final == Decimal("5000000.00")  # 5000 miles


def test_ingreso_declarado_no_es_fuente(motor, solicitud_empleado, hdc_basico, parametros_demo):
    # PPT v4: el ingreso declarado se captura pero no alimenta el motor.
    hdc_basico.quanto = None
    r = _eval(motor, solicitud_empleado, hdc_basico, None, parametros_demo)
    assert r.fuente_ingreso_final == "ninguna"
    assert Causal.E3 in r.causales


def test_independiente_aprobado_con_camara(motor, solicitud_empleado, hdc_basico, parametros_demo):
    s = solicitud_empleado.model_copy(
        update={"ocupacion": Ocupacion.INDEPENDIENTE, "anios_camara_comercio": Decimal(2)}
    )
    hdc_basico.scores = [Score(tipo="67", puntaje=Decimal("780"))]
    vi = crear_valor_ingreso(Decimal(SMMLV_PRUEBAS) * 3, continuidad=None)
    r = _eval(motor, s, hdc_basico, vi, parametros_demo)
    assert r.decision == DecisionFinal.APROBADO


def test_valores_redondeados(motor, solicitud_empleado, hdc_basico, vi_con_continuidad, parametros_demo):
    r = _eval(motor, solicitud_empleado, hdc_basico, vi_con_continuidad, parametros_demo)
    assert r.cupo_sugerido == r.cupo_sugerido.quantize(Decimal("0.01"))
    assert r.ingreso_final_smmlv == r.ingreso_final_smmlv.quantize(Decimal("0.0001"))


def test_smmlv_invalido():
    with pytest.raises(ValidacionError):
        MotorDecision(smmlv=0)
