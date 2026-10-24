"""
Cálculo del INGRESO FINAL (PPT v4 "Valor Ingreso & Quanto").

El ingreso declarado NO alimenta el motor: se captura en la solicitud
como dato de contacto, pero la fuente efectiva depende de la ocupación:

    Empleado / Pensionado  -> siempre VALOR_INGRESO. VI = 0 -> Rechazo.
    Fuerzas Militares      -> siempre QUANTO3_MEDIO (no tienen VI).
    Independiente          -> cotiza: VALOR_INGRESO; no cotiza: QUANTO.

Fuente aplicable = 0 -> INGRESO_FINAL = 0, Rechazo E3.

QUANTO3_MEDIO se recibe ya convertido a pesos (HDC+ lo entrega en miles).
"""

from dataclasses import dataclass
from decimal import Decimal

from backend.models.enums import Causal, Decision, Ocupacion
from backend.models.motor_models import Solicitud

FUENTE_VALOR_INGRESO = "valor_ingreso"
FUENTE_QUANTO = "quanto3_medio"
FUENTE_NINGUNA = "ninguna"


@dataclass
class ResultadoIngresoFinal:
    ingreso_final: Decimal
    fuente: str
    decision_forzada: Decision | None = None
    causal_forzada: Causal | None = None
    razon: str = ""


def _sin_fuente(razon: str) -> ResultadoIngresoFinal:
    return ResultadoIngresoFinal(
        ingreso_final=Decimal(0),
        fuente=FUENTE_NINGUNA,
        decision_forzada=Decision.RECHAZADO,
        causal_forzada=Causal.E3,
        razon=razon,
    )


def calcular_ingreso_final(
    solicitud: Solicitud,
    valor_ingreso: Decimal,
    quanto_medio_pesos: Decimal,
) -> ResultadoIngresoFinal:
    valor_ingreso = valor_ingreso or Decimal(0)
    quanto_medio_pesos = quanto_medio_pesos or Decimal(0)
    ocup = solicitud.ocupacion.value

    if solicitud.ocupacion == Ocupacion.FUERZAS_MILITARES:
        # Las FFMM no cotizan en PILA: su reporte nunca trae Valor Ingreso.
        if quanto_medio_pesos > 0:
            return ResultadoIngresoFinal(
                quanto_medio_pesos, FUENTE_QUANTO, razon=f"{ocup}: Ingreso final = Quanto 3 Medio"
            )
        return _sin_fuente(f"{ocup}: Quanto 3 Medio = 0")

    if solicitud.ocupacion == Ocupacion.INDEPENDIENTE:
        # Cotizante -> Valor Ingreso; no cotizante -> Quanto 3 Medio.
        if valor_ingreso > 0:
            return ResultadoIngresoFinal(
                valor_ingreso, FUENTE_VALOR_INGRESO, razon=f"{ocup} cotizante: Ingreso final = Valor Ingreso"
            )
        if quanto_medio_pesos > 0:
            return ResultadoIngresoFinal(
                quanto_medio_pesos,
                FUENTE_QUANTO,
                razon=f"{ocup} no cotizante: sin Valor Ingreso, Ingreso final = Quanto 3 Medio",
            )
        return _sin_fuente(f"{ocup}: sin Valor Ingreso ni Quanto 3 Medio")

    # Empleado y Pensionado: siempre Valor Ingreso.
    if valor_ingreso > 0:
        return ResultadoIngresoFinal(
            valor_ingreso, FUENTE_VALOR_INGRESO, razon=f"{ocup}: Ingreso final = Valor Ingreso"
        )
    return _sin_fuente(f"{ocup}: Valor Ingreso = 0")
