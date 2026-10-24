"""
Reportes de buró FICTICIOS para el ambiente demo (sin credenciales de
Experian). Nunca se usan en ambiente "produccion".

Cada escenario devuelve (RespuestaHDC, RespuestaValorIngreso | None)
construidos para disparar una regla concreta con los parámetros por
defecto. Los vectores de comportamiento ponen el evento en el mes más
reciente (posición 0), igual que asume el motor.
"""

from decimal import Decimal

from backend.models.buro_models import (
    Aportante,
    CuentaAhorro,
    CuentaCartera,
    PeriodoPago,
    PersonaBasica,
    Quanto,
    RespuestaHDC,
    RespuestaValorIngreso,
    ResumenGeneralIngresos,
    Score,
)
from backend.models.enums import TipoIdentificacion

ESCENARIOS: dict[str, str] = {
    "aprobado": "Cliente sano: score 800, ingreso 5.000.000 con continuidad de 12 meses.",
    "score_bajo": "Score 300: por debajo del punto de corte (R14).",
    "sin_experiencia": "Score 100: cliente sin experiencia crediticia (R23).",
    "fallecido": "Score 3 y documento cancelado por muerte (R1, R12).",
    "exclusion_score": "Score 0: exclusión de score (E7 o RC3 según ingreso).",
    "mora_90": "Mora de 90 días en el mes más reciente y calificación C (R6, R8, R9, R10).",
    "embargo": "Cuenta de ahorros embargada (R2).",
    "castigada": "Cartera castigada (R4).",
    "mora_30": "Mora de 30 días vigente (E2).",
    "perfil_bajo": "Ingreso de 1,2 SMMLV con continuidad: perfil BAJO (E4).",
    "sin_valor_ingreso": "Empleado sin Valor Ingreso: no hay fuente de ingreso -> rechazo E3.",
    "endeudamiento_alto": "Obligaciones que llevan el endeudamiento a 86% (R17).",
    # No llega al buró: el pre-filtro SIMIT rechaza (R22) antes de
    # construir este reporte. Si el pre-filtro está deshabilitado, el
    # escenario se comporta como 'aprobado'.
    "simit_multas": "Deuda pendiente en SIMIT: rechazo R22 sin consultar el buró.",
}

_PERIODOS = [(2026, 8), (2026, 7), (2026, 6)]


def _valor_ingreso(tipo_id: str, numero_id: str, ingreso: Decimal, continuidad: int = 12) -> RespuestaValorIngreso:
    return RespuestaValorIngreso(
        tipo_id=tipo_id,
        numero_id=numero_id,
        aportantes=[
            Aportante(
                razon_social="EMPLEADOR FICTICIO S.A.S.",
                tipo_cotizante=1,
                descripcion_cotizante="Dependiente",
                resultado_pagos=[PeriodoPago(anio=a, mes=m, realizo_pago=True, ingresos=ingreso) for a, m in _PERIODOS],
            )
        ],
        resumen_general=ResumenGeneralIngresos(meses_continuidad=continuidad),
    )


def _cartera(**kw) -> CuentaCartera:
    base = dict(
        entidad="BANCO FICTICIO",
        numero="000000",
        tipo_cuenta="CAB",
        calificacion="A",
        estado_pago="01",
        saldo_actual=Decimal("2000000"),
        saldo_mora=Decimal("0"),
        cuota=Decimal("100000"),
        comportamiento="N" * 48,
        sector="1",
        calidad_deudor="00",
    )
    base.update(kw)
    return CuentaCartera(**base)


def crear_escenario(
    escenario: str,
    tipo_id: TipoIdentificacion,
    numero_id: str,
    primer_apellido: str,
    smmlv: int,
) -> tuple[RespuestaHDC, RespuestaValorIngreso | None]:
    if escenario not in ESCENARIOS:
        raise ValueError(f"Escenario mock desconocido: '{escenario}'. Opciones: {sorted(ESCENARIOS)}")

    persona = PersonaBasica(
        nombres="CLIENTE FICTICIO",
        primer_apellido=primer_apellido.upper(),
        tipo_id=tipo_id.value,
        numero_id=numero_id,
        estado_documento="00",
    )
    score = Decimal("800")
    quanto = Quanto(producto="62", valor_medio=Decimal("5000"))  # miles de pesos
    cuentas_cartera: list[CuentaCartera] = []
    cuentas_ahorro: list[CuentaAhorro] = []
    vi: RespuestaValorIngreso | None = _valor_ingreso(tipo_id.value, numero_id, Decimal("5000000"))

    if escenario == "score_bajo":
        score = Decimal("300")
    elif escenario == "sin_experiencia":
        score = Decimal("100")
    elif escenario == "fallecido":
        score = Decimal("3")
        persona.estado_documento = "21"
    elif escenario == "exclusion_score":
        score = Decimal("0")
    elif escenario == "mora_90":
        cuentas_cartera = [
            _cartera(calificacion="C", estado_pago="19", comportamiento="3" + "N" * 47, saldo_mora=Decimal("500000"))
        ]
    elif escenario == "embargo":
        cuentas_ahorro = [CuentaAhorro(entidad="BANCO FICTICIO", numero="111", estado="06")]
    elif escenario == "castigada":
        cuentas_cartera = [_cartera(estado_pago="45", comportamiento="C" + "N" * 47, saldo_mora=Decimal("1000000"))]
    elif escenario == "mora_30":
        cuentas_cartera = [_cartera(estado_pago="17", comportamiento="1" + "N" * 47, saldo_mora=Decimal("100000"))]
    elif escenario == "perfil_bajo":
        vi = _valor_ingreso(tipo_id.value, numero_id, (Decimal(smmlv) * Decimal("1.2")).quantize(Decimal(1)))
    elif escenario == "sin_valor_ingreso":
        vi = None
    elif escenario == "endeudamiento_alto":
        cuentas_cartera = [_cartera(numero=f"99{i}", cuota=Decimal("460000")) for i in range(5)]

    hdc = RespuestaHDC(
        persona=persona,
        scores=[Score(tipo="67", puntaje=score)],
        quanto=quanto,
        cuentas_cartera=cuentas_cartera,
        cuentas_ahorro=cuentas_ahorro,
        respuesta_codigo="13",
        respuesta_desc="Escenario ficticio (demo)",
    )
    return hdc, vi
