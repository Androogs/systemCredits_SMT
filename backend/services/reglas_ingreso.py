"""
Cálculo del INGRESO FINAL (PPT v4 + BRD).

Precedencia aprobada para todas las ocupaciones:
    1. VALOR_INGRESO > 0 -> Valor Ingreso.
    2. QUANTO3_MEDIO > 0 -> Quanto 3 Medio.
    3. INGRESOS_MENSUALES > 0 -> ingreso declarado.
    4. Sin ninguna fuente -> INGRESO_FINAL = 0, Estudio E3.

QUANTO3_MEDIO se recibe ya convertido a pesos (HDC+ lo entrega en miles).
"""

from dataclasses import dataclass
from decimal import Decimal

from backend.models.enums import Causal, Decision
from backend.models.motor_models import Solicitud

FUENTE_VALOR_INGRESO = "valor_ingreso"
FUENTE_QUANTO = "quanto3_medio"
FUENTE_DECLARADO = "ingresos_declarados"
FUENTE_NINGUNA = "ninguna"


@dataclass
class ResultadoIngresoFinal:
    ingreso_final: Decimal
    fuente: str
    decision_forzada: Decision | None = None
    causal_forzada: Causal | None = None
    razon: str = ""


def calcular_ingreso_final(
    solicitud: Solicitud,
    valor_ingreso: Decimal,
    quanto_medio_pesos: Decimal,
) -> ResultadoIngresoFinal:
    declarados = solicitud.ingresos_mensuales or Decimal(0)
    valor_ingreso = valor_ingreso or Decimal(0)
    quanto_medio_pesos = quanto_medio_pesos or Decimal(0)

    # Caso 1: Valor Ingreso verificado
    if valor_ingreso > 0:
        return ResultadoIngresoFinal(
            valor_ingreso,
            FUENTE_VALOR_INGRESO,
            razon=f"{solicitud.ocupacion.value}: Ingreso final = Valor Ingreso",
        )

    # Caso 2: Quanto como respaldo
    if quanto_medio_pesos > 0:
        return ResultadoIngresoFinal(
            quanto_medio_pesos,
            FUENTE_QUANTO,
            razon=f"{solicitud.ocupacion.value}: Sin Valor Ingreso; ingreso final = Quanto 3 Medio",
        )

    # Caso 3: Ingreso declarado como último recurso
    if declarados > 0:
        return ResultadoIngresoFinal(
            declarados,
            FUENTE_DECLARADO,
            razon=f"{solicitud.ocupacion.value}: Sin Valor Ingreso ni Quanto; ingreso final = declarado",
        )

    # Caso 4: Sin ninguna fuente de ingreso
    return ResultadoIngresoFinal(
        ingreso_final=Decimal(0),
        fuente=FUENTE_NINGUNA,
        decision_forzada=Decision.RECHAZADO,
        causal_forzada=Causal.E3,
        razon="Sin valor ingreso, sin Quanto y sin ingresos declarados",
    )
