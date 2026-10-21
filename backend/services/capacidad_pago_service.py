"""
Capacidad de pago (BRD 2.4.8, versión PPT v4). Aplica a TODOS los
casos con ingreso final > 0, sin importar la decisión previa, para que
la evaluación quede completa y trazable.

    Gasto financiero no rotativo = Σ cuotas mensuales de obligaciones
        vigentes no rotativas (cartera), propias (no codeudor), no bloqueadas.
    Gasto financiero rotativo    = Σ cuotas de cartera rotativa (TDC, CBR)
        y tarjetas de crédito.
        Cuota reportada bimensual/trimestral/... -> se lleva a mensual.
        Sin cuota reportada -> se estima con la anualidad sobre el cupo
        (cupo_total/valor_inicial) y, si no viene informado, sobre el saldo:
        rotativo a Tasa_Gasto_Financiero y Plazo_Rotativo_Default;
        no rotativo con el plazo apertura -> vencimiento.

    BASE                 = INGRESO_FINAL + OTROS_INGRESOS
    Gastos personales    = BASE × (50% si SMMLV < 1.6 ; 45% si 1.6 <= SMMLV < 2.0 ;
                                    40% si SMMLV >= 2.0)           [PPT v4]
    Endeudamiento (%)    = (rotativo + no rotativo + personales) / BASE × 100
    Disponible           = BASE − (rotativo + no rotativo + personales)
    Capacidad de pago    = Disponible × 70%
    Cupo sugerido        = valor presente de la capacidad de pago con la
                           TASA y el PLAZO de la solicitud
    Cuota sugerida       = cuota del cupo sugerido (tasa y plazo de la solicitud)
    Cuota moto           = cuota del saldo a financiar (tasa y plazo de la solicitud)

Decisiones:
    Disponible <= 0          -> Rechazo R18
    Capacidad de pago <= 0   -> Rechazo R19
    Endeudamiento > Endeu_1  -> Rechazo R17
    (si no hubo rechazo)
    Endeu_2 <= Endeudamiento -> Estudio E8
    Cuota moto > cuota sugerida -> E9, solo trazabilidad: el saldo
    evaluado es insumo de política, no una moto concreta; la oferta
    se topea por el cupo calculado con datos de centrales.

Nota: con la PPT v4 el cupo y la cuota sugerida usan la misma tasa y
plazo, por lo que cuota_sugerida = capacidad_pago por construcción; E9
equivale a "la cuota estimada supera la capacidad de pago".
"""

from dataclasses import dataclass, field
from decimal import Decimal

from backend.models.buro_models import RespuestaHDC, TarjetaCredito
from backend.models.enums import Causal, Decision
from backend.models.motor_models import Solicitud
from backend.services.finanzas import cuota_a_valor_mensual, cuota_anualidad, valor_presente_anualidad
from backend.services.motor_parametros import MotorParametros
from backend.services.reglas_filtros_duros import es_codeudor

_CIEN = Decimal(100)

# Estados de pago que indican obligación vigente (no cerrada), Tabla 4 HDC+.
ESTADOS_VIGENTES_CARTERA = {
    "0",
    "00",
    "01",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "31",
    "32",
    "33",
    "34",
    "35",
    "36",
    "37",
    "38",
    "39",
    "40",
    "41",
    "45",
    "47",
    "60",
}

# Códigos/textos que indican que la obligación ya no está abierta. HDC+
# puede informar el código de pago actual como "01" aunque el estado de
# origen indique que la obligación fue pagada o cancelada.
# Estado de pago HDC+ 03 = Pago total/cierre de la obligación.
ESTADOS_CERRADOS_CARTERA = {"03"}
# Evento HDC+ de tarjetas 05 = Cancelación/cierre de la tarjeta.
EVENTOS_CIERRE_TARJETA = {"05"}
MARCADORES_ESTADO_CERRADO = (
    "PAGO TOTAL",
    "PAGO VOL",
    "PAGO VOLUNT",
    "PAGÓ VOL",
    "PAGO OBLIGACIÓN",
    "CANCELAD",
    "CERRAD",
    "INACTIV",
    "TERMINAD",
    "FINALIZ",
    "CLOSED",
    "INACTIVE",
    "CANCELLED",
    "SETTLED",
)
# Tipos de cuenta rotativos (carteras 2 y 3). HDC+ puede enviar el
# código numérico, la sigla normalizada o la descripción.
TIPOS_ROTATIVOS = {
    "2",
    "3",
    "TDC",
    "CBR",
    "TARJETA DE CREDITO",
    "TARJETA DE CRÉDITO",
    "CARTERA BANCARIA ROTATIVA",
}


@dataclass
class ResultadoCapacidadPago:
    gastos_financieros_no_rotativos: Decimal = Decimal(0)
    gasto_financiero_rotativo: Decimal = Decimal(0)
    gastos_personales: Decimal = Decimal(0)
    endeudamiento: Decimal = Decimal(0)
    disponible: Decimal = Decimal(0)
    capacidad_pago: Decimal = Decimal(0)
    cupo_sugerido: Decimal = Decimal(0)
    cuota_sugerida: Decimal = Decimal(0)
    cuota_moto: Decimal = Decimal(0)
    causales: list[Causal] = field(default_factory=list)
    # E9 reporta pero no decide: el saldo evaluado es insumo de política
    # (el cliente aún no elige moto); la oferta se topea por el cupo real.
    causales_traza: list[Causal] = field(default_factory=list)
    detalles: list[str] = field(default_factory=list)

    @property
    def decision_forzada(self) -> Decision | None:
        if any(c.tipo == Decision.RECHAZADO for c in self.causales):
            return Decision.RECHAZADO
        if self.causales:
            return Decision.ESTUDIO
        return None


def _cuota_mensual_obligacion(cuenta, es_rotativo: bool, params: MotorParametros) -> Decimal:
    cuota = cuenta.cuota or Decimal(0)
    if cuota > 0:
        return cuota_a_valor_mensual(cuota, cuenta.forma_pago)

    # BRD: si la cuota reportada es cero/no existe, el rotativo se calcula
    # sobre el cupo. En HDC+ el cupo de una tarjeta llega como ``cupo_total``
    # y el de una cartera rotativa como ``valor_inicial``. Algunos reportes
    # no traen ese campo; en ese caso conservamos ``saldo_actual`` como
    # respaldo para no perder la obligación.
    if es_rotativo:
        cupo = getattr(cuenta, "cupo_total", Decimal(0)) or Decimal(0)
        if cupo <= 0:
            cupo = getattr(cuenta, "valor_inicial", Decimal(0)) or Decimal(0)
        monto = cupo if cupo > 0 else (cuenta.saldo_actual or Decimal(0))
    else:
        monto = cuenta.saldo_actual or Decimal(0)

    if monto <= 0:
        return Decimal(0)
    if es_rotativo:
        return cuota_anualidad(monto, params.tasa_gasto_financiero_pct, params.plazo_rotativo_default_meses)
    if cuenta.fecha_apertura and cuenta.fecha_vencimiento:
        plazo = max(1, (cuenta.fecha_vencimiento - cuenta.fecha_apertura).days // 30)
        return cuota_anualidad(monto, params.tasa_gasto_financiero_pct, plazo)
    return Decimal(0)


def clasificar_obligacion(cuenta) -> tuple[str, str]:
    """Devuelve la condición operativa y el motivo usado en capacidad de pago."""
    if cuenta.bloqueada:
        return "Excluida", "Obligación bloqueada por HDC+"

    codigo_pago = str(cuenta.estado_pago or "").strip().upper()
    codigo_origen = str(getattr(cuenta, "estado_origen", "") or "").strip().upper()
    evento_buro = str(getattr(cuenta, "evento_buro", "") or "").strip().upper()
    if codigo_pago.isdigit() and len(codigo_pago) == 1:
        codigo_pago = codigo_pago.zfill(2)
    if codigo_origen.isdigit() and len(codigo_origen) == 1:
        codigo_origen = codigo_origen.zfill(2)
    if codigo_pago in ESTADOS_CERRADOS_CARTERA:
        return "Cerrada", f"Estado de pago {codigo_pago}"
    if codigo_origen in ESTADOS_CERRADOS_CARTERA:
        return "Cerrada", f"Estado de origen {codigo_origen}"
    if isinstance(cuenta, TarjetaCredito) and evento_buro in EVENTOS_CIERRE_TARJETA:
        return "Cerrada", f"Evento de cierre de tarjeta {evento_buro}"

    textos = (
        str(cuenta.estado_cuenta or ""),
        str(getattr(cuenta, "estado_cuenta_desc", "") or ""),
        str(getattr(cuenta, "estado_origen_desc", "") or ""),
    )
    texto_estado = " ".join(textos).upper()
    marcador = next((valor for valor in MARCADORES_ESTADO_CERRADO if valor in texto_estado), None)
    if marcador:
        return "Cerrada", f"Descripción de cierre: {marcador}"
    if codigo_pago in ESTADOS_VIGENTES_CARTERA:
        return "Abierta", f"Estado de pago vigente {codigo_pago}"
    if not codigo_pago:
        return "Excluida", "Sin estado de pago para validar vigencia"
    return "Excluida", f"Estado de pago no reconocido como vigente: {codigo_pago}"


def rol_deudor(cuenta) -> str:
    calidad = str(getattr(cuenta, "calidad_deudor", "") or "").strip().upper()
    if es_codeudor(cuenta):
        return "Codeudor"
    if calidad in {"0", "00"} or "PRINCIPAL" in calidad:
        return "Principal"
    if not calidad:
        return "No reportado"
    return "Otro"


def inclusion_gasto_financiero(cuenta) -> tuple[bool, str]:
    condicion, motivo_condicion = clasificar_obligacion(cuenta)
    if es_codeudor(cuenta):
        return False, "La persona figura como codeudora"
    if condicion != "Abierta":
        return False, motivo_condicion
    return True, "Obligación propia abierta/vigente"


def calcular_gastos_financieros(hdc: RespuestaHDC, params: MotorParametros) -> tuple[Decimal, Decimal]:
    """Devuelve (no_rotativos, rotativos) en pesos mensuales."""
    no_rotativos = Decimal(0)
    rotativos = Decimal(0)

    for c in hdc.cuentas_cartera:
        if not inclusion_gasto_financiero(c)[0]:
            continue
        tipo_cuenta = (c.tipo_cuenta or "").strip().upper()
        es_rotativo = tipo_cuenta in TIPOS_ROTATIVOS
        cuota = _cuota_mensual_obligacion(c, es_rotativo, params)
        if es_rotativo:
            rotativos += cuota
        else:
            no_rotativos += cuota

    for t in hdc.tarjetas_credito:
        if not inclusion_gasto_financiero(t)[0]:
            continue
        rotativos += _cuota_mensual_obligacion(t, True, params)

    return no_rotativos, rotativos


def calcular_gastos_personales(
    ingreso_final: Decimal,
    otros_ingresos: Decimal,
    ingreso_final_smmlv: Decimal,
    params: MotorParametros,
    fuente_ingreso: str = "",
) -> Decimal:
    # PPT v4 p.10: Cuando se toma Quanto 3 Medio -> 50% fijo
    if fuente_ingreso == "quanto3_medio":
        pct = params.gastos_personales_pct_quanto
    elif ingreso_final_smmlv < params.gastos_personales_umbral_medio:
        pct = params.gastos_personales_pct_bajo
    elif ingreso_final_smmlv < params.gastos_personales_umbral_alto:
        pct = params.gastos_personales_pct_medio
    else:
        pct = params.gastos_personales_pct_alto
    return (ingreso_final + otros_ingresos) * pct / _CIEN


def calcular_capacidad_pago(
    hdc: RespuestaHDC,
    solicitud: Solicitud,
    params: MotorParametros,
    ingreso_final: Decimal,
    ingreso_final_smmlv: Decimal,
    fuente_ingreso: str = "",
) -> ResultadoCapacidadPago:
    otros = solicitud.otros_ingresos or Decimal(0)
    base = ingreso_final + otros

    no_rot, rot = calcular_gastos_financieros(hdc, params)
    personales = calcular_gastos_personales(ingreso_final, otros, ingreso_final_smmlv, params, fuente_ingreso)
    gastos_totales = no_rot + rot + personales

    endeudamiento = gastos_totales / base * _CIEN if base > 0 else Decimal(0)
    disponible = base - gastos_totales
    capacidad = disponible * params.capacidad_pago_pct / _CIEN if disponible > 0 else Decimal(0)

    # BRD p.19: Cupo sugerido con Tasa = 2%, Plazo = 24 meses
    # PPT v4 p.11: Plazo = 48 meses
    # Se usa la definición aprobada y parametrizable para campañas
    # Límite máximo de cupo parametrizable en COP
    tasa_cupo = params.cupo_sugerido_tasa_pct
    plazo_cupo = params.cupo_sugerido_plazo_meses
    cupo = valor_presente_anualidad(capacidad, tasa_cupo, plazo_cupo)
    cuota_sugerida = cuota_anualidad(cupo, tasa_cupo, plazo_cupo)

    # Aplicar límite máximo configurado
    cupo_maximo = params.cupo_sugerido_tope
    if cupo > cupo_maximo:
        cupo = cupo_maximo
        cuota_sugerida = cuota_anualidad(cupo, tasa_cupo, plazo_cupo)

    # Cuota moto usa tasa y plazo de la solicitud
    tasa_solicitud = solicitud.tasa or Decimal(0)
    plazo_solicitud = solicitud.plazo or 0
    cuota_moto = cuota_anualidad(solicitud.saldo_financiar or Decimal(0), tasa_solicitud, plazo_solicitud)

    r = ResultadoCapacidadPago(
        gastos_financieros_no_rotativos=no_rot,
        gasto_financiero_rotativo=rot,
        gastos_personales=personales,
        endeudamiento=endeudamiento,
        disponible=disponible,
        capacidad_pago=capacidad,
        cupo_sugerido=cupo,
        cuota_sugerida=cuota_sugerida,
        cuota_moto=cuota_moto,
    )

    if disponible <= 0:
        r.causales.append(Causal.R18)
        r.detalles.append(f"Disponible {disponible:.0f} <= 0")
    if capacidad <= 0:
        r.causales.append(Causal.R19)
        r.detalles.append("Sin capacidad de pago")

    # BRD p.18: Endeudamiento >= 86 <= 90 -> RECHAZO (R17)
    # Endeudamiento > 90 -> RECHAZO (R17)
    if endeudamiento > params.endeu_1:
        r.causales.append(Causal.R17)
        r.detalles.append(f"Endeudamiento {endeudamiento:.2f}% > {params.endeu_1}%")
    elif params.endeu_2 <= endeudamiento <= params.endeu_1:
        r.causales.append(Causal.R17)
        r.detalles.append(f"Endeudamiento moderado {endeudamiento:.2f}% entre {params.endeu_2}% y {params.endeu_1}%")

    if not r.causales:
        if cuota_sugerida > 0 and cuota_moto > cuota_sugerida:
            r.causales_traza.append(Causal.E9)
            r.detalles.append(f"Cuota moto {cuota_moto:.0f} > cuota sugerida {cuota_sugerida:.0f}")

    return r
