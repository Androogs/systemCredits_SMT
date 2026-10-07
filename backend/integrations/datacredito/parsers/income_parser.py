"""Parser de respuesta JSON de Valor Ingreso a modelos de dominio."""

from decimal import Decimal
from typing import Any

from backend.integrations.datacredito.parsers.common import _dec, _int, _str
from backend.models.buro_models import (
    Aportante,
    Indicadores,
    PeriodoPago,
    RespuestaValorIngreso,
    ResumenGeneralIngresos,
)
from backend.services.valor_ingreso_service import (
    calcular_indicadores_agregados,
    calcular_ingreso_min_max,
    obtener_ultima_empresa,
    promedio_aportante,
)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"true", "1", "si", "sí", "s"}


class IncomeParser:
    """Parsea el JSON de Valor Ingreso devuelto por el servicio REST."""

    def parse(self, payload: dict[str, Any]) -> RespuestaValorIngreso:
        # Nombre completo -> separar en nombres/apellidos si vienen separados
        nombres_partes = [
            payload.get("primer_nombre_persona_natural"),
            payload.get("segundo_nombre_persona_natural"),
        ]
        apellidos_partes = [
            payload.get("primer_apellido_persona_natural"),
            payload.get("segundo_apellido_persona_natural"),
        ]
        nombres = " ".join(p for p in nombres_partes if p) or None
        apellidos = " ".join(p for p in apellidos_partes if p) or None

        # Parse aportantes first
        aportantes = self._parse_aportantes(payload.get("aportantes") or [])

        # Determine última empresa
        ultima_empresa = obtener_ultima_empresa(aportantes)

        # Recalculate indicators from actual payment data
        indicadores_calculados = calcular_indicadores_agregados(aportantes)

        # Parse original indicators to preserve other fields
        indicadores_originales = self._parse_indicadores(payload.get("indicadores"))

        # Merge: use calculated values for averages, preserve other fields from original
        if indicadores_originales:
            indicadores_finales = Indicadores(
                tiempo_sin_pago=indicadores_originales.tiempo_sin_pago,
                tiempo_total_laborado=indicadores_originales.tiempo_total_laborado,
                promedio_ult_mes=indicadores_calculados.promedio_ult_mes,
                ingreso_total_ult_mes=indicadores_originales.ingreso_total_ult_mes,
                promedio_ult_tres_meses=indicadores_calculados.promedio_ult_tres_meses,
                total_ult_tres_meses=indicadores_calculados.total_ult_tres_meses,
                promedio_ult_doce_meses=indicadores_calculados.promedio_ult_doce_meses,
                total_ult_doce_meses=indicadores_calculados.total_ult_doce_meses,
            )
        else:
            indicadores_finales = indicadores_calculados if aportantes else None

        respuesta = RespuestaValorIngreso(
            tipo_id=_str(payload.get("tipo_identificacion_persona_natural_id")),
            numero_id=_str(payload.get("numero_identificacion_persona_natural")),
            nombres=nombres,
            apellidos=apellidos,
            eps=_str(payload.get("EPS")),
            afp=_str(payload.get("AFP")),
            respuesta_id=_int(payload.get("respuesta_id"), default=None),
            aportantes=aportantes,
            indicadores=indicadores_finales,
            resumen_general=self._parse_resumen(payload.get("resumen_general_ingresos")),
            ultima_empresa=ultima_empresa,
        )
        return respuesta

    # -----------------------------------------------------------
    def _parse_aportantes(self, items: list[Any]) -> list[Aportante]:
        out: list[Aportante] = []
        for a in items:
            if not isinstance(a, dict):
                continue
            # Parse payments first to calculate correct average
            pagos = self._parse_pagos(a.get("resultado_pagos") or [])
            # Calculate average from payment data instead of using API value
            promedio_calculado = promedio_aportante(pagos, periodos_a_considerar=3)
            # Calculate min/max from payment data instead of using API value
            ingreso_minimo, ingreso_maximo = calcular_ingreso_min_max(pagos)

            out.append(
                Aportante(
                    tipo_id=_str(a.get("tipo_identificacion_aportante_id")),
                    numero_id=_str(a.get("numero_identificacion_aportante")),
                    razon_social=_str(a.get("razon_social_aportante")),
                    tipo_cotizante=_int(a.get("tipo_cotizante_persona_natural"), default=None),
                    descripcion_cotizante=_str(a.get("descripcion_cotizante_persona_natural")),
                    ingreso_maximo=ingreso_maximo,
                    ingreso_minimo=ingreso_minimo,
                    promedio_ingresos=promedio_calculado,
                    media_ingresos=_dec(a.get("media_ingresos"), Decimal(0)) or Decimal(0),
                    tiene_salario_integral=a.get("tiene_salario_integral_actualmente"),
                    tiene_salario_fijo=a.get("tiene_salario_fijo_actualmente"),
                    tiene_salario_variable=a.get("tiene_salario_variable_actualmente"),
                    tiene_novedad_ingreso=a.get("tiene_novedad_ingreso_actualmente_empleador"),
                    tiene_novedad_retiro=a.get("tiene_novedad_retiro_actualmente_empleado"),
                    tipo_planilla=_str(a.get("tipo_planilla")),
                    actividad_aportante=_str(a.get("actividad_aportante")),
                    resultado_pagos=pagos,
                )
            )
        return out

    def _parse_pagos(self, items: list[Any]) -> list[PeriodoPago]:
        out: list[PeriodoPago] = []
        for p in items:
            if not isinstance(p, dict):
                continue
            anio = _int(p.get("ano_periodo_validado"), default=None)
            mes = _int(p.get("mes_periodo_validado"), default=None)
            if anio is None or mes is None:
                continue
            out.append(
                PeriodoPago(
                    anio=anio,
                    mes=mes,
                    realizo_pago=_bool(p.get("realizo_pago", False)),
                    ingresos=_dec(p.get("ingresos"), Decimal(0)) or Decimal(0),
                )
            )
        return out

    def _parse_indicadores(self, data: Any) -> Indicadores | None:
        if not isinstance(data, dict):
            return None
        return Indicadores(
            tiempo_sin_pago=_int(data.get("tiempo_sin_pago"), 0) or 0,
            tiempo_total_laborado=_int(data.get("tiempo_total_laborado"), 0) or 0,
            ingreso_total_ult_mes=_dec(data.get("ingreso_total_ult_mes"), Decimal(0)) or Decimal(0),
            promedio_ult_tres_meses=_dec(data.get("promedio_ult_tres_meses"), Decimal(0)) or Decimal(0),
            promedio_ult_doce_meses=_dec(data.get("promedio_ult_doce_meses"), Decimal(0)) or Decimal(0),
        )

    def _parse_resumen(self, data: Any) -> ResumenGeneralIngresos | None:
        if not isinstance(data, dict):
            return None
        return ResumenGeneralIngresos(
            promedio_ingresos_cotizante=_dec(data.get("promedio_ingresos_cotizante"), default=None),
            mediana_ingresos_cotizante=_dec(data.get("mediana_ingresos_cotizante"), default=None),
            desviacion_estandar=_dec(data.get("desviacion_estandar"), default=None),
            ingreso_minimo_cotizante=_dec(data.get("ingreso_minimo_cotizante"), default=None),
            ingreso_maximo_cotizante=_dec(data.get("ingreso_maximo_cotizante"), default=None),
            pendiente_ingresos=_dec(data.get("pendiente_ingresos"), default=None),
            tendencia_ingresos=_str(data.get("tendencia_ingresos")),
            meses_continuidad=_int(data.get("meses_continuidad"), default=None),
            cantidad_fuentes_ingreso=_int(data.get("cantidad_fuentes_ingreso"), default=None),
            ultimo_periodo_cotizado=_str(data.get("ultimo_periodo_cotizado")),
            promedio_ultimos_tres_meses_sin_dic_jun=_dec(
                data.get("promedio_ultimos_tres_meses_sin_dic_jun"), default=None
            ),
            promedio_ultimos_seis_meses_sin_dic_jun=_dec(
                data.get("promedio_ultimos_seis_meses_sin_dic_jun"), default=None
            ),
            consecutivos_seis_meses=_int(data.get("consecutivos_seis_meses"), default=None),
        )
