"""Parser de respuesta JSON de Valor Ingreso a modelos de dominio."""

from decimal import Decimal
from typing import Any

from backend.integrations.datacredito.parsers.common import _dec, _int, _str
from backend.models.buro_models import (
    Aportante,
    PeriodoPago,
    RespuestaValorIngreso,
)
from backend.services.valor_ingreso_service import (
    calcular_indicadores_agregados,
    calcular_ingreso_min_max,
    calcular_resumen_general,
    mediana_ingresos,
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

        respuesta = RespuestaValorIngreso(
            tipo_id=_str(payload.get("tipo_identificacion_persona_natural_id")),
            numero_id=_str(payload.get("numero_identificacion_persona_natural")),
            nombres=nombres,
            apellidos=apellidos,
            eps=_str(payload.get("EPS")),
            afp=_str(payload.get("AFP")),
            respuesta_id=_int(payload.get("respuesta_id"), default=None),
            aportantes=aportantes,
            # Indicadores y resumen se derivan siempre de resultado_pagos;
            # los valores agregados del JSON no son confiables.
            indicadores=calcular_indicadores_agregados(aportantes) if aportantes else None,
            resumen_general=calcular_resumen_general(aportantes),
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
                    media_ingresos=mediana_ingresos(pagos),
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
