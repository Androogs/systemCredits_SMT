"""Cantidades en letras para los documentos de legalización.

El formato sigue el de los pagarés reales de Inversiones Pacífico:
"DOCE MILLONES SETECIENTOS OCHENTA Y UNO MIL SEISCIENTOS SESENTA Y
CINCO PESOS M/CTE".
"""

from decimal import Decimal

from num2words import num2words


def numero_a_letras(valor: int | float | Decimal, sufijo: str = "PESOS M/CTE") -> str:
    """'12781665' → 'DOCE MILLONES SETECIENTOS OCHENTA Y UNO MIL
    SEISCIENTOS SESENTA Y CINCO PESOS M/CTE'."""
    entero = int(Decimal(str(valor)).quantize(Decimal("1")))
    return f"{num2words(entero, lang='es').upper()} {sufijo}".strip()
