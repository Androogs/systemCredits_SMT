"""Tests del motor de decision completo."""

from decimal import Decimal

from backend.models.enums import Causal, Decision, PerfilIngreso, PerfilScore
from backend.services.motor_decision_service import MotorDecision
from backend.services.reglas_ingreso import calcular_ingreso_final
from backend.services.reglas_perfil import asignar_perfil_score, cruzar_perfiles_empleado
from backend.services.valor_ingreso_service import calcular_valor_ingreso
from tests.modelos import RespuestaValorIngreso, Score


def test_ingreso_final_usa_valor_ingreso(solicitud_empleado):
    r = calcular_ingreso_final(solicitud_empleado, Decimal("5000000"), Decimal("0"))
    assert r.ingreso_final == Decimal("5000000")
    assert r.decision_forzada is None


def test_ingreso_final_sin_datos_fuerza_rechazo(solicitud_empleado):
    # Para que se dispare la regla, TODOS los ingresos deben ser 0
    solicitud = solicitud_empleado.model_copy(update={"ingresos_mensuales": Decimal("0")})
    r = calcular_ingreso_final(solicitud, Decimal("0"), Decimal("0"))
    assert r.ingreso_final == Decimal("0")
    assert r.decision_forzada == Decision.RECHAZADO
    assert r.causal_forzada == Causal.E3  # Sin Valor Ingreso, Quanto ni declarado


def test_ingreso_final_empleado_sin_valor_ingreso_rechaza(solicitud_empleado):
    # PPT v4: el empleado solo usa Valor Ingreso; Quanto no lo rescata.
    r = calcular_ingreso_final(solicitud_empleado, Decimal("0"), Decimal("3000000"))
    assert r.ingreso_final == Decimal("0")
    assert r.decision_forzada == Decision.RECHAZADO
    assert r.causal_forzada == Causal.E3


def test_perfil_score_A(solicitud_empleado, parametros_demo):
    r = asignar_perfil_score(Decimal("850"), solicitud_empleado, parametros_demo)
    assert r.perfil == PerfilScore.A


def test_perfil_score_D(solicitud_empleado, parametros_demo):
    r = asignar_perfil_score(Decimal("520"), solicitud_empleado, parametros_demo)
    assert r.perfil == PerfilScore.D


def test_perfil_score_rechazado(solicitud_empleado, parametros_demo):
    r = asignar_perfil_score(Decimal("300"), solicitud_empleado, parametros_demo)
    assert r.perfil is None
    assert r.decision_forzada == Decision.RECHAZADO
    assert r.causal_forzada == Causal.R14


def test_cruce_perfiles_A_ALTO():
    r = cruzar_perfiles_empleado(PerfilScore.A, PerfilIngreso.ALTO)
    assert r.decision == Decision.APROBADO


def test_cruce_perfiles_A_BAJO():
    r = cruzar_perfiles_empleado(PerfilScore.A, PerfilIngreso.BAJO)
    assert r.decision == Decision.APROBADO
    assert r.causal == Causal.E4


def test_cruce_perfiles_D():
    r = cruzar_perfiles_empleado(PerfilScore.D, PerfilIngreso.ALTO)
    assert r.decision == Decision.RECHAZADO
    assert r.causal == Causal.R25


def test_valor_ingreso_sin_aportantes():
    assert calcular_valor_ingreso(None) == Decimal(0)
    assert calcular_valor_ingreso(RespuestaValorIngreso()) == Decimal(0)


def test_motor_aprobado(solicitud_empleado, hdc_basico, parametros_demo):
    """Cliente aprobado: requiere Valor Ingreso con continuidad >= meses_cont_1.

    Sin RespuestaValorIngreso, un Empleado INDEFINIDO no cumple continuidad
    """
    from tests.modelos import (
        Aportante,
        PeriodoPago,
        RespuestaValorIngreso,
        ResumenGeneralIngresos,
    )

    vi = RespuestaValorIngreso(
        aportantes=[
            Aportante(
                razon_social="EMPLEADOR SA",
                tipo_cotizante=1,
                resultado_pagos=[
                    PeriodoPago(anio=2026, mes=9, realizo_pago=True, ingresos=Decimal("5000000")),
                    PeriodoPago(anio=2026, mes=8, realizo_pago=True, ingresos=Decimal("5000000")),
                    PeriodoPago(anio=2026, mes=7, realizo_pago=True, ingresos=Decimal("5000000")),
                ],
            )
        ],
        resumen_general=ResumenGeneralIngresos(meses_continuidad=6),
    )

    motor = MotorDecision(smmlv=1300000)
    r = motor.evaluar(solicitud_empleado, hdc_basico, vi, parametros_demo)
    assert r.decision == Decision.APROBADO
    assert r.evaluacion_id
    assert r.tiempo_ms >= 0


def test_motor_empleado_sin_valor_ingreso_rechaza_e3(solicitud_empleado, hdc_basico, parametros_demo):
    """Sin Valor Ingreso el empleado no tiene fuente de ingreso → Rechazado E3"""
    motor = MotorDecision(smmlv=1300000)
    r = motor.evaluar(solicitud_empleado, hdc_basico, None, parametros_demo)
    assert r.decision == Decision.RECHAZADO
    assert Causal.E3 in r.causales


def test_motor_score_bajo_rechaza(solicitud_empleado, hdc_basico, parametros_demo):
    hdc_basico.scores = [Score(tipo="67", puntaje=Decimal("300"))]
    motor = MotorDecision(smmlv=1300000)
    r = motor.evaluar(solicitud_empleado, hdc_basico, None, parametros_demo)
    assert r.decision == Decision.RECHAZADO
    assert Causal.R14 in r.causales


def test_motor_documento_no_vigente(solicitud_empleado, hdc_basico, parametros_demo):
    hdc_basico.persona.estado_documento = "21"  # Cancelada por muerte
    motor = MotorDecision(smmlv=1300000)
    r = motor.evaluar(solicitud_empleado, hdc_basico, None, parametros_demo)
    assert r.decision == Decision.RECHAZADO
    assert Causal.R12 in r.causales
