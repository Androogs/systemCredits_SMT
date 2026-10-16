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


# ---------------------------------------------------------------------------
# Línea de tiempo unificada y estadísticas derivadas de resultado_pagos
# ---------------------------------------------------------------------------
def _periodo_anterior(anio: int, mes: int) -> tuple[int, int]:
    return (anio - 1, 12) if mes == 1 else (anio, mes - 1)


def _linea_tiempo(aportantes: Sequence[Aportante]) -> dict[tuple[int, int], dict]:
    """Unifica los periodos de todos los aportantes por (anio, mes).

    Un mes cuenta como pagado si ALGÚN aportante reportó pago ese mes;
    el ingreso del mes es la suma de los ingresos pagados. Así la
    continuidad y los indicadores reflejan a la persona, no a cada
    empleador por separado.
    """
    linea: dict[tuple[int, int], dict] = {}
    for aportante in aportantes:
        for pago in aportante.resultado_pagos or []:
            nodo = linea.setdefault((pago.anio, pago.mes), {"pagado": False, "ingresos": Decimal(0)})
            if pago.realizo_pago:
                nodo["pagado"] = True
                nodo["ingresos"] += pago.ingresos or Decimal(0)
    return linea


def _continuidad_linea(linea: dict[tuple[int, int], dict]) -> int:
    """Meses calendario consecutivos pagados desde el periodo más reciente."""
    if not linea:
        return 0
    periodo = max(linea)
    continuidad = 0
    while linea.get(periodo, {}).get("pagado"):
        continuidad += 1
        periodo = _periodo_anterior(*periodo)
    return continuidad


def _mediana(valores: Sequence[Decimal]) -> Decimal | None:
    if not valores:
        return None
    ordenados = sorted(valores)
    n = len(ordenados)
    mitad = n // 2
    if n % 2:
        return ordenados[mitad]
    return (ordenados[mitad - 1] + ordenados[mitad]) / 2


def _desviacion(valores: Sequence[Decimal]) -> Decimal | None:
    """Desviación estándar poblacional de la serie."""
    if not valores:
        return None
    if len(valores) == 1:
        return Decimal(0)
    media = sum(valores) / len(valores)
    varianza = sum((v - media) ** 2 for v in valores) / len(valores)
    return varianza.sqrt()


def _pendiente_lineal(valores: Sequence[Decimal]) -> Decimal | None:
    """Pendiente de regresión lineal simple sobre la serie en orden cronológico."""
    n = len(valores)
    if n < 2:
        return None
    media_x = Decimal(n - 1) / 2
    media_y = sum(valores) / n
    numerador = sum((Decimal(i) - media_x) * (v - media_y) for i, v in enumerate(valores))
    denominador = sum((Decimal(i) - media_x) ** 2 for i in range(n))
    return numerador / denominador


def mediana_ingresos(pagos: Sequence[PeriodoPago]) -> Decimal:
    """Mediana de los ingresos pagados de un aportante."""
    ingresos = [p.ingresos for p in pagos if p.realizo_pago and p.ingresos > 0]
    return _mediana(ingresos) or Decimal(0)


def calcular_resumen_general(aportantes: Sequence[Aportante]) -> ResumenGeneralIngresos | None:
    """Deriva resumen_general_ingresos desde los resultado_pagos.

    Las estadísticas de ingreso se calculan sobre el total mensual de la
    línea de tiempo unificada (suma de aportantes por mes), solo meses
    pagados con ingreso > 0.
    """
    if not aportantes:
        return None
    linea = _linea_tiempo(aportantes)
    if not linea:
        return ResumenGeneralIngresos(cantidad_fuentes_ingreso=len(aportantes))

    periodos = sorted(linea)
    totales = [linea[k]["ingresos"] for k in periodos if linea[k]["pagado"] and linea[k]["ingresos"] > 0]
    continuidad = _continuidad_linea(linea)
    ultimo_pagado = next((k for k in reversed(periodos) if linea[k]["pagado"]), None)
    pendiente = _pendiente_lineal(totales)
    sin_dic_jun = [
        k for k in periodos if k[1] not in (6, 12) and linea[k]["pagado"] and linea[k]["ingresos"] > 0
    ]

    def _promedio(claves: list[tuple[int, int]]) -> Decimal | None:
        vals = [linea[k]["ingresos"] for k in claves]
        return sum(vals) / len(vals) if vals else None

    return ResumenGeneralIngresos(
        promedio_ingresos_cotizante=sum(totales) / len(totales) if totales else None,
        mediana_ingresos_cotizante=_mediana(totales),
        desviacion_estandar=_desviacion(totales),
        ingreso_minimo_cotizante=min(totales) if totales else None,
        ingreso_maximo_cotizante=max(totales) if totales else None,
        pendiente_ingresos=pendiente,
        tendencia_ingresos=(
            "Creciente" if pendiente > 0 else "Decreciente" if pendiente < 0 else "Estable"
        )
        if pendiente is not None
        else None,
        meses_continuidad=continuidad if continuidad > 0 else None,
        cantidad_fuentes_ingreso=len(aportantes),
        ultimo_periodo_cotizado=f"{ultimo_pagado[1]:02d}-{ultimo_pagado[0]}" if ultimo_pagado else None,
        promedio_ultimos_tres_meses_sin_dic_jun=_promedio(sin_dic_jun[-3:]),
        promedio_ultimos_seis_meses_sin_dic_jun=_promedio(sin_dic_jun[-6:]),
        consecutivos_seis_meses=min(continuidad, 6),
    )


def calcular_indicadores_agregados(
    aportantes: Sequence[Aportante],
) -> Indicadores:
    """Calcula indicadores agregados desde todos los aportantes.

    Retorna:
    - tiempo_sin_pago: meses sin pago en la línea de tiempo unificada
    - tiempo_total_laborado: meses con pago en la línea unificada
    - promedio_ult_mes: Promedio del último ingreso por aportante
    - ingreso_total_ult_mes: Ingreso total del último periodo reportado
    - promedio_ult_tres_meses: Promedio del ingreso de los últimos 3 meses por aportante
    - total_ult_tres_meses: Suma total de los promedios de 3 meses de cada aportante
    - promedio_ult_doce_meses: Promedio del ingreso de los últimos 12 meses por aportante
    - total_ult_doce_meses: Suma total de los promedios de 12 meses de cada aportante
    """
    if not aportantes:
        return Indicadores()

    linea = _linea_tiempo(aportantes)
    tiempo_laborado = sum(1 for nodo in linea.values() if nodo["pagado"])
    tiempo_sin_pago = len(linea) - tiempo_laborado
    ingreso_total_ult_mes = linea[max(linea)]["ingresos"] if linea else Decimal(0)

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
    # ingreso_total_ult_mes usa la línea unificada: suma de ingresos del
    # último periodo reportado, no el último pago de cada aportante.

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
        tiempo_sin_pago=tiempo_sin_pago,
        tiempo_total_laborado=tiempo_laborado,
        promedio_ult_mes=promedio_ult_mes,
        ingreso_total_ult_mes=ingreso_total_ult_mes,
        promedio_ult_tres_meses=promedio_3,
        total_ult_tres_meses=total_3_meses,
        promedio_ult_doce_meses=promedio_12,
        total_ult_doce_meses=total_12_meses,
    )


def calcular_meses_continuidad(pagos: list[PeriodoPago]) -> int:
    """Meses calendario consecutivos con pago desde el más reciente.

    Se detiene al primer mes sin pago o al primer hueco calendario en la
    serie (un periodo ausente rompe la continuidad).
    """
    if not pagos:
        return 0

    ordenados = _ordenar_pagos(pagos)
    esperado = (ordenados[0].anio, ordenados[0].mes)
    continuidad = 0
    for pago in ordenados:
        if (pago.anio, pago.mes) != esperado or not pago.realizo_pago:
            break
        continuidad += 1
        esperado = _periodo_anterior(*esperado)
    return continuidad


def respuesta_desde_cotizantes(
    cotizantes,
) -> RespuestaValorIngreso | None:
    if not cotizantes:
        return None

    aportantes = aportantes_desde_cotizantes(cotizantes)
    return RespuestaValorIngreso(
        aportantes=aportantes,
        indicadores=calcular_indicadores_agregados(aportantes),
        resumen_general=calcular_resumen_general(aportantes),
        ultima_empresa=obtener_ultima_empresa(aportantes),
    )
