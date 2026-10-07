from collections.abc import Sequence
from decimal import Decimal

from backend.models.buro_models import (
    Aportante,
    Indicadores,
    PeriodoPago,
    RespuestaValorIngreso,
    ResumenGeneralIngresos,
)


def _ordenar_pagos(pagos: Sequence[PeriodoPago]) -> list[PeriodoPago]:
    """Ordena los pagos del más reciente al más antiguo."""
    return sorted(pagos, key=lambda pago: (pago.anio, pago.mes), reverse=True)


def promedio_aportante(
    pagos: Sequence[PeriodoPago],
    periodos_a_considerar: int = 3,
) -> Decimal:
    if periodos_a_considerar <= 0:
        raise ValueError("periodos_a_considerar debe ser mayor que 0")

    # Tomar los periodos más recientes consecutivos tal como vienen en el reporte
    # incluyendo ceros (BRD: "no se deben tomar los reportes con valor cero" se refiere
    # a no omitir periodos, no a excluirlos del promedio)
    ultimos_periodos = _ordenar_pagos(pagos)[:periodos_a_considerar]

    if not ultimos_periodos:
        return Decimal(0)

    return sum((pago.ingresos for pago in ultimos_periodos), Decimal(0)) / Decimal(len(ultimos_periodos))


def calcular_ingreso_min_max(pagos: list[PeriodoPago]) -> tuple[Decimal, Decimal]:
    """Calcula el ingreso mínimo y máximo desde los pagos reales del aportante.

    Retorna (ingreso_minimo, ingreso_maximo).
    Si no hay pagos con ingreso > 0, retorna (0, 0).
    """
    if not pagos:
        return Decimal(0), Decimal(0)

    # Filtrar solo pagos con ingreso
    ingresos = [pago.ingresos for pago in pagos if pago.ingresos > 0]

    if not ingresos:
        return Decimal(0), Decimal(0)

    return min(ingresos), max(ingresos)


def calcular_valor_ingreso_aportantes(
    aportantes: Sequence[Aportante],
    max_aportantes: int = 5,
    periodos_a_considerar: int = 3,
) -> Decimal:
    if max_aportantes <= 0:
        raise ValueError("max_aportantes debe ser mayor que 0")

    if periodos_a_considerar <= 0:
        raise ValueError("periodos_a_considerar debe ser mayor que 0")

    return sum(
        (
            promedio_aportante(
                aportante.resultado_pagos,
                periodos_a_considerar,
            )
            for aportante in aportantes[:max_aportantes]
        ),
        Decimal(0),
    )


def calcular_valor_ingreso(
    vi: RespuestaValorIngreso | None,
    max_aportantes: int = 5,
    periodos_a_considerar: int = 3,
) -> Decimal:
    """Devuelve la suma del promedio de los últimos N meses de cada aportante.

    BRD/PPT v4 / Experian: Valor Ingreso es la suma de los promedios
    recientes de cada aportante, no un promedio global ni un promedio de
    promedios. Esto evita rechazos injustificados cuando solo algunos
    aportantes tienen pagos en el periodo.
    """
    if not vi or not vi.aportantes:
        return Decimal(0)

    return calcular_valor_ingreso_aportantes(
        vi.aportantes,
        max_aportantes=max_aportantes,
        periodos_a_considerar=periodos_a_considerar,
    )


def aportantes_desde_cotizantes(cotizantes) -> list[Aportante]:
    aportantes = []

    for cotizante in cotizantes:
        pagos = []

        for ingreso_mensual in cotizante.ingresos_mensuales:
            ingreso = Decimal(ingreso_mensual.ingreso or 0)

            pagos.append(
                PeriodoPago(
                    anio=ingreso_mensual.periodo.year,
                    mes=ingreso_mensual.periodo.month,
                    realizo_pago=ingreso > 0,
                    ingresos=ingreso,
                )
            )

        aportantes.append(
            Aportante(
                razon_social=cotizante.razon_social_aportante,
                resultado_pagos=pagos,
            )
        )

    return aportantes


def obtener_ultima_empresa(aportantes: Sequence[Aportante]) -> str | None:
    """Determina la última empresa en la que trabajó o está trabajando la persona.

    Retorna la razón social del aportante con el pago más reciente.
    """
    if not aportantes:
        return None

    ultima_empresa = None
    fecha_mas_reciente = None

    for aportante in aportantes:
        if aportante.resultado_pagos:
            pagos_ordenados = _ordenar_pagos(aportante.resultado_pagos)
            if pagos_ordenados:
                pago_mas_reciente = pagos_ordenados[0]
                fecha_pago = (pago_mas_reciente.anio, pago_mas_reciente.mes)

                if fecha_mas_reciente is None or fecha_pago > fecha_mas_reciente:
                    fecha_mas_reciente = fecha_pago
                    ultima_empresa = aportante.razon_social

    return ultima_empresa


def calcular_indicadores_agregados(
    aportantes: Sequence[Aportante],
) -> Indicadores:
    """Calcula indicadores agregados desde todos los aportantes.

    Retorna:
    - promedio_ult_mes: Promedio del último ingreso por aportante
    - ingreso_total_ult_mes: Suma total del último ingreso de todos los aportantes
    - promedio_ult_tres_meses: Promedio del ingreso de los últimos 3 meses por aportante
    - total_ult_tres_meses: Suma total de los promedios de 3 meses de cada aportante
    - promedio_ult_doce_meses: Promedio del ingreso de los últimos 12 meses por aportante
    - total_ult_doce_meses: Suma total de los promedios de 12 meses de cada aportante
    """
    if not aportantes:
        return Indicadores()

    def promedio_ultimos_n(pagos: Sequence[PeriodoPago], n: int) -> Decimal | None:
        recientes = _ordenar_pagos(pagos)[:n]
        if not recientes:
            return None
        return sum(pago.ingresos for pago in recientes) / Decimal(len(recientes))

    # Calcular ingreso del último mes por aportante
    ingresos_ult_mes_por_aportante = []
    for aportante in aportantes:
        if aportante.resultado_pagos:
            pagos_ordenados = _ordenar_pagos(aportante.resultado_pagos)
            if pagos_ordenados and pagos_ordenados[0].realizo_pago:
                ingresos_ult_mes_por_aportante.append(pagos_ordenados[0].ingresos)

    ingreso_ult_mes_total = sum(ingresos_ult_mes_por_aportante, Decimal(0))
    promedio_ult_mes = (
        ingreso_ult_mes_total / len(ingresos_ult_mes_por_aportante) if ingresos_ult_mes_por_aportante else Decimal(0)
    )

    # Calcular promedios de 3 y 12 meses por aportante
    promedios_3_meses_por_aportante = [
        promedio
        for aportante in aportantes
        if (promedio := promedio_ultimos_n(aportante.resultado_pagos, 3)) is not None
    ]
    promedios_12_meses_por_aportante = [
        promedio
        for aportante in aportantes
        if (promedio := promedio_ultimos_n(aportante.resultado_pagos, 12)) is not None
    ]

    total_3_meses = sum(promedios_3_meses_por_aportante, Decimal(0))
    promedio_3 = total_3_meses / len(promedios_3_meses_por_aportante) if promedios_3_meses_por_aportante else Decimal(0)
    total_12_meses = sum(promedios_12_meses_por_aportante, Decimal(0))
    promedio_12 = (
        total_12_meses / len(promedios_12_meses_por_aportante) if promedios_12_meses_por_aportante else Decimal(0)
    )

    return Indicadores(
        promedio_ult_mes=promedio_ult_mes,
        ingreso_total_ult_mes=ingreso_ult_mes_total,
        promedio_ult_tres_meses=promedio_3,
        total_ult_tres_meses=total_3_meses,
        promedio_ult_doce_meses=promedio_12,
        total_ult_doce_meses=total_12_meses,
    )


def respuesta_desde_cotizantes(
    cotizantes,
) -> RespuestaValorIngreso | None:
    if not cotizantes:
        return None

    continuidades = [cotizante.meses_continuidad for cotizante in cotizantes if cotizante.meses_continuidad is not None]

    return RespuestaValorIngreso(
        aportantes=aportantes_desde_cotizantes(cotizantes),
        resumen_general=ResumenGeneralIngresos(
            meses_continuidad=max(continuidades) if continuidades else None,
        ),
    )
