"""
Modelos del motor de decisión: entrada (Solicitud), salida
(ResultadoMotor) y DTOs de la API /motor.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.models.buro_models import RespuestaHDC, RespuestaValorIngreso
from backend.models.enums import (
    Causal,
    Decision,
    DecisionFinal,
    Ocupacion,
    PerfilIngreso,
    PerfilScore,
    TipoContrato,
    TipoIdentificacion,
)


# ---------------------------------------------------------------------------
# Entrada del motor
# ---------------------------------------------------------------------------
class Solicitud(BaseModel):
    """Formulario de entrada del motor (BRD 2.1)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    tipo_id: TipoIdentificacion
    numero_id: str = Field(min_length=1, max_length=20)
    primer_apellido: str = Field(min_length=1, max_length=60)

    ocupacion: Ocupacion
    tipo_contrato: TipoContrato | None = None
    # Informativa: la PPT v4 ya no usa la antigüedad declarada; la
    # continuidad se mide con Valor Ingreso (meses_continuidad).
    antiguedad_meses: int | None = Field(default=None, ge=0)
    anios_camara_comercio: Decimal | None = Field(default=None, ge=0)
    fecha_nacimiento: date

    # Políticas del BRD (edad/nacionalidad/RUNT). RUNT no tiene
    # integración: se recibe como dato de la solicitud.
    nacionalidad: str = "Colombia"
    tiene_multas_runt: bool = False

    ingresos_mensuales: Decimal = Field(default=Decimal(0), ge=0)
    otros_ingresos: Decimal = Field(default=Decimal(0), ge=0)
    saldo_financiar: Decimal = Field(default=Decimal(0), ge=0)
    plazo: int = Field(default=0, ge=0)
    tasa: Decimal = Field(default=Decimal(0), ge=0)  # tasa MENSUAL en %


# ---------------------------------------------------------------------------
# Salida del motor
# ---------------------------------------------------------------------------
class CausalDetalle(BaseModel):
    codigo: str
    descripcion: str
    tipo: Decision
    cantidad: int = 1

    @classmethod
    def desde(cls, causal: Causal, cantidad: int = 1) -> "CausalDetalle":
        return cls(codigo=causal.codigo, descripcion=causal.value, tipo=causal.tipo, cantidad=cantidad)


class PasoTraza(BaseModel):
    """Una etapa evaluada por el motor, para auditoría."""

    etapa: str
    resultado: str
    causales: list[str] = Field(default_factory=list)
    detalle: list[str] = Field(default_factory=list)


class ResultadoMotor(BaseModel):
    evaluacion_id: str
    fecha_evaluacion: datetime
    ambiente: str
    solicitud: Solicitud

    decision: DecisionFinal
    decision_interna: Decision
    causales: list[Causal] = Field(default_factory=list)

    score_consultado: Decimal | None = None
    score_tipo: str | None = None
    perfil_score: PerfilScore | None = None
    quanto_medio: Decimal = Decimal(0)
    valor_ingreso: Decimal = Decimal(0)
    ingreso_final: Decimal = Decimal(0)
    fuente_ingreso_final: str = "ninguna"
    ingreso_final_smmlv: Decimal = Decimal(0)
    smmlv: int = 0
    perfil_ingreso: PerfilIngreso | None = None

    gastos_financieros_no_rotativos: Decimal = Decimal(0)
    gasto_financiero_rotativo: Decimal = Decimal(0)
    gastos_personales: Decimal = Decimal(0)
    endeudamiento: Decimal = Decimal(0)
    disponible: Decimal = Decimal(0)
    capacidad_pago: Decimal = Decimal(0)
    cupo_sugerido: Decimal = Decimal(0)
    cuota_sugerida: Decimal = Decimal(0)
    cuota_moto: Decimal = Decimal(0)

    indicadores_buro: dict[str, Any] = Field(default_factory=dict)
    trazabilidad: list[PasoTraza] = Field(default_factory=list)
    advertencias: list[str] = Field(default_factory=list)
    parametros_usados: dict[str, Any] = Field(default_factory=dict)
    tiempo_ms: int = 0

    hdc_respuesta: RespuestaHDC | None = None
    valor_ingreso_respuesta: RespuestaValorIngreso | None = None

    @property
    def causales_detalle(self) -> list[CausalDetalle]:
        indicadores_por_causal = {
            "R2": "embargos",
            "R3": "cancelaciones_mal_manejo",
            "R4": "cartera_castigada",
            "R5": "dudoso_recaudo",
            "R6": "mora_60_vigente",
            "R7": "moras_30_historicas",
            "R8": "moras_60_historicas",
            "R9": "moras_90_historicas",
            "R10": "calificaciones_negativas",
            "R11": "reestructuraciones",
            "E2": "mora_30_vigente",
        }
        return [
            CausalDetalle.desde(
                causal,
                max(1, int(self.indicadores_buro.get(indicadores_por_causal.get(causal.codigo, ""), 1) or 1)),
            )
            for causal in self.causales
        ]


# ---------------------------------------------------------------------------
# DTOs de la API
# ---------------------------------------------------------------------------
class EvaluarRequest(BaseModel):
    """POST /motor/evaluar: solicitud completa en el payload."""

    model_config = ConfigDict(str_strip_whitespace=True)

    tipo_id: TipoIdentificacion
    numero_id: str = Field(min_length=1, max_length=20)
    primer_apellido: str = Field(min_length=1, max_length=60)
    ocupacion: Ocupacion
    tipo_contrato: TipoContrato | None = None
    antiguedad_meses: int | None = Field(default=None, ge=0)
    anios_camara_comercio: Decimal | None = Field(default=None, ge=0)
    fecha_nacimiento: date
    nacionalidad: str = "Colombia"
    tiene_multas_runt: bool = False
    ingresos_mensuales: Decimal = Field(default=Decimal(0), ge=0)
    otros_ingresos: Decimal = Field(default=Decimal(0), ge=0)
    saldo_financiar: Decimal = Field(gt=0, description="Valor a financiar de la moto (COP).")
    plazo: int = Field(gt=0, description="Plazo en meses.")
    tasa: Decimal = Field(ge=0, description="Tasa MENSUAL en porcentaje (ej. 2.0).")

    consultar_experian: bool = Field(
        default=False,
        description="Consulta HDC+ y Valor Ingreso en línea (requiere credenciales en .env).",
    )
    escenario_mock: str | None = Field(
        default=None,
        description="Solo ambiente demo sin consulta en línea: ver /motor/escenarios.",
    )

    def a_solicitud(self) -> Solicitud:
        return Solicitud(**self.model_dump(exclude={"consultar_experian", "escenario_mock"}))


class EvaluarSolicitudRequest(BaseModel):
    """
    POST /solicitudes/{id_solicitud}/evaluar: evalúa una solicitud ya
    existente en solicitud_credito (cliente, datos laborales). Los
    datos del crédito (monto, plazo, tasa) no están en el esquema, por
    eso se envían aquí.
    """

    saldo_financiar: Decimal = Field(gt=0)
    plazo: int = Field(gt=0)
    tasa: Decimal = Field(ge=0)
    primer_apellido: str | None = Field(
        default=None,
        description="Obligatorio si cliente.primer_apellido está vacío (HDC+ lo exige).",
    )
    tiene_multas_runt: bool = False
    consultar_experian: bool = False
    escenario_mock: str | None = None


class IngresoPropioRequest(BaseModel):
    """
    POST /motor/ingreso: Valor Ingreso calculado sobre cotizante /
    cotizante_ingreso_mensual ya almacenados para la solicitud.
    """

    id_solicitud: UUID
    meses_a_promediar: int = Field(default=3, ge=1, le=12)


class IngresoPropioResponse(BaseModel):
    id_solicitud: UUID
    valor_ingreso: Decimal
    aportantes_considerados: int
    meses_a_promediar: int


class ResultadoMotorResponse(BaseModel):
    """Respuesta pública del motor (sin las respuestas completas del buró)."""

    evaluacion_id: str
    fecha_evaluacion: datetime
    ambiente: str
    id_solicitud: str | None = None
    decision: DecisionFinal
    decision_interna: Decision
    causales: list[CausalDetalle]
    score_consultado: Decimal | None = None
    score_tipo: str | None = None
    perfil_score: PerfilScore | None = None
    perfil_ingreso: PerfilIngreso | None = None
    quanto_medio: Decimal
    valor_ingreso: Decimal
    ingreso_final: Decimal
    fuente_ingreso_final: str
    ingreso_final_smmlv: Decimal
    gastos_financieros_no_rotativos: Decimal
    gasto_financiero_rotativo: Decimal
    gastos_personales: Decimal
    endeudamiento: Decimal
    disponible: Decimal
    capacidad_pago: Decimal
    cupo_sugerido: Decimal
    cuota_sugerida: Decimal
    cuota_moto: Decimal
    indicadores_buro: dict[str, Any]
    trazabilidad: list[PasoTraza]
    advertencias: list[str]
    tiempo_ms: int
    valor_ingreso_respuesta: dict[str, Any] | None = None

    @classmethod
    def desde_resultado(
        cls, r: ResultadoMotor, id_solicitud: str | None = None, incluir_detalle_buro: bool = False
    ) -> "ResultadoMotorResponse":
        datos = r.model_dump(
            exclude={
                "causales",
                "solicitud",
                "hdc_respuesta",
                "valor_ingreso_respuesta",
                "parametros_usados",
                "smmlv",
            }
        )

        # Si se solicita, agregar información detallada del buró (sin datos sensibles)
        if incluir_detalle_buro and r.hdc_respuesta:
            datos["indicadores_buro"]["detalle_personas"] = {
                "nombre_completo": r.hdc_respuesta.persona.nombre_completo if r.hdc_respuesta.persona else None,
                "tipo_id": r.hdc_respuesta.persona.tipo_id if r.hdc_respuesta.persona else None,
                "numero_id": r.hdc_respuesta.persona.numero_id if r.hdc_respuesta.persona else None,
                "estado_documento": r.hdc_respuesta.persona.estado_documento if r.hdc_respuesta.persona else None,
                "edad_min": r.hdc_respuesta.persona.edad_min if r.hdc_respuesta.persona else None,
                "edad_max": r.hdc_respuesta.persona.edad_max if r.hdc_respuesta.persona else None,
                "genero": r.hdc_respuesta.persona.genero if r.hdc_respuesta.persona else None,
                "fecha_expedicion": str(r.hdc_respuesta.persona.fecha_expedicion)
                if r.hdc_respuesta.persona and r.hdc_respuesta.persona.fecha_expedicion
                else None,
                "validada": r.hdc_respuesta.persona.validada if r.hdc_respuesta.persona else False,
                "rut": r.hdc_respuesta.persona.rut if r.hdc_respuesta.persona else False,
            }
            datos["indicadores_buro"]["scores"] = [
                {
                    "tipo": s.tipo,
                    "puntaje": float(s.puntaje) if s.puntaje is not None else None,
                    "razones": s.razones,
                    "fecha": str(s.fecha) if s.fecha else None,
                    "poblacion": s.poblacion,
                }
                for s in r.hdc_respuesta.scores
            ]
            quanto_factor = Decimal(str(r.parametros_usados.get("quanto_factor", 1000)))
            datos["indicadores_buro"]["quanto"] = (
                {
                    "producto": r.hdc_respuesta.quanto.producto,
                    "valor_medio": float(r.hdc_respuesta.quanto.valor_medio * quanto_factor),
                    "valor_min": float(r.hdc_respuesta.quanto.valor_min * quanto_factor),
                    "valor_max": float(r.hdc_respuesta.quanto.valor_max * quanto_factor),
                    "razon": r.hdc_respuesta.quanto.razon,
                }
                if r.hdc_respuesta.quanto
                else None
            )
            from backend.services.capacidad_pago_service import (
                clasificar_obligacion,
                inclusion_gasto_financiero,
                rol_deudor,
            )

            def _serializar_obligacion(cuenta, es_tarjeta: bool = False) -> dict[str, Any]:
                base = {
                    "entidad": cuenta.entidad,
                    "numero": cuenta.numero,
                    "calificacion": cuenta.calificacion,
                    "calificacion_desc": cuenta.calificacion_desc,
                    "estado_cuenta": cuenta.estado_cuenta,
                    "estado_cuenta_desc": cuenta.estado_cuenta_desc,
                    "estado_origen": cuenta.estado_origen,
                    "estado_origen_desc": cuenta.estado_origen_desc,
                    "estado_pago": cuenta.estado_pago,
                    "evento_buro": cuenta.evento_buro,
                    "fecha_evento": str(cuenta.fecha_evento) if cuenta.fecha_evento else None,
                    "fecha_actualizacion": str(cuenta.fecha_actualizacion) if cuenta.fecha_actualizacion else None,
                    "saldo_actual": float(cuenta.saldo_actual),
                    "saldo_mora": float(cuenta.saldo_mora),
                    "cuota": float(cuenta.cuota),
                    "dias_mora": cuenta.dias_mora,
                    "comportamiento": cuenta.comportamiento,
                    "bloqueada": cuenta.bloqueada,
                    "calidad_deudor": cuenta.calidad_deudor,
                    "rol_deudor": rol_deudor(cuenta),
                    "condicion": clasificar_obligacion(cuenta)[0],
                    "motivo_condicion": clasificar_obligacion(cuenta)[1],
                    "entra_gasto_financiero": inclusion_gasto_financiero(cuenta)[0],
                    "motivo_inclusion_financiera": inclusion_gasto_financiero(cuenta)[1],
                }
                if es_tarjeta:
                    base.update(
                        {
                            "tipo_producto": "Tarjeta de crédito",
                            "clase": cuenta.clase,
                            "franquicia": cuenta.franquicia,
                            "cupo_total": float(cuenta.cupo_total),
                        }
                    )
                else:
                    base["tipo_cuenta"] = cuenta.tipo_cuenta
                return base

            datos["indicadores_buro"]["cuentas_cartera"] = [
                _serializar_obligacion(c) for c in r.hdc_respuesta.cuentas_cartera
            ]
            datos["indicadores_buro"]["tarjetas_credito"] = [
                _serializar_obligacion(t, es_tarjeta=True) for t in r.hdc_respuesta.tarjetas_credito
            ]
            datos["indicadores_buro"]["cuentas_ahorro"] = [
                {
                    "entidad": c.entidad,
                    "numero": c.numero,
                    "calificacion": c.calificacion,
                    "estado": c.estado,
                    "bloqueada": c.bloqueada,
                }
                for c in r.hdc_respuesta.cuentas_ahorro
            ]
            datos["indicadores_buro"]["cuentas_corriente"] = [
                {
                    "entidad": c.entidad,
                    "numero": c.numero,
                    "calificacion": c.calificacion,
                    "estado": c.estado,
                    "bloqueada": c.bloqueada,
                }
                for c in r.hdc_respuesta.cuentas_corriente
            ]
            datos["indicadores_buro"]["alertas"] = [
                {
                    "codigo": a.codigo,
                    "texto": a.texto,
                    "fuente": a.fuente,
                    "colocacion": str(a.colocacion) if a.colocacion else None,
                    "vencimiento": str(a.vencimiento) if a.vencimiento else None,
                }
                for a in r.hdc_respuesta.alertas
            ]
            datos["indicadores_buro"]["endeudamiento_global"] = [
                {
                    "entidad": e.entidad,
                    "sector": e.sector,
                    "calificacion": e.calificacion,
                    "tipo_credito": e.tipo_credito,
                    "moneda": e.moneda,
                    "numero_creditos": e.numero_creditos,
                    "saldo_pendiente": float(e.saldo_pendiente),
                    "fecha_reporte": str(e.fecha_reporte) if e.fecha_reporte else None,
                }
                for e in r.hdc_respuesta.endeudamiento_global
            ]

        # Valor Ingreso si está disponible
        if incluir_detalle_buro and r.valor_ingreso_respuesta:
            datos["valor_ingreso_respuesta"] = {
                "resumen_general": {
                    "promedio_ingresos_cotizante": float(
                        r.valor_ingreso_respuesta.resumen_general.promedio_ingresos_cotizante or 0
                    )
                    if r.valor_ingreso_respuesta.resumen_general
                    else 0,
                    "mediana_ingresos_cotizante": float(
                        r.valor_ingreso_respuesta.resumen_general.mediana_ingresos_cotizante or 0
                    )
                    if r.valor_ingreso_respuesta.resumen_general
                    else 0,
                    "ingreso_minimo_cotizante": float(
                        r.valor_ingreso_respuesta.resumen_general.ingreso_minimo_cotizante or 0
                    )
                    if r.valor_ingreso_respuesta.resumen_general
                    else 0,
                    "ingreso_maximo_cotizante": float(
                        r.valor_ingreso_respuesta.resumen_general.ingreso_maximo_cotizante or 0
                    )
                    if r.valor_ingreso_respuesta.resumen_general
                    else 0,
                    "meses_continuidad": r.valor_ingreso_respuesta.resumen_general.meses_continuidad
                    if r.valor_ingreso_respuesta.resumen_general
                    else 0,
                    "cantidad_fuentes_ingreso": r.valor_ingreso_respuesta.resumen_general.cantidad_fuentes_ingreso
                    if r.valor_ingreso_respuesta.resumen_general
                    else 0,
                    "ultimo_periodo_cotizado": r.valor_ingreso_respuesta.resumen_general.ultimo_periodo_cotizado
                    if r.valor_ingreso_respuesta.resumen_general
                    else None,
                },
                "tipo_id": r.valor_ingreso_respuesta.tipo_id,
                "numero_id": r.valor_ingreso_respuesta.numero_id,
                "nombres": r.valor_ingreso_respuesta.nombres,
                "apellidos": r.valor_ingreso_respuesta.apellidos,
                "eps": r.valor_ingreso_respuesta.eps,
                "afp": r.valor_ingreso_respuesta.afp,
                "respuesta_id": r.valor_ingreso_respuesta.respuesta_id,
                "ultima_empresa": r.valor_ingreso_respuesta.ultima_empresa,
                "indicadores": {
                    "tiempo_sin_pago": r.valor_ingreso_respuesta.indicadores.tiempo_sin_pago
                    if r.valor_ingreso_respuesta.indicadores
                    else 0,
                    "tiempo_total_laborado": r.valor_ingreso_respuesta.indicadores.tiempo_total_laborado
                    if r.valor_ingreso_respuesta.indicadores
                    else 0,
                    "promedio_ult_mes": float(r.valor_ingreso_respuesta.indicadores.promedio_ult_mes)
                    if r.valor_ingreso_respuesta.indicadores
                    else 0,
                    "ingreso_total_ult_mes": float(r.valor_ingreso_respuesta.indicadores.ingreso_total_ult_mes)
                    if r.valor_ingreso_respuesta.indicadores
                    else 0,
                    "promedio_ult_tres_meses": float(r.valor_ingreso_respuesta.indicadores.promedio_ult_tres_meses)
                    if r.valor_ingreso_respuesta.indicadores
                    else 0,
                    "total_ult_tres_meses": float(r.valor_ingreso_respuesta.indicadores.total_ult_tres_meses)
                    if r.valor_ingreso_respuesta.indicadores
                    else 0,
                    "promedio_ult_doce_meses": float(r.valor_ingreso_respuesta.indicadores.promedio_ult_doce_meses)
                    if r.valor_ingreso_respuesta.indicadores
                    else 0,
                    "total_ult_doce_meses": float(r.valor_ingreso_respuesta.indicadores.total_ult_doce_meses)
                    if r.valor_ingreso_respuesta.indicadores
                    else 0,
                },
                "aportantes": [
                    {
                        "razon_social": a.razon_social,
                        "tipo_id": a.tipo_id,
                        "numero_id": a.numero_id,
                        "tipo_cotizante": a.tipo_cotizante,
                        "descripcion_cotizante": a.descripcion_cotizante,
                        "tipo_planilla": a.tipo_planilla,
                        "actividad_aportante": a.actividad_aportante,
                        "ingreso_maximo": float(a.ingreso_maximo),
                        "ingreso_minimo": float(a.ingreso_minimo),
                        "promedio_ingresos": float(a.promedio_ingresos),
                        "media_ingresos": float(a.media_ingresos),
                        "resultado_pagos": [
                            {
                                "anio": p.anio,
                                "mes": p.mes,
                                "realizo_pago": p.realizo_pago,
                                "ingresos": float(p.ingresos),
                            }
                            for p in a.resultado_pagos
                        ],
                    }
                    for a in r.valor_ingreso_respuesta.aportantes
                ],
            }

        return cls(**datos, causales=r.causales_detalle, id_solicitud=id_solicitud)


class ResultadoBinarioResponse(BaseModel):
    """Vista operativa de la evaluación para asesor y aliado: la
    decisión del motor y lo que sostiene la oferta. Nunca incluye score,
    causales, trazabilidad, indicadores de buró ni métricas internas —
    eso es exclusivo del expediente del administrador."""

    evaluacion_id: str
    fecha_evaluacion: datetime
    ambiente: str
    id_solicitud: str | None = None
    decision: DecisionFinal
    cupo_sugerido: Decimal
    cuota_sugerida: Decimal
    cuota_moto: Decimal
    advertencias: list[str]
    tiempo_ms: int

    @classmethod
    def desde_resultado(
        cls, r: ResultadoMotor, id_solicitud: str | None = None
    ) -> "ResultadoBinarioResponse":
        return cls(
            evaluacion_id=r.evaluacion_id,
            fecha_evaluacion=r.fecha_evaluacion,
            ambiente=r.ambiente,
            id_solicitud=id_solicitud,
            decision=r.decision,
            cupo_sugerido=r.cupo_sugerido,
            cuota_sugerida=r.cuota_sugerida,
            cuota_moto=r.cuota_moto,
            advertencias=r.advertencias,
            tiempo_ms=r.tiempo_ms,
        )
