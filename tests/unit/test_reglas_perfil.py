"""Perfiles y matrices de decisión por ocupación (PPT v4 + piso del BRD)."""

from decimal import Decimal

import pytest

from backend.models.enums import Causal, Decision, Ocupacion, PerfilIngreso, PerfilScore
from backend.services.reglas_perfil import (
    asignar_perfil_ingreso,
    asignar_perfil_score,
    cruzar_perfiles_empleado,
    cruzar_perfiles_ffmm,
    cruzar_perfiles_independiente,
    cruzar_perfiles_pensionado,
    decidir_por_ocupacion,
)


@pytest.mark.parametrize(
    "score,perfil",
    [
        (770, PerfilScore.A),
        (769, PerfilScore.B),
        (700, PerfilScore.B),
        (699, PerfilScore.C),
        (620, PerfilScore.C),
        (619, PerfilScore.D),
        (520, PerfilScore.D),
    ],
)
def test_escalera_empleado(solicitud_empleado, parametros_demo, score, perfil):
    assert asignar_perfil_score(Decimal(score), solicitud_empleado, parametros_demo).perfil == perfil


@pytest.mark.parametrize("ocupacion", [Ocupacion.INDEPENDIENTE, Ocupacion.FUERZAS_MILITARES])
def test_escalera_independiente_y_ffmm(solicitud_empleado, parametros_demo, ocupacion):
    s = solicitud_empleado.model_copy(update={"ocupacion": ocupacion})
    assert asignar_perfil_score(Decimal(760), s, parametros_demo).perfil == PerfilScore.B
    assert asignar_perfil_score(Decimal(519), s, parametros_demo).causal_forzada == Causal.R14


def test_piso_sin_experiencia(solicitud_empleado, parametros_demo):
    r = asignar_perfil_score(Decimal(149), solicitud_empleado, parametros_demo)
    assert r.causal_forzada == Causal.R23 and r.decision_forzada == Decision.RECHAZADO
    assert asignar_perfil_score(Decimal(150), solicitud_empleado, parametros_demo).causal_forzada == Causal.R14


def test_sin_score(solicitud_empleado, parametros_demo):
    r = asignar_perfil_score(None, solicitud_empleado, parametros_demo)
    assert r.perfil is None and r.causal_forzada is None


@pytest.mark.parametrize(
    "smmlv,perfil",
    [("1.6", PerfilIngreso.ALTO), ("1.4", PerfilIngreso.MEDIO), ("1.0", PerfilIngreso.BAJO), ("0.99", None)],
)
def test_perfil_ingreso_pensionado(solicitud_empleado, parametros_demo, smmlv, perfil):
    s = solicitud_empleado.model_copy(update={"ocupacion": Ocupacion.PENSIONADO})
    r = asignar_perfil_ingreso(Decimal(smmlv), s, parametros_demo)
    assert r.perfil == perfil
    if perfil is None:
        assert r.causal_forzada == Causal.R15


@pytest.mark.parametrize(
    "smmlv,perfil",
    [
        ("2.5", PerfilIngreso.ALTO),
        ("2.0", PerfilIngreso.MEDIO),
        ("1.6", PerfilIngreso.BAJO),
        ("1.41", PerfilIngreso.GRIS),
        ("1.4", None),
    ],
)
def test_perfil_ingreso_independiente(solicitud_empleado, parametros_demo, smmlv, perfil):
    s = solicitud_empleado.model_copy(update={"ocupacion": Ocupacion.INDEPENDIENTE})
    assert asignar_perfil_ingreso(Decimal(smmlv), s, parametros_demo).perfil == perfil


@pytest.mark.parametrize(
    "score,ingreso,decision,causal",
    [
        (PerfilScore.A, PerfilIngreso.ALTO, Decision.APROBADO, None),
        (PerfilScore.C, PerfilIngreso.MEDIO, Decision.APROBADO, None),
        (PerfilScore.A, PerfilIngreso.BAJO, Decision.APROBADO, Causal.E4),  # Empleado + BAJO -> Aprobado
        (PerfilScore.B, PerfilIngreso.BAJO, Decision.APROBADO, Causal.E5),
        (PerfilScore.C, PerfilIngreso.BAJO, Decision.APROBADO, Causal.E6),
        (PerfilScore.B, PerfilIngreso.GRIS, Decision.RECHAZADO, Causal.RC1),
        (PerfilScore.D, PerfilIngreso.ALTO, Decision.RECHAZADO, Causal.R25),
        (None, PerfilIngreso.ALTO, Decision.RECHAZADO, None),
    ],
)
def test_matriz_empleado(score, ingreso, decision, causal):
    r = cruzar_perfiles_empleado(score, ingreso)
    assert (r.decision, r.causal) == (decision, causal)


@pytest.mark.parametrize(
    "score,ingreso,anios,decision,causal",
    [
        (PerfilScore.A, PerfilIngreso.ALTO, 1, Decision.APROBADO, None),
        (PerfilScore.A, PerfilIngreso.ALTO, 0, Decision.RECHAZADO, Causal.R24),
        (PerfilScore.B, PerfilIngreso.MEDIO, 2, Decision.APROBADO, None),
        (PerfilScore.B, PerfilIngreso.MEDIO, Decimal("1.5"), Decision.RECHAZADO, Causal.R24),
        (PerfilScore.C, PerfilIngreso.BAJO, 3, Decision.RECHAZADO, Causal.E6),  # Independiente + BAJO -> Rechazado
        (PerfilScore.A, PerfilIngreso.GRIS, 4, Decision.RECHAZADO, Causal.R15),  # GRIS -> Rechazado
        (PerfilScore.A, PerfilIngreso.GRIS, 3, Decision.RECHAZADO, Causal.R24),
        (PerfilScore.D, PerfilIngreso.ALTO, 4, Decision.RECHAZADO, Causal.R25),
        (PerfilScore.D, PerfilIngreso.ALTO, 3, Decision.RECHAZADO, Causal.R24),
    ],
)
def test_matriz_independiente(parametros_demo, score, ingreso, anios, decision, causal):
    r = cruzar_perfiles_independiente(score, ingreso, anios, parametros_demo)
    assert (r.decision, r.causal) == (decision, causal)


def test_decidir_por_ocupacion_enruta(solicitud_empleado, parametros_demo):
    ind = solicitud_empleado.model_copy(update={"ocupacion": Ocupacion.INDEPENDIENTE, "anios_camara_comercio": None})
    assert decidir_por_ocupacion(ind, PerfilScore.A, PerfilIngreso.ALTO, parametros_demo).causal == Causal.R16
    assert (
        decidir_por_ocupacion(solicitud_empleado, PerfilScore.A, PerfilIngreso.ALTO, parametros_demo).decision
        == Decision.APROBADO
    )


def test_independiente_con_camara_sin_antiguedad_minima(parametros_demo):
    r = cruzar_perfiles_independiente(PerfilScore.A, PerfilIngreso.ALTO, Decimal("0"), parametros_demo)
    assert r.causal == Causal.R24


@pytest.mark.parametrize(
    "score,ingreso,decision,causal",
    [
        (PerfilScore.A, PerfilIngreso.ALTO, Decision.APROBADO, None),
        (PerfilScore.C, PerfilIngreso.MEDIO, Decision.APROBADO, None),
        (PerfilScore.A, PerfilIngreso.BAJO, Decision.RECHAZADO, Causal.E4),  # Pensionado + BAJO -> Rechazado
        (PerfilScore.B, PerfilIngreso.BAJO, Decision.RECHAZADO, Causal.E5),
        (PerfilScore.C, PerfilIngreso.BAJO, Decision.RECHAZADO, Causal.E6),
        (PerfilScore.B, PerfilIngreso.GRIS, Decision.RECHAZADO, Causal.RC1),
        (PerfilScore.D, PerfilIngreso.ALTO, Decision.RECHAZADO, Causal.R25),
        (None, PerfilIngreso.ALTO, Decision.RECHAZADO, None),
        (PerfilScore.A, None, Decision.RECHAZADO, None),
    ],
)
def test_matriz_pensionado(score, ingreso, decision, causal):
    r = cruzar_perfiles_pensionado(score, ingreso)
    assert (r.decision, r.causal) == (decision, causal)


@pytest.mark.parametrize(
    "score,ingreso,decision,causal",
    [
        (PerfilScore.A, PerfilIngreso.ALTO, Decision.APROBADO, None),
        (PerfilScore.C, PerfilIngreso.MEDIO, Decision.APROBADO, None),
        (PerfilScore.A, PerfilIngreso.BAJO, Decision.RECHAZADO, Causal.E4),  # FFMM + BAJO -> Rechazado
        (PerfilScore.B, PerfilIngreso.BAJO, Decision.RECHAZADO, Causal.E5),
        (PerfilScore.C, PerfilIngreso.BAJO, Decision.RECHAZADO, Causal.E6),
        (PerfilScore.B, PerfilIngreso.GRIS, Decision.RECHAZADO, Causal.R15),
        (PerfilScore.D, PerfilIngreso.ALTO, Decision.RECHAZADO, Causal.R25),
        (None, PerfilIngreso.ALTO, Decision.RECHAZADO, None),
        (PerfilScore.A, None, Decision.RECHAZADO, None),
    ],
)
def test_matriz_ffmm(score, ingreso, decision, causal):
    r = cruzar_perfiles_ffmm(score, ingreso)
    assert (r.decision, r.causal) == (decision, causal)


def test_independiente_perfil_incompleto(parametros_demo):
    for score, ingreso in [(None, PerfilIngreso.ALTO), (PerfilScore.A, None)]:
        r = cruzar_perfiles_independiente(score, ingreso, 5, parametros_demo)
        assert r.decision == Decision.RECHAZADO and r.causal is None


def test_decidir_por_ocupacion_enruta_pensionado_y_ffmm(solicitud_empleado, parametros_demo):
    pensionado = solicitud_empleado.model_copy(update={"ocupacion": Ocupacion.PENSIONADO})
    ffmm = solicitud_empleado.model_copy(update={"ocupacion": Ocupacion.FUERZAS_MILITARES})
    # ALTO aprueba en ambas; BAJO rechaza (a diferencia de Empleado)
    assert (
        decidir_por_ocupacion(pensionado, PerfilScore.A, PerfilIngreso.ALTO, parametros_demo).decision
        == Decision.APROBADO
    )
    assert (
        decidir_por_ocupacion(ffmm, PerfilScore.A, PerfilIngreso.ALTO, parametros_demo).decision
        == Decision.APROBADO
    )
    assert (
        decidir_por_ocupacion(pensionado, PerfilScore.A, PerfilIngreso.BAJO, parametros_demo).causal
        == Causal.E4
    )
    assert (
        decidir_por_ocupacion(ffmm, PerfilScore.A, PerfilIngreso.BAJO, parametros_demo).causal == Causal.E4
    )
