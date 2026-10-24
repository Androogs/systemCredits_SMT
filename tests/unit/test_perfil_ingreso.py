"""Tests de asignacion de perfil de ingreso (BRD 2.4.6)."""

from datetime import date
from decimal import Decimal

from backend.models.enums import Ocupacion, PerfilIngreso, TipoContrato, TipoIdentificacion
from backend.services.reglas_perfil import asignar_perfil_ingreso
from tests.modelos import Solicitud


def _solicitud(ocupacion: Ocupacion, contrato: TipoContrato, antiguedad: int = 36) -> Solicitud:
    return Solicitud(
        tipo_id=TipoIdentificacion.CC,
        numero_id="12345678",
        primer_apellido="TEST",
        ocupacion=ocupacion,
        tipo_contrato=contrato,
        antiguedad_meses=antiguedad,
        fecha_nacimiento=date(1980, 1, 1),
    )


def test_empleado_alto_por_continuidad(parametros_demo):
    s = _solicitud(Ocupacion.EMPLEADO, TipoContrato.INDEFINIDO)
    r = asignar_perfil_ingreso(Decimal("2.0"), s, parametros_demo, meses_continuidad=6)
    assert r.perfil == PerfilIngreso.ALTO


def test_empleado_medio(parametros_demo):
    s = _solicitud(Ocupacion.EMPLEADO, TipoContrato.INDEFINIDO)
    r = asignar_perfil_ingreso(Decimal("1.5"), s, parametros_demo, meses_continuidad=6)
    assert r.perfil == PerfilIngreso.MEDIO


def test_empleado_bajo_con_continuidad_cumplida(parametros_demo):
    """BAJO requiere cumplir continuidad (ppt 2026, p.2)."""
    s = _solicitud(Ocupacion.EMPLEADO, TipoContrato.FIJO)
    # meses_cont_2 = 12
    r = asignar_perfil_ingreso(Decimal("1.2"), s, parametros_demo, meses_continuidad=12)
    assert r.perfil == PerfilIngreso.BAJO


def test_empleado_gris_por_no_cumplir_continuidad(parametros_demo):
    """Ingreso suficiente pero sin continuidad → GRIS (ppt 2026, p.2)."""
    s = _solicitud(Ocupacion.EMPLEADO, TipoContrato.FIJO)
    # 1 < meses_cont_2 = 12 → NO cumple continuidad
    r = asignar_perfil_ingreso(Decimal("1.6"), s, parametros_demo, meses_continuidad=1)
    assert r.perfil == PerfilIngreso.GRIS


def test_empleado_rechazado_ingreso_bajo(parametros_demo):
    s = _solicitud(Ocupacion.EMPLEADO, TipoContrato.INDEFINIDO)
    r = asignar_perfil_ingreso(Decimal("0.8"), s, parametros_demo, meses_continuidad=1)
    assert r.perfil is None
    assert r.decision_forzada is not None
    assert r.decision_forzada.value == "Rechazado"


def test_pensionado_alto(parametros_demo):
    s = _solicitud(Ocupacion.PENSIONADO, TipoContrato.NA)
    r = asignar_perfil_ingreso(Decimal("3.5"), s, parametros_demo, meses_continuidad=0)
    assert r.perfil == PerfilIngreso.ALTO


def test_independiente_alto(parametros_demo):
    s = _solicitud(Ocupacion.INDEPENDIENTE, TipoContrato.NA)
    r = asignar_perfil_ingreso(Decimal("3.0"), s, parametros_demo, meses_continuidad=0)
    assert r.perfil == PerfilIngreso.ALTO


def test_independiente_medio(parametros_demo):
    s = _solicitud(Ocupacion.INDEPENDIENTE, TipoContrato.NA)
    r = asignar_perfil_ingreso(Decimal("2.2"), s, parametros_demo, meses_continuidad=0)
    assert r.perfil == PerfilIngreso.MEDIO


def test_independiente_gris(parametros_demo):
    """GRIS para independiente: ingreso entre i_4 (1.4) e i_3 (1.6)."""
    s = _solicitud(Ocupacion.INDEPENDIENTE, TipoContrato.NA)
    # ingreso=1.5 ∈ (1.4, 1.6) → GRIS
    r = asignar_perfil_ingreso(Decimal("1.5"), s, parametros_demo, meses_continuidad=0)
    assert r.perfil == PerfilIngreso.GRIS


def test_independiente_rechazado(parametros_demo):
    s = _solicitud(Ocupacion.INDEPENDIENTE, TipoContrato.NA)
    r = asignar_perfil_ingreso(Decimal("0.5"), s, parametros_demo, meses_continuidad=0)
    assert r.perfil is None
    assert r.decision_forzada is not None
