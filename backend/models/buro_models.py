"""
Modelos de las respuestas de buró (DataCrédito Experian) ya
normalizadas: Historia de Crédito+ (HDC+) y Valor Ingreso.

Los parsers de backend/integrations/datacredito/parsers convierten el
JSON del proveedor a estos modelos; las reglas del motor solo conocen
estos modelos, nunca el JSON crudo.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class PersonaBasica(BaseModel):
    nombres: str | None = None
    primer_apellido: str | None = None
    segundo_apellido: str | None = None
    nombre_completo: str | None = None
    tipo_id: str | None = None
    numero_id: str | None = None
    genero: str | None = None
    estado_documento: str | None = None
    fecha_expedicion: date | None = None
    edad_min: int | None = None
    edad_max: int | None = None
    validada: bool = False
    rut: bool = False


class Score(BaseModel):
    tipo: str | None = None
    puntaje: Decimal | None = None
    razones: list[str] = Field(default_factory=list)
    fecha: date | None = None
    poblacion: int | None = None


class Quanto(BaseModel):
    """Estimador de ingresos. HDC+ lo reporta en MILES de pesos."""

    producto: str
    valor_medio: Decimal = Decimal(0)
    valor_min: Decimal = Decimal(0)
    valor_max: Decimal = Decimal(0)
    valor_medio_smlv: Decimal = Decimal(0)
    valor_min_smlv: Decimal = Decimal(0)
    valor_max_smlv: Decimal = Decimal(0)
    razon: str | None = None


class CuentaCartera(BaseModel):
    entidad: str | None = None
    numero: str | None = None
    tipo_cuenta: str | None = None
    calificacion: str | None = None
    calificacion_desc: str | None = None
    estado_pago: str | None = None
    estado_cuenta: str | None = None
    estado_cuenta_desc: str | None = None
    estado_origen: str | None = None
    estado_origen_desc: str | None = None
    fecha_estado_origen: date | None = None
    evento_buro: str | None = None
    fecha_evento: date | None = None
    fecha_actualizacion: date | None = None
    fecha_apertura: date | None = None
    fecha_vencimiento: date | None = None
    saldo_actual: Decimal = Decimal(0)
    saldo_mora: Decimal = Decimal(0)
    cuota: Decimal = Decimal(0)
    valor_inicial: Decimal = Decimal(0)
    dias_mora: int = 0
    cuotas_mora: int = 0
    comportamiento: str | None = None
    sector: str | None = None
    bloqueada: bool = False
    forma_pago: str | None = None
    garantia: str | None = None
    tipo_obligacion: str | None = None
    calidad_deudor: str | None = None


class TarjetaCredito(BaseModel):
    entidad: str | None = None
    numero: str | None = None
    calificacion: str | None = None
    calificacion_desc: str | None = None
    estado_pago: str | None = None
    estado_cuenta: str | None = None
    estado_cuenta_desc: str | None = None
    estado_plastico: str | None = None
    evento_buro: str | None = None
    fecha_evento: date | None = None
    fecha_actualizacion: date | None = None
    estado_origen: str | None = None
    estado_origen_desc: str | None = None
    fecha_estado_origen: date | None = None
    forma_pago: str | None = None
    fecha_apertura: date | None = None
    fecha_vencimiento: date | None = None
    saldo_actual: Decimal = Decimal(0)
    saldo_mora: Decimal = Decimal(0)
    cupo_total: Decimal = Decimal(0)
    cuota: Decimal = Decimal(0)
    dias_mora: int = 0
    cuotas_mora: int = 0
    comportamiento: str | None = None
    sector: str | None = None
    bloqueada: bool = False
    franquicia: str | None = None
    clase: str | None = None
    calidad_deudor: str | None = None


class CuentaAhorro(BaseModel):
    entidad: str | None = None
    numero: str | None = None
    calificacion: str | None = None
    estado: str | None = None
    fecha_apertura: date | None = None
    bloqueada: bool = False
    clase: str | None = None


class CuentaCorriente(BaseModel):
    entidad: str | None = None
    numero: str | None = None
    calificacion: str | None = None
    estado: str | None = None
    fecha_apertura: date | None = None
    bloqueada: bool = False


class EndeudamientoGlobal(BaseModel):
    entidad: str | None = None
    sector: str | None = None
    calificacion: str | None = None
    tipo_credito: str | None = None
    moneda: str | None = None
    numero_creditos: int = 0
    saldo_pendiente: Decimal = Decimal(0)
    fecha_reporte: date | None = None


class Alerta(BaseModel):
    codigo: str | None = None
    texto: str | None = None
    fuente: str | None = None
    colocacion: date | None = None
    vencimiento: date | None = None


class RespuestaHDC(BaseModel):
    persona: PersonaBasica | None = None
    scores: list[Score] = Field(default_factory=list)
    quanto: Quanto | None = None
    cuentas_cartera: list[CuentaCartera] = Field(default_factory=list)
    tarjetas_credito: list[TarjetaCredito] = Field(default_factory=list)
    cuentas_ahorro: list[CuentaAhorro] = Field(default_factory=list)
    cuentas_corriente: list[CuentaCorriente] = Field(default_factory=list)
    endeudamiento_global: list[EndeudamientoGlobal] = Field(default_factory=list)
    alertas: list[Alerta] = Field(default_factory=list)
    respuesta_codigo: str | None = None
    respuesta_desc: str | None = None


# Código de respuesta de HDC+ que indica "La consulta fue efectiva".
HDC_CODIGO_CONSULTA_EFECTIVA = "13"


class PeriodoPago(BaseModel):
    anio: int
    mes: int
    realizo_pago: bool
    ingresos: Decimal = Decimal(0)


class Aportante(BaseModel):
    tipo_id: str | None = None
    numero_id: str | None = None
    razon_social: str | None = None
    tipo_cotizante: int | None = None
    descripcion_cotizante: str | None = None
    ingreso_maximo: Decimal = Decimal(0)
    ingreso_minimo: Decimal = Decimal(0)
    promedio_ingresos: Decimal = Decimal(0)
    media_ingresos: Decimal = Decimal(0)
    tiene_salario_integral: bool | None = None
    tiene_salario_fijo: bool | None = None
    tiene_salario_variable: bool | None = None
    tiene_novedad_ingreso: bool | None = None
    tiene_novedad_retiro: bool | None = None
    tipo_planilla: str | None = None
    actividad_aportante: str | None = None
    resultado_pagos: list[PeriodoPago] = Field(default_factory=list)


class Indicadores(BaseModel):
    tiempo_sin_pago: int = 0
    tiempo_total_laborado: int = 0
    ingreso_total_ult_mes: Decimal = Decimal(0)
    promedio_ult_tres_meses: Decimal = Decimal(0)
    promedio_ult_doce_meses: Decimal = Decimal(0)
    total_ult_tres_meses: Decimal = Decimal(0)
    total_ult_doce_meses: Decimal = Decimal(0)
    promedio_ult_mes: Decimal = Decimal(0)


class ResumenGeneralIngresos(BaseModel):
    promedio_ingresos_cotizante: Decimal | None = None
    mediana_ingresos_cotizante: Decimal | None = None
    desviacion_estandar: Decimal | None = None
    ingreso_minimo_cotizante: Decimal | None = None
    ingreso_maximo_cotizante: Decimal | None = None
    pendiente_ingresos: Decimal | None = None
    tendencia_ingresos: str | None = None
    meses_continuidad: int | None = None
    cantidad_fuentes_ingreso: int | None = None
    ultimo_periodo_cotizado: str | None = None
    promedio_ultimos_tres_meses_sin_dic_jun: Decimal | None = None
    promedio_ultimos_seis_meses_sin_dic_jun: Decimal | None = None
    consecutivos_seis_meses: int | None = None


class RespuestaValorIngreso(BaseModel):
    tipo_id: str | None = None
    numero_id: str | None = None
    nombres: str | None = None
    apellidos: str | None = None
    eps: str | None = None
    afp: str | None = None
    aportantes: list[Aportante] = Field(default_factory=list)
    indicadores: Indicadores | None = None
    resumen_general: ResumenGeneralIngresos | None = None
    respuesta_id: int | None = None
    ultima_empresa: str | None = None
