"""
Funciones financieras puras (Decimal) usadas por el motor.

IMPORTANTE — bug encontrado en el archivo de referencia
'Ejemplo Calculo cuotas 1.xlsx': la fórmula ahí escrita es

    = (Cupo * Tasa) / 1 - (1 / (1 + Tasa) ** Plazo)

que por precedencia de operadores en Excel "divide entre 1" y LUEGO
resta, en vez de dividir por el paréntesis completo. Para un cupo de
1.000, tasa 2%, plazo 36: esa fórmula da 19.5; el valor correcto de la
cuota (anualidad francesa estándar) es 39.23. Usada como referencia,
subestima el gasto financiero entre 25% y 50% e infla la capacidad de
pago.

Este módulo implementa la fórmula correcta:

    cuota          = monto * i / (1 - (1 + i) ** -n)
    valor_presente = cuota * (1 - (1 + i) ** -n) / i

donde i es la tasa periódica en decimal (2% -> 0.02) y n el número de
periodos. Montos o plazos no positivos devuelven 0 (no hay cuota que
calcular), para que el motor pueda seguir y reportar la causal que
corresponda en vez de romperse.
"""

from decimal import Decimal

_CIEN = Decimal(100)
_UNO = Decimal(1)


def _tasa_decimal(tasa_pct: Decimal) -> Decimal:
    return Decimal(tasa_pct) / _CIEN


def cuota_anualidad(monto: Decimal, tasa_pct: Decimal, plazo_meses: int) -> Decimal:
    """Cuota mensual fija. tasa_pct: tasa mensual en porcentaje (2.0 = 2%)."""
    monto = Decimal(monto)
    if plazo_meses <= 0 or monto <= 0:
        return Decimal(0)
    i = _tasa_decimal(tasa_pct)
    if i <= 0:
        return monto / Decimal(plazo_meses)
    return monto * i / (_UNO - (_UNO + i) ** -plazo_meses)


def valor_presente_anualidad(cuota: Decimal, tasa_pct: Decimal, plazo_meses: int) -> Decimal:
    """
    Monto máximo financiable con una cuota dada (inversa de
    cuota_anualidad): dado lo que la capacidad de pago cubre al mes,
    calcula el cupo.
    """
    cuota = Decimal(cuota)
    if plazo_meses <= 0 or cuota <= 0:
        return Decimal(0)
    i = _tasa_decimal(tasa_pct)
    if i <= 0:
        return cuota * Decimal(plazo_meses)
    return cuota * (_UNO - (_UNO + i) ** -plazo_meses) / i


# Tabla 7 - Modalidad de pago (manual HDC+). Se aceptan el texto
# descriptivo y variantes en mayúsculas/minúsculas.
_MESES_POR_PERIODICIDAD = {
    "mensual": 1,
    "bimensual": 2,
    "trimestral": 3,
    "semestral": 6,
    "anual": 12,
}


def meses_por_periodicidad(periodicidad: str | None) -> int:
    """Meses que cubre una cuota según su periodicidad (desconocida o vacía -> 1)."""
    if not periodicidad:
        return 1
    return _MESES_POR_PERIODICIDAD.get(periodicidad.strip().lower(), 1)


def cuota_a_valor_mensual(cuota: Decimal, periodicidad: str | None) -> Decimal:
    """Convierte una cuota bimensual/trimestral/semestral/anual a su equivalente mensual."""
    return Decimal(cuota) / Decimal(meses_por_periodicidad(periodicidad))
