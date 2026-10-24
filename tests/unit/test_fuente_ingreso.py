"""Fuente de ingreso por ocupación (PPT v4 "Valor Ingreso & Quanto").

Regla: el ingreso declarado NO alimenta el motor; solo se captura como
dato de la solicitud. La fuente efectiva depende de la ocupación:

- Empleado / Pensionado -> siempre Valor Ingreso; VI = 0 -> Rechazado.
- Fuerzas Militares     -> siempre Quanto 3 Medio (no tienen VI).
- Independiente         -> cotiza: Valor Ingreso; no cotiza: Quanto.
- Fuente aplicable = 0  -> Rechazado (E3).
"""

from datetime import date
from decimal import Decimal

import pytest

from backend.models.buro_models import Quanto, Score
from backend.models.enums import Causal, DecisionFinal, Ocupacion
from backend.services.motor_decision_service import MotorDecision
from tests.conftest import SMMLV_PRUEBAS, crear_valor_ingreso


@pytest.fixture
def motor():
    return MotorDecision(smmlv=SMMLV_PRUEBAS)


def _eval(motor, s, hdc, vi, p):
    return motor.evaluar(s, hdc, vi, p, fecha_evaluacion=date(2026, 9, 30))


def _quanto(hdc_basico, miles: Decimal | None):
    hdc_basico.quanto = Quanto(producto="62", valor_medio=miles) if miles is not None else None
    return hdc_basico


# ---------------------------------------------------------------------------
# Empleado y Pensionado: solo Valor Ingreso
# ---------------------------------------------------------------------------


class TestEmpleadoSoloValorIngreso:
    def test_sin_valor_ingreso_rechaza_aunque_haya_quanto_y_declarado(
        self, motor, solicitud_empleado, hdc_basico, parametros_demo
    ):
        """VI = 0 -> Rechazado; ni Quanto ni el declarado lo rescatan."""
        assert solicitud_empleado.ingresos_mensuales > 0  # declarado presente
        r = _eval(motor, solicitud_empleado, hdc_basico, None, parametros_demo)
        assert r.fuente_ingreso_final == "ninguna"
        assert r.decision == DecisionFinal.RECHAZADO
        assert Causal.E3 in r.causales

    def test_valor_ingreso_cero_rechaza(self, motor, solicitud_empleado, hdc_basico, parametros_demo):
        r = _eval(motor, solicitud_empleado, hdc_basico, crear_valor_ingreso(Decimal(0)), parametros_demo)
        assert r.decision == DecisionFinal.RECHAZADO
        assert Causal.E3 in r.causales

    def test_valor_ingreso_presente_ignora_quanto(self, motor, solicitud_empleado, hdc_basico, parametros_demo):
        """Con VI > 0 la fuente es Valor Ingreso, aunque Quanto difiera."""
        vi = crear_valor_ingreso(Decimal("6000000"))
        r = _eval(motor, solicitud_empleado, _quanto(hdc_basico, Decimal("1000")), vi, parametros_demo)
        assert r.fuente_ingreso_final == "valor_ingreso"
        assert r.ingreso_final == Decimal("6000000")


class TestPensionadoSoloValorIngreso:
    def test_sin_valor_ingreso_rechaza(self, motor, solicitud_empleado, hdc_basico, parametros_demo):
        s = solicitud_empleado.model_copy(update={"ocupacion": Ocupacion.PENSIONADO})
        r = _eval(motor, s, hdc_basico, None, parametros_demo)
        assert r.fuente_ingreso_final == "ninguna"
        assert r.decision == DecisionFinal.RECHAZADO
        assert Causal.E3 in r.causales


# ---------------------------------------------------------------------------
# Fuerzas Militares: siempre Quanto 3 Medio
# ---------------------------------------------------------------------------


class TestFFMMSoloQuanto:
    def test_siempre_quanto_aunque_exista_valor_ingreso(
        self, motor, solicitud_empleado, hdc_basico, parametros_demo
    ):
        """Las FFMM no tienen Valor Ingreso: la fuente es Quanto."""
        s = solicitud_empleado.model_copy(update={"ocupacion": Ocupacion.FUERZAS_MILITARES})
        vi = crear_valor_ingreso(Decimal("9000000"))
        r = _eval(motor, s, _quanto(hdc_basico, Decimal("4000")), vi, parametros_demo)
        assert r.fuente_ingreso_final == "quanto3_medio"
        assert r.ingreso_final == Decimal("4000000")  # 4000 mil pesos

    def test_quanto_cero_rechaza_aunque_haya_valor_ingreso(
        self, motor, solicitud_empleado, hdc_basico, parametros_demo
    ):
        s = solicitud_empleado.model_copy(update={"ocupacion": Ocupacion.FUERZAS_MILITARES})
        vi = crear_valor_ingreso(Decimal("9000000"))
        r = _eval(motor, s, _quanto(hdc_basico, None), vi, parametros_demo)
        assert r.decision == DecisionFinal.RECHAZADO
        assert Causal.E3 in r.causales


# ---------------------------------------------------------------------------
# Independiente: cotiza -> Valor Ingreso; no cotiza -> Quanto
# ---------------------------------------------------------------------------


class TestIndependienteFuente:
    def test_sin_valor_ingreso_usa_quanto(self, motor, solicitud_empleado, hdc_basico, parametros_demo):
        s = solicitud_empleado.model_copy(
            update={"ocupacion": Ocupacion.INDEPENDIENTE, "anios_camara_comercio": Decimal("5")}
        )
        r = _eval(motor, s, _quanto(hdc_basico, Decimal("5000")), None, parametros_demo)
        assert r.fuente_ingreso_final == "quanto3_medio"
        assert r.ingreso_final == Decimal("5000000")

    def test_cotizante_usa_valor_ingreso(self, motor, solicitud_empleado, hdc_basico, parametros_demo):
        s = solicitud_empleado.model_copy(
            update={"ocupacion": Ocupacion.INDEPENDIENTE, "anios_camara_comercio": Decimal("5")}
        )
        vi = crear_valor_ingreso(Decimal("6000000"))
        r = _eval(motor, s, hdc_basico, vi, parametros_demo)
        assert r.fuente_ingreso_final == "valor_ingreso"


# ---------------------------------------------------------------------------
# El ingreso declarado nunca es fuente, en ninguna ocupación
# ---------------------------------------------------------------------------


class TestIngresoDeclaradoIgnorado:
    @pytest.mark.parametrize(
        "ocupacion",
        [Ocupacion.EMPLEADO, Ocupacion.PENSIONADO, Ocupacion.FUERZAS_MILITARES, Ocupacion.INDEPENDIENTE],
    )
    def test_solo_declarado_rechaza(self, motor, solicitud_empleado, hdc_basico, parametros_demo, ocupacion):
        s = solicitud_empleado.model_copy(
            update={
                "ocupacion": ocupacion,
                "anios_camara_comercio": Decimal("5"),
                "ingresos_mensuales": Decimal("9000000"),
            }
        )
        r = _eval(motor, s, _quanto(hdc_basico, None), None, parametros_demo)
        assert r.fuente_ingreso_final == "ninguna"
        assert r.decision == DecisionFinal.RECHAZADO
        assert Causal.E3 in r.causales


# ---------------------------------------------------------------------------
# Exclusión de score 0/4: la causal "sin experiencia con ingreso alto"
# solo aplica cuando el ingreso alcanza el perfil ALTO de su ocupación
# ---------------------------------------------------------------------------


class TestUmbralExclusionIngresoAlto:
    def _score_excluido(self, hdc_basico, valor=0):
        hdc_basico.scores = [Score(tipo="67", puntaje=Decimal(str(valor)))]
        return hdc_basico

    def test_ingreso_medio_con_score_cero_no_es_e7(self, motor, solicitud_empleado, hdc_basico, parametros_demo):
        """1.4 <= SMMLV < 1.6 es MEDIO, no ALTO -> causal genérica, no E7."""
        vi = crear_valor_ingreso(Decimal(SMMLV_PRUEBAS) * Decimal("1.5"))
        r = _eval(motor, solicitud_empleado, self._score_excluido(hdc_basico), vi, parametros_demo)
        assert Causal.E7 not in r.causales
        assert Causal.RC3 in r.causales
        assert r.decision == DecisionFinal.RECHAZADO

    def test_ingreso_alto_con_score_cero_es_e7(self, motor, solicitud_empleado, hdc_basico, parametros_demo):
        vi = crear_valor_ingreso(Decimal(SMMLV_PRUEBAS) * Decimal("1.6"))
        r = _eval(motor, solicitud_empleado, self._score_excluido(hdc_basico), vi, parametros_demo)
        assert r.causales == [Causal.E7]

    def test_independiente_exige_perfil_alto_propio(self, motor, solicitud_empleado, hdc_basico, parametros_demo):
        s = solicitud_empleado.model_copy(update={"ocupacion": Ocupacion.INDEPENDIENTE})
        vi = crear_valor_ingreso(Decimal(SMMLV_PRUEBAS) * Decimal("2.4"))  # < 2.5 -> no es ALTO
        r = _eval(motor, s, self._score_excluido(hdc_basico, 4), vi, parametros_demo)
        assert Causal.RC3 in r.causales
        assert Causal.E7 not in r.causales
