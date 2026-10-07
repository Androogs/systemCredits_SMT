"""Tests de calculo de Valor Ingreso (BRD 2.4.3)."""

from decimal import Decimal

from backend.services.valor_ingreso_service import calcular_valor_ingreso
from tests.modelos import Aportante, PeriodoPago, RespuestaValorIngreso


def _pago(anio: int, mes: int, ingresos: int, realizo: bool = True) -> PeriodoPago:
    return PeriodoPago(anio=anio, mes=mes, realizo_pago=realizo, ingresos=Decimal(ingresos))


def test_promedio_tres_meses_un_aportante():
    a = Aportante(
        resultado_pagos=[
            _pago(2024, 3, 3000000),
            _pago(2024, 2, 3000000),
            _pago(2024, 1, 3000000),
        ]
    )
    vi = RespuestaValorIngreso(aportantes=[a])
    assert calcular_valor_ingreso(vi) == Decimal("3000000")


def test_incluye_periodos_en_cero():
    a = Aportante(
        resultado_pagos=[
            _pago(2024, 3, 3000000),
            _pago(2024, 2, 0),
            _pago(2024, 1, 3000000),
        ]
    )
    vi = RespuestaValorIngreso(aportantes=[a])
    # Conserva los tres períodos consecutivos, incluido el mes en cero
    assert calcular_valor_ingreso(vi) == Decimal("2000000")


def test_suma_multiples_aportantes():
    # Valor Ingreso es la suma del promedio de cada aportante en sus
    # ultimos 3 meses.
    a1 = Aportante(resultado_pagos=[_pago(2024, 3, 2000000), _pago(2024, 2, 2000000)])
    a2 = Aportante(resultado_pagos=[_pago(2024, 3, 1000000), _pago(2024, 2, 1000000)])
    vi = RespuestaValorIngreso(aportantes=[a1, a2])
    assert calcular_valor_ingreso(vi) == Decimal("3000000")


def test_max_cinco_aportantes():
    # Con 10 aportantes de 1.000.000, solo se usan 5 y se suman sus promedios.
    aportantes = [Aportante(resultado_pagos=[_pago(2024, 3, 1000000)]) for _ in range(10)]
    vi = RespuestaValorIngreso(aportantes=aportantes)
    assert calcular_valor_ingreso(vi) == Decimal("5000000")


def test_sin_pagos_validos():
    a = Aportante(resultado_pagos=[_pago(2024, 3, 0, realizo=False)])
    vi = RespuestaValorIngreso(aportantes=[a])
    assert calcular_valor_ingreso(vi) == Decimal(0)
