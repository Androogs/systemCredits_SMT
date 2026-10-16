"""Tests del parser de Valor Ingreso."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.integrations.datacredito.parsers.income_parser import IncomeParser

FIXTURE = Path(__file__).parent.parent / "integration" / "fixtures" / "income_response_example.json"


@pytest.fixture
def payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parse_identidad(payload):
    r = IncomeParser().parse(payload)
    assert r.tipo_id == "1"
    assert r.numero_id == "12345612"
    assert r.nombres == "NOMBRE112 NOMBRE212"
    assert r.apellidos == "APELLIDO112 APELLIDO212"
    assert r.eps == "EPSE212"


def test_parse_aportantes(payload):
    r = IncomeParser().parse(payload)
    assert len(r.aportantes) == 1
    a = r.aportantes[0]
    assert a.razon_social == "Empresa1"
    assert a.tipo_cotizante == 1
    assert a.descripcion_cotizante == "Empleado"
    assert a.ingreso_maximo == Decimal("1000000")
    assert a.ingreso_minimo == Decimal("1000000")
    assert len(a.resultado_pagos) == 5


def test_parse_pagos(payload):
    r = IncomeParser().parse(payload)
    pagos = r.aportantes[0].resultado_pagos
    assert pagos[0].anio == 2020
    assert pagos[0].mes == 6
    assert pagos[0].realizo_pago is True
    assert pagos[0].ingresos == Decimal("1000000")
    # Periodo sin pago
    assert pagos[3].realizo_pago is False
    assert pagos[3].ingresos == Decimal("0")


def test_parse_indicadores(payload):
    """Indicadores derivados de resultado_pagos, no del JSON agregado.

    El fixture reporta tiempo_sin_pago=9 e ingreso_total_ult_mes=4000000,
    pero sus pagos reales muestran 2 meses sin pago y 1M en el último mes.
    """
    r = IncomeParser().parse(payload)
    assert r.indicadores is not None
    assert r.indicadores.tiempo_sin_pago == 2
    assert r.indicadores.tiempo_total_laborado == 3
    assert r.indicadores.ingreso_total_ult_mes == Decimal("1000000")
    assert r.indicadores.total_ult_tres_meses == Decimal("1000000")
    assert r.indicadores.promedio_ult_tres_meses == Decimal("1000000")


def test_parse_resumen(payload):
    """Resumen derivado de resultado_pagos (ingreso plano -> Estable)."""
    r = IncomeParser().parse(payload)
    assert r.resumen_general is not None
    assert r.resumen_general.tendencia_ingresos == "Estable"
    assert r.resumen_general.meses_continuidad == 3
    assert r.resumen_general.cantidad_fuentes_ingreso == 1
    assert r.resumen_general.ultimo_periodo_cotizado == "06-2020"
    assert r.resumen_general.consecutivos_seis_meses == 3
    assert r.resumen_general.mediana_ingresos_cotizante == Decimal("1000000")


def test_parse_vacio():
    r = IncomeParser().parse({})
    assert r.numero_id is None
    assert r.aportantes == []
    assert r.indicadores is None
    assert r.resumen_general is None
