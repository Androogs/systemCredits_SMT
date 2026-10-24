"""Fixtures compartidas de las pruebas del motor."""

from datetime import date
from decimal import Decimal

import pytest

from backend.models.buro_models import (
    Aportante,
    PeriodoPago,
    PersonaBasica,
    Quanto,
    RespuestaHDC,
    RespuestaValorIngreso,
    ResumenGeneralIngresos,
    Score,
)
from backend.models.enums import Ocupacion, TipoContrato, TipoIdentificacion
from backend.models.motor_models import Solicitud
from backend.services.motor_parametros import MotorParametros

SMMLV_PRUEBAS = 1_750_905  # valor fijo para que los cálculos de las pruebas no dependan del año


@pytest.fixture
def parametros_demo() -> MotorParametros:
    """Parámetros por defecto del motor (PPT v4): 770/700/620/520, 1.6/1.4/1.0, etc."""
    return MotorParametros()


@pytest.fixture
def solicitud_empleado() -> Solicitud:
    return Solicitud(
        tipo_id=TipoIdentificacion.CC,
        numero_id="79995359",
        primer_apellido="VIDAL",
        ocupacion=Ocupacion.EMPLEADO,
        tipo_contrato=TipoContrato.INDEFINIDO,
        antiguedad_meses=36,
        fecha_nacimiento=date(1980, 5, 15),
        ingresos_mensuales=Decimal("5000000"),
        otros_ingresos=Decimal("0"),
        saldo_financiar=Decimal("10000000"),
        plazo=36,
        tasa=Decimal("2.0"),
    )


@pytest.fixture
def hdc_basico() -> RespuestaHDC:
    return RespuestaHDC(
        persona=PersonaBasica(
            nombres="JUAN",
            primer_apellido="VIDAL",
            tipo_id="1",
            numero_id="79995359",
            estado_documento="00",
        ),
        scores=[Score(tipo="67", puntaje=Decimal("800"))],
        quanto=Quanto(producto="62", valor_medio=Decimal("5000")),
        cuentas_cartera=[],
        tarjetas_credito=[],
        respuesta_codigo="13",
    )


def crear_valor_ingreso(
    ingreso: Decimal = Decimal("5000000"), continuidad: int | None = 12, numero_id: str | None = None
) -> RespuestaValorIngreso:
    return RespuestaValorIngreso(
        numero_id=numero_id,
        aportantes=[
            Aportante(
                razon_social="EMPLEADOR SA",
                tipo_cotizante=1,
                resultado_pagos=[PeriodoPago(anio=2026, mes=m, realizo_pago=True, ingresos=ingreso) for m in (7, 8, 9)],
            )
        ],
        resumen_general=ResumenGeneralIngresos(meses_continuidad=continuidad),
    )


@pytest.fixture
def vi_con_continuidad() -> RespuestaValorIngreso:
    return crear_valor_ingreso()
