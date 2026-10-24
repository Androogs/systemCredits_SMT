"""Tests de continuidad laboral (D27 FIJO, D28 OBRA_LABOR).
- La continuidad se mide SOLO con `meses_continuidad` de Valor Ingreso.
  La antigüedad declarada NO se usa (ppt v4: "Ya no se tiene en cuenta
  la Antigüedad Laboral").
- Umbrales:
    INDEFINIDO        → meses_cont_1
    FIJO / OBRA_LABOR → meses_cont_2
- Si el ingreso >= piso (1.0 SMMLV) y NO se cumple continuidad → GRIS.
- Si el ingreso < piso → RECHAZADO con causal Ingreso Insuficiente.
"""

from datetime import date
from decimal import Decimal

import pytest

from backend.models.enums import (
    Causal,
    Decision,
    Ocupacion,
    PerfilIngreso,
    TipoContrato,
    TipoIdentificacion,
)
from backend.services.reglas_perfil import asignar_perfil_ingreso
from tests.modelos import ParametrosIP, Solicitud

# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------


@pytest.fixture
def parametros_ppt(parametros_demo: ParametrosIP) -> ParametrosIP:
    """parametros_demo ajustado a los umbrales de ppt v4 (p.2 y p.9).

    Así los tests quedan alineados con la regla vigente, sin depender
    de los valores legacy de parametros_demo.
    """
    return parametros_demo.model_copy(
        update={
            "meses_cont_1": 6,
            "meses_cont_2": 12,
            "ingreso_e_1": Decimal("1.6"),
            "ingreso_e_2": Decimal("1.4"),
            "ingreso_e_3": Decimal("1.0"),
        }
    )


def _solicitud(tipo_contrato: TipoContrato) -> Solicitud:
    """Empleado con datos mínimos. `antiguedad_meses=0` a propósito:
    la ppt v4 la ignora, así que cualquier valor es irrelevante."""
    return Solicitud(
        tipo_id=TipoIdentificacion.CC,
        numero_id="12345678",
        primer_apellido="TEST",
        ocupacion=Ocupacion.EMPLEADO,
        tipo_contrato=tipo_contrato,
        antiguedad_meses=0,
        fecha_nacimiento=date(1985, 1, 1),
        ingresos_mensuales=Decimal("0"),
    )


# ---------------------------------------------------------------------------
# D27 / D28 – FIJO y OBRA_LABOR comparten umbral `meses_cont_2`
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tipo_contrato",
    [TipoContrato.FIJO, TipoContrato.OBRA_LABOR],
    ids=["D27_FIJO", "D28_OBRA_LABOR"],
)
class TestContinuidadFijoObra:
    """Ambos contratos comparten la regla: exigir `meses_cont_2`."""

    # ---- Cumple continuidad → perfil por banda de ingreso ----

    def test_cumple_continuidad_ingreso_alto(self, tipo_contrato, parametros_ppt):
        # meses_continuidad = 12 == meses_cont_2 → cumple
        r = asignar_perfil_ingreso(
            ingreso_final_smmlv=Decimal("2.0"),
            solicitud=_solicitud(tipo_contrato),
            params=parametros_ppt,
            meses_continuidad=12,
        )
        assert r.perfil == PerfilIngreso.ALTO
        assert r.decision_forzada is None

    def test_cumple_continuidad_ingreso_medio(self, tipo_contrato, parametros_ppt):
        # 1.5 ∈ [1.4, 1.6) → MEDIO
        r = asignar_perfil_ingreso(
            ingreso_final_smmlv=Decimal("1.5"),
            solicitud=_solicitud(tipo_contrato),
            params=parametros_ppt,
            meses_continuidad=12,
        )
        assert r.perfil == PerfilIngreso.MEDIO

    def test_cumple_continuidad_ingreso_bajo(self, tipo_contrato, parametros_ppt):
        # 1.2 ∈ [1.0, 1.4) → BAJO
        r = asignar_perfil_ingreso(
            ingreso_final_smmlv=Decimal("1.2"),
            solicitud=_solicitud(tipo_contrato),
            params=parametros_ppt,
            meses_continuidad=12,
        )
        assert r.perfil == PerfilIngreso.BAJO

    def test_cumple_continuidad_sobre_umbral_no_cambia(self, tipo_contrato, parametros_ppt):
        # 15 >= 12 → mismo resultado que con 12, no hay bonus por exceso
        r = asignar_perfil_ingreso(
            ingreso_final_smmlv=Decimal("2.0"),
            solicitud=_solicitud(tipo_contrato),
            params=parametros_ppt,
            meses_continuidad=15,
        )
        assert r.perfil == PerfilIngreso.ALTO

    # ---- NO cumple continuidad → GRIS si el ingreso alcanza el piso ----

    def test_no_cumple_continuidad_un_mes_antes_del_umbral_da_gris(self, tipo_contrato, parametros_ppt):
        # 11 = meses_cont_2 - 1 → NO cumple, ingreso alto → GRIS
        r = asignar_perfil_ingreso(
            ingreso_final_smmlv=Decimal("2.0"),
            solicitud=_solicitud(tipo_contrato),
            params=parametros_ppt,
            meses_continuidad=11,
        )
        assert r.perfil == PerfilIngreso.GRIS
        assert r.decision_forzada is None  # GRIS no rechaza aquí; se decide en cruce

    def test_no_cumple_continuidad_ingreso_justo_en_piso_da_gris(self, tipo_contrato, parametros_ppt):
        # ingreso = 1.0 == ingreso_e_3 → alcanza el piso, sin continuidad → GRIS
        r = asignar_perfil_ingreso(
            ingreso_final_smmlv=Decimal("1.0"),
            solicitud=_solicitud(tipo_contrato),
            params=parametros_ppt,
            meses_continuidad=0,
        )
        assert r.perfil == PerfilIngreso.GRIS

    def test_meses_continuidad_none_se_trata_como_cero(self, tipo_contrato, parametros_ppt):
        r = asignar_perfil_ingreso(
            ingreso_final_smmlv=Decimal("2.0"),
            solicitud=_solicitud(tipo_contrato),
            params=parametros_ppt,
            meses_continuidad=None,
        )
        assert r.perfil == PerfilIngreso.GRIS

    # ---- NO cumple continuidad + ingreso bajo el piso → RECHAZADO ----

    def test_no_cumple_continuidad_ingreso_bajo_piso_rechaza(self, tipo_contrato, parametros_ppt):
        r = asignar_perfil_ingreso(
            ingreso_final_smmlv=Decimal("0.8"),
            solicitud=_solicitud(tipo_contrato),
            params=parametros_ppt,
            meses_continuidad=0,
        )
        assert r.perfil is None
        assert r.decision_forzada == Decision.RECHAZADO
        assert r.causal_forzada == Causal.R15

    # ---- Umbral parametrizable ----

    def test_umbral_personalizado_respetado(self, tipo_contrato, parametros_ppt):
        # Override a 6: con 5 meses ya no cumple
        p = parametros_ppt.model_copy(update={"meses_cont_2": 6})
        r = asignar_perfil_ingreso(
            ingreso_final_smmlv=Decimal("2.0"),
            solicitud=_solicitud(tipo_contrato),
            params=p,
            meses_continuidad=5,
        )
        assert r.perfil == PerfilIngreso.GRIS


# ---------------------------------------------------------------------------
# Regresión: INDEFINIDO sigue usando `meses_cont_1`
# ---------------------------------------------------------------------------


class TestContinuidadIndefinido:
    def test_cumple_meses_cont_1(self, parametros_ppt):
        r = asignar_perfil_ingreso(
            ingreso_final_smmlv=Decimal("2.0"),
            solicitud=_solicitud(TipoContrato.INDEFINIDO),
            params=parametros_ppt,
            meses_continuidad=6,  # == meses_cont_1
        )
        assert r.perfil == PerfilIngreso.ALTO

    def test_no_cumple_meses_cont_1_da_gris(self, parametros_ppt):
        # 5 < 6 → no cumple. Debe dar GRIS por el umbral 1.
        r = asignar_perfil_ingreso(
            ingreso_final_smmlv=Decimal("2.0"),
            solicitud=_solicitud(TipoContrato.INDEFINIDO),
            params=parametros_ppt,
            meses_continuidad=5,
        )
        assert r.perfil == PerfilIngreso.GRIS

    def test_no_usa_umbral_de_fijo(self, parametros_ppt):
        """INDEFINIDO con 6 meses NO debe caer al umbral 12 de FIJO."""
        r = asignar_perfil_ingreso(
            ingreso_final_smmlv=Decimal("2.0"),
            solicitud=_solicitud(TipoContrato.INDEFINIDO),
            params=parametros_ppt,
            meses_continuidad=6,
        )
        assert r.perfil == PerfilIngreso.ALTO  # si usara umbral 12, daría GRIS


# ---------------------------------------------------------------------------
# Regresión: tipo de contrato ausente o NA
# ---------------------------------------------------------------------------


class TestContinuidadSinContrato:
    def test_na_no_cumple_continuidad(self, parametros_ppt):
        r = asignar_perfil_ingreso(
            ingreso_final_smmlv=Decimal("2.0"),
            solicitud=_solicitud(TipoContrato.NA),
            params=parametros_ppt,
            meses_continuidad=12,
        )
        assert r.perfil == PerfilIngreso.GRIS

    def test_none_no_cumple_continuidad(self, parametros_ppt):
        s = _solicitud(TipoContrato.NA)
        s = s.model_copy(update={"tipo_contrato": None})
        r = asignar_perfil_ingreso(
            ingreso_final_smmlv=Decimal("2.0"),
            solicitud=s,
            params=parametros_ppt,
            meses_continuidad=12,
        )
        assert r.perfil == PerfilIngreso.GRIS


# ---------------------------------------------------------------------------
# Invariante: la antigüedad declarada es irrelevante (ppt v4)
# ---------------------------------------------------------------------------


class TestAntiguedadIgnorada:
    @pytest.mark.parametrize("antiguedad", [0, 6, 36, 120])
    def test_antiguedad_no_afecta_la_clasificacion(self, antiguedad, parametros_ppt):
        """La antigüedad no debe alterar el perfil cuando la continuidad de VI
        no cumple. En ppt v4, la antigüedad ya no se usa."""
        s = _solicitud(TipoContrato.FIJO).model_copy(update={"antiguedad_meses": antiguedad})
        r = asignar_perfil_ingreso(
            ingreso_final_smmlv=Decimal("2.0"),
            solicitud=s,
            params=parametros_ppt,
            meses_continuidad=0,  # VI no cumple
        )
        assert r.perfil == PerfilIngreso.GRIS, (
            f"Con antigüedad={antiguedad} se espera GRIS "
            "porque la antigüedad NO debe usarse como sustituto de continuidad."
        )
