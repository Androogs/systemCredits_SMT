"""
Modelos SQLAlchemy (Fase 1) que mapean las tablas de database/schema.sql
necesarias para el motor de decisión propio.

Alcance: se mapean las tablas que el motor de decisión, el cálculo
de capacidad de pago y el motor de elegibilidad necesitan leer o
escribir directamente. El resto de tablas del esquema (seguros,
desembolsos, bancos, auditoría, etc.) no se mapean aquí porque no
son parte del flujo de evaluación de crédito en sí; se pueden ir
agregando en este mismo archivo o en módulos adicionales bajo
db_models/ a medida que se necesiten.

No se reimplementan aquí los ENUM de Postgres uno por uno: se usan
como String con el valor validado a nivel de aplicación, para no
duplicar el CREATE TYPE de schema.sql. Si se prefiere el mapeo
estricto a ENUM de Postgres, reemplazar String por
sqlalchemy.dialects.postgresql.ENUM apuntando al tipo ya creado en
la base de datos (create_type=False).

Tipos portables (ensamble): se usan sqlalchemy.Uuid y JSON con
variante JSONB, que en PostgreSQL mapean a UUID/JSONB nativos y en
SQLite permiten correr las pruebas sin servidor. Las columnas que el
motor agregó al esquema están marcadas y su ALTER TABLE está en
database/migraciones/001_motor_decision.sql.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    FetchedValue,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db_models.base import Base

# JSONB en PostgreSQL, JSON genérico en otros motores.
JSONPortable = JSON().with_variant(JSONB(), "postgresql")

# Tipos ENUM nativos de PostgreSQL (schema.sql). Con create_type=False
# el ORM usa el tipo existente en Postgres y VARCHAR en SQLite, sin
# intentar crear el type en CREATE TABLE.
OCUPACION_DB = Enum(
    "empleado", "independiente", "pensionado", "fuerzas_militares",
    name="ocupacion_cliente", create_type=False,
)
DECISION_DB = Enum(
    "aprobado", "rechazado", "perfil_gris",
    name="decision_credito", create_type=False,
)
ESTADO_SOLICITUD_DB = Enum(
    "creada", "en_evaluacion", "aprobada", "rechazada", "en_revision",
    "desembolsada", "cancelada",
    name="estado_solicitud", create_type=False,
)
TIPO_CONTRATO_DB = Enum(
    "indefinido", "fijo", "obra_labor", "no_aplica",
    name="tipo_contrato", create_type=False,
)
TIPO_CUENTA_DB = Enum(
    "ahorros",
    name="tipo_cuenta", create_type=False,
)
ESTADO_DESEMBOLSO_DB = Enum(
    "pendiente", "confirmado", "rechazado", "anulado",
    name="estado_desembolso", create_type=False,
)


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class Cliente(Base):
    __tablename__ = "cliente"

    id_cliente: Mapped[int] = mapped_column(primary_key=True)
    tipo_documento: Mapped[str] = mapped_column(String(30))
    num_cedula: Mapped[str] = mapped_column(String(40), unique=True)
    nombre_completo: Mapped[str] = mapped_column(String(200))
    # Agregado por el motor: HDC+ exige el primer apellido para consultar.
    primer_apellido: Mapped[str | None] = mapped_column(String(60))
    fecha_nacimiento: Mapped[date] = mapped_column(Date)
    ocupacion: Mapped[str | None] = mapped_column(OCUPACION_DB)
    es_persona_natural: Mapped[bool] = mapped_column(Boolean, default=True)
    nacionalidad: Mapped[str] = mapped_column(String(80), default="Colombia")

    solicitudes: Mapped[list["SolicitudCredito"]] = relationship(back_populates="cliente")


class SolicitudCredito(Base):
    __tablename__ = "solicitud_credito"

    id_solicitud: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Generado por la base de datos (secuencia en schema.sql).
    num_solicitud: Mapped[int | None] = mapped_column(unique=True, server_default=FetchedValue())
    id_cliente: Mapped[int] = mapped_column(ForeignKey("cliente.id_cliente"))
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora_utc)
    moneda: Mapped[str] = mapped_column(String(3), default="COP")
    decision: Mapped[str | None] = mapped_column(DECISION_DB)
    estado: Mapped[str] = mapped_column(ESTADO_SOLICITUD_DB, default="creada")
    descripcion_estado: Mapped[str | None] = mapped_column(Text)
    # Datos del producto capturados en el paso "Crear solicitud" del
    # flujo de originación (columnas agregadas en 0002_motor_decision).
    linea_credito: Mapped[str | None] = mapped_column(String(60))
    destino_credito: Mapped[str | None] = mapped_column(String(80))
    plazo_deseado_meses: Mapped[int | None] = mapped_column(SmallInteger)

    cliente: Mapped["Cliente"] = relationship(back_populates="solicitudes")
    datos_laborales: Mapped["DatosLaborales"] = relationship(back_populates="solicitud", uselist=False)
    contacto_vivienda: Mapped["SolicitudContactoVivienda"] = relationship(back_populates="solicitud", uselist=False)
    cotizantes: Mapped[list["Cotizante"]] = relationship(back_populates="solicitud")
    evaluaciones: Mapped[list["EvaluacionCredito"]] = relationship(back_populates="solicitud")
    capacidades_pago: Mapped[list["CapacidadPago"]] = relationship(back_populates="solicitud")
    causales: Mapped[list["SolicitudCausal"]] = relationship(back_populates="solicitud")
    ofertas: Mapped[list["OfertaCredito"]] = relationship(back_populates="solicitud")


class DatosLaborales(Base):
    __tablename__ = "datos_laborales"

    id_datos_laborales: Mapped[int] = mapped_column(primary_key=True)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("solicitud_credito.id_solicitud"),
        unique=True,
    )
    tipo_contrato: Mapped[str | None] = mapped_column(TIPO_CONTRATO_DB)
    meses_continuidad: Mapped[int | None] = mapped_column(Integer)
    ingreso_mensual: Mapped[float | None] = mapped_column(Numeric(18, 2))
    otros_ingresos: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # Agregado al implementar el motor propio: solo aplica para
    # Independientes (perfil de ingreso, ver reglas_perfil.py).
    anios_camara_comercio: Mapped[float | None] = mapped_column(Numeric(6, 2))

    solicitud: Mapped["SolicitudCredito"] = relationship(back_populates="datos_laborales")


class SolicitudContactoVivienda(Base):
    __tablename__ = "solicitud_contacto_vivienda"

    id_contacto_vivienda: Mapped[int] = mapped_column(primary_key=True)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("solicitud_credito.id_solicitud"),
        unique=True,
    )
    estrato: Mapped[int | None] = mapped_column(SmallInteger)
    personas_a_cargo: Mapped[int | None] = mapped_column(SmallInteger)
    tipo_vivienda: Mapped[str | None] = mapped_column(String(50))

    solicitud: Mapped["SolicitudCredito"] = relationship(back_populates="contacto_vivienda")


class Cotizante(Base):
    __tablename__ = "cotizante"

    id_cotizante: Mapped[int] = mapped_column(primary_key=True)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("solicitud_credito.id_solicitud"))
    razon_social_aportante: Mapped[str] = mapped_column(String(200))
    valor_ingreso: Mapped[float | None] = mapped_column(Numeric(18, 2))
    promedio_ultimos_3_meses: Mapped[float | None] = mapped_column(Numeric(18, 2))
    mediana: Mapped[float | None] = mapped_column(Numeric(18, 2))
    moda: Mapped[float | None] = mapped_column(Numeric(18, 2))
    tendencia: Mapped[str | None] = mapped_column(String(40))
    percentil: Mapped[float | None] = mapped_column(Numeric(8, 4))
    meses_continuidad: Mapped[int | None] = mapped_column(Integer)

    solicitud: Mapped["SolicitudCredito"] = relationship(back_populates="cotizantes")
    ingresos_mensuales: Mapped[list["CotizanteIngresoMensual"]] = relationship(back_populates="cotizante")


class CotizanteIngresoMensual(Base):
    __tablename__ = "cotizante_ingreso_mensual"

    id_cotizante: Mapped[int] = mapped_column(ForeignKey("cotizante.id_cotizante"), primary_key=True)
    periodo: Mapped[date] = mapped_column(Date, primary_key=True)
    ingreso: Mapped[float] = mapped_column(Numeric(18, 2))

    cotizante: Mapped["Cotizante"] = relationship(back_populates="ingresos_mensuales")


class CriterioEvaluacion(Base):
    __tablename__ = "criterio_evaluacion"

    id_criterio: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(60), unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(20))  # 'buro' | 'interno' | 'aliado'


class EvaluacionCredito(Base):
    __tablename__ = "evaluacion_credito"

    id_evaluacion: Mapped[int] = mapped_column(primary_key=True)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("solicitud_credito.id_solicitud"))
    version: Mapped[int] = mapped_column(SmallInteger, default=1)
    vigente: Mapped[bool] = mapped_column(Boolean, default=True)
    origen_evaluacion: Mapped[str] = mapped_column(String(40), default="motor_pacifico")
    score: Mapped[float | None] = mapped_column(Numeric(8, 2))
    valor_ingreso: Mapped[float | None] = mapped_column(Numeric(18, 2))
    ingreso_final: Mapped[float | None] = mapped_column(Numeric(18, 2))
    endeudamiento: Mapped[float | None] = mapped_column(Numeric(8, 4))
    capacidad_pago: Mapped[float | None] = mapped_column(Numeric(18, 2))

    # Variables de riesgo provistas por Datacrédito (tipo 'buro' en
    # criterio_evaluacion). Se llenan con los conteos que el motor
    # deriva de HDC+ (reglas_filtros_duros.IndicadoresBuro), ver
    # EvaluacionRepository.crear_evaluacion_motor.
    mora_historica_90: Mapped[int] = mapped_column(Integer, default=0)
    mora_historica_60: Mapped[int] = mapped_column(Integer, default=0)
    mora_historica_30: Mapped[int] = mapped_column(Integer, default=0)
    mora_60: Mapped[int] = mapped_column(Integer, default=0)
    mora_30: Mapped[int] = mapped_column(Integer, default=0)
    embargo: Mapped[int] = mapped_column(Integer, default=0)
    dudoso_recaudo: Mapped[int] = mapped_column(Integer, default=0)
    cartera_castigada: Mapped[int] = mapped_column(Integer, default=0)
    cancelaciones_negativas: Mapped[int] = mapped_column(Integer, default=0)
    obligaciones_reestructuradas: Mapped[int] = mapped_column(Integer, default=0)
    calificacion_diferente_ab: Mapped[int] = mapped_column(Integer, default=0)
    documento_vigente: Mapped[bool | None] = mapped_column(Boolean)

    # Agregados al implementar el motor propio (BRD-IMPL-111350):
    # letra de calificación real (A, B, C, D, E, AA, BB, CC, K),
    # necesaria para el filtro duro CAUSAL_R10; quanto3_medio, usado
    # en la cadena de respaldo de ingreso final; reportado_fallecido
    # para CAUSAL_R1; y el código de exclusión del score (0/4/99/
    # 70-77) que cambia la lógica de decisión.
    calificacion: Mapped[str | None] = mapped_column(String(5))
    quanto3_medio: Mapped[float | None] = mapped_column(Numeric(18, 2))
    reportado_fallecido: Mapped[bool] = mapped_column(Boolean, default=False)
    score_codigo_exclusion: Mapped[str | None] = mapped_column(String(5))

    # Agregados en el ensamble: perfiles asignados por el motor y
    # decisión interna (Estudio / Requiere Codeudor) para trazabilidad.
    perfil_score: Mapped[str | None] = mapped_column(String(10))
    perfil_ingreso: Mapped[str | None] = mapped_column(String(10))
    decision_interna: Mapped[str | None] = mapped_column(String(30))

    solicitud: Mapped["SolicitudCredito"] = relationship(back_populates="evaluaciones")
    detalles: Mapped[list["EvaluacionDetalle"]] = relationship(back_populates="evaluacion")


class EvaluacionDetalle(Base):
    __tablename__ = "evaluacion_detalle"

    id_evaluacion_detalle: Mapped[int] = mapped_column(primary_key=True)
    id_evaluacion: Mapped[int] = mapped_column(ForeignKey("evaluacion_credito.id_evaluacion"))
    id_criterio: Mapped[int] = mapped_column(ForeignKey("criterio_evaluacion.id_criterio"))
    resultado: Mapped[bool] = mapped_column(Boolean)
    puntaje: Mapped[float | None] = mapped_column(Numeric(8, 2))
    causal: Mapped[str | None] = mapped_column(Text)

    evaluacion: Mapped["EvaluacionCredito"] = relationship(back_populates="detalles")
    criterio: Mapped["CriterioEvaluacion"] = relationship()


class SolicitudCausal(Base):
    __tablename__ = "solicitud_causal"

    id_solicitud_causal: Mapped[int] = mapped_column(primary_key=True)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("solicitud_credito.id_solicitud"))
    id_criterio: Mapped[int | None] = mapped_column(ForeignKey("criterio_evaluacion.id_criterio"))
    codigo: Mapped[str] = mapped_column(String(60))
    descripcion: Mapped[str] = mapped_column(Text)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)

    solicitud: Mapped["SolicitudCredito"] = relationship(back_populates="causales")


class CapacidadPago(Base):
    __tablename__ = "capacidad_pago"

    id_capacidad: Mapped[int] = mapped_column(primary_key=True)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("solicitud_credito.id_solicitud"))
    version: Mapped[int] = mapped_column(SmallInteger, default=1)
    vigente: Mapped[bool] = mapped_column(Boolean, default=True)
    salario_minimo: Mapped[float | None] = mapped_column(Numeric(18, 2))
    ingreso_final: Mapped[float | None] = mapped_column(Numeric(18, 2))
    ingreso_final_smlmv: Mapped[float | None] = mapped_column(Numeric(8, 4))
    gastos_personales: Mapped[float | None] = mapped_column(Numeric(18, 2))
    disponible_1: Mapped[float | None] = mapped_column(Numeric(18, 2))
    capacidad_pago_2: Mapped[float | None] = mapped_column(Numeric(18, 2))
    tasa_cupo: Mapped[float | None] = mapped_column(Numeric(8, 4))
    plazo_cupo: Mapped[int | None] = mapped_column(Integer)
    cupo_calculado: Mapped[float | None] = mapped_column(Numeric(18, 2))
    cupo_aprobado: Mapped[float | None] = mapped_column(Numeric(18, 2))

    solicitud: Mapped["SolicitudCredito"] = relationship(back_populates="capacidades_pago")


class AliadoProducto(Base):
    __tablename__ = "aliado_producto"
    __table_args__ = (
        UniqueConstraint("id_aliado", "nombre", name="uq_aliado_producto"),
    )

    id_aliado_producto: Mapped[int] = mapped_column(primary_key=True)
    id_aliado: Mapped[int] = mapped_column(ForeignKey("aliado_financiero.id_aliado"))
    nombre: Mapped[str] = mapped_column(String(180))
    tasa_min: Mapped[float | None] = mapped_column(Numeric(8, 4))
    tasa_max: Mapped[float | None] = mapped_column(Numeric(8, 4))
    plazo_min_meses: Mapped[int | None] = mapped_column(SmallInteger)
    plazo_max_meses: Mapped[int | None] = mapped_column(SmallInteger)
    monto_min: Mapped[float | None] = mapped_column(Numeric(18, 2))
    monto_max: Mapped[float | None] = mapped_column(Numeric(18, 2))
    score_min: Mapped[int | None] = mapped_column(SmallInteger)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    reglas: Mapped[list["AliadoReglaElegibilidad"]] = relationship(back_populates="producto")
    ofertas: Mapped[list["OfertaCredito"]] = relationship(back_populates="producto")


class AliadoFinanciero(Base):
    __tablename__ = "aliado_financiero"

    id_aliado: Mapped[int] = mapped_column(primary_key=True)
    nit: Mapped[str] = mapped_column(String(30), unique=True)
    nombre: Mapped[str] = mapped_column(String(180), unique=True)
    tipo: Mapped[str] = mapped_column(String(20))
    es_propio: Mapped[bool] = mapped_column(Boolean, default=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class AliadoReglaElegibilidad(Base):
    __tablename__ = "aliado_regla_elegibilidad"

    id_regla: Mapped[int] = mapped_column(primary_key=True)
    id_aliado_producto: Mapped[int] = mapped_column(ForeignKey("aliado_producto.id_aliado_producto"))
    campo: Mapped[str] = mapped_column(String(80))
    operador: Mapped[str] = mapped_column(String(10))
    valor_json: Mapped[dict] = mapped_column(JSONPortable)

    producto: Mapped["AliadoProducto"] = relationship(back_populates="reglas")


class OfertaCredito(Base):
    __tablename__ = "oferta_credito"

    id_oferta: Mapped[int] = mapped_column(primary_key=True)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("solicitud_credito.id_solicitud"))
    id_aliado_producto: Mapped[int] = mapped_column(ForeignKey("aliado_producto.id_aliado_producto"))
    elegible: Mapped[bool] = mapped_column(Boolean)
    motivo_no_elegible: Mapped[str | None] = mapped_column(Text)
    tasa_ofrecida: Mapped[float | None] = mapped_column(Numeric(8, 4))
    plazo_ofrecido: Mapped[int | None] = mapped_column(Integer)
    cuota_mensual: Mapped[float | None] = mapped_column(Numeric(18, 2))
    monto_aprobado: Mapped[float | None] = mapped_column(Numeric(18, 2))
    seleccionada: Mapped[bool] = mapped_column(Boolean, default=False)

    solicitud: Mapped["SolicitudCredito"] = relationship(back_populates="ofertas")
    producto: Mapped["AliadoProducto"] = relationship(back_populates="ofertas")


# ---------------------------------------------------------------------------
# Formalización y desembolso (Fase 2 del flujo: oferta seleccionada -> crédito
# -> desembolso). Los triggers del esquema (validar_cuentas_desembolso)
# validan en Postgres que el emisor sea cuenta del aliado propio y el
# receptor una cuenta de ahorros activa del cliente.
# ---------------------------------------------------------------------------
class Banco(Base):
    __tablename__ = "banco"

    id_banco: Mapped[int] = mapped_column(primary_key=True)
    codigo_ach: Mapped[str | None] = mapped_column(String(10), unique=True)
    nombre: Mapped[str] = mapped_column(String(180))
    nit: Mapped[str | None] = mapped_column(String(30))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class CuentaBancaria(Base):
    __tablename__ = "cuenta_bancaria"
    __table_args__ = (
        UniqueConstraint("id_banco", "numero", "tipo", name="uq_cuenta_banco_numero_tipo"),
    )

    id_cuenta: Mapped[int] = mapped_column(primary_key=True)
    id_banco: Mapped[int] = mapped_column(ForeignKey("banco.id_banco"))
    tipo: Mapped[str] = mapped_column(TIPO_CUENTA_DB)
    numero: Mapped[str] = mapped_column(String(40))
    titular: Mapped[str] = mapped_column(String(180))
    nit_titular: Mapped[str | None] = mapped_column(String(30))
    id_aliado: Mapped[int | None] = mapped_column(ForeignKey("aliado_financiero.id_aliado"))
    id_concesionario: Mapped[int | None] = mapped_column(Integer)
    id_cliente: Mapped[int | None] = mapped_column(ForeignKey("cliente.id_cliente"))
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


class ProductoVehiculo(Base):
    __tablename__ = "producto_vehiculo"

    id_vehiculo: Mapped[int] = mapped_column(primary_key=True)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("solicitud_credito.id_solicitud"))
    producto_a_financiar: Mapped[str] = mapped_column(String(180))
    marca: Mapped[str | None] = mapped_column(String(100))
    referencia: Mapped[str | None] = mapped_column(String(120))
    modelo: Mapped[str | None] = mapped_column(String(30))
    color: Mapped[str | None] = mapped_column(String(60))
    valor_moto_iva: Mapped[float | None] = mapped_column(Numeric(18, 2))


class CreditoFinanciacion(Base):
    __tablename__ = "credito_financiacion"

    id_credito: Mapped[int] = mapped_column(primary_key=True)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("solicitud_credito.id_solicitud"))
    id_vehiculo: Mapped[int] = mapped_column(ForeignKey("producto_vehiculo.id_vehiculo"))
    id_oferta: Mapped[int | None] = mapped_column(ForeignKey("oferta_credito.id_oferta"))
    id_aliado_financiero: Mapped[int | None] = mapped_column(ForeignKey("aliado_financiero.id_aliado"))
    ganadora: Mapped[bool] = mapped_column(Boolean, default=False)
    tasa: Mapped[float] = mapped_column(Numeric(8, 4))
    plazo: Mapped[int] = mapped_column(Integer)
    seguro: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    cuota_inicial: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    valor_financiar: Mapped[float] = mapped_column(Numeric(18, 2))
    gastos_administrativos: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    saldo_financiar: Mapped[float] = mapped_column(Numeric(18, 2))
    valor_financiacion: Mapped[float] = mapped_column(Numeric(18, 2))
    valor_seguro_vida: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total_a_pagar: Mapped[float] = mapped_column(Numeric(18, 2))
    cuota_financiacion: Mapped[float] = mapped_column(Numeric(18, 2))
    cuota_seguro_vida: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    cuota_total: Mapped[float] = mapped_column(Numeric(18, 2))
    moneda: Mapped[str] = mapped_column(String(3), default="COP")
    dia_pago: Mapped[int | None] = mapped_column(SmallInteger)
    fecha_inicio: Mapped[date | None] = mapped_column(Date)
    fecha_fin: Mapped[date | None] = mapped_column(Date)


class Desembolso(Base):
    __tablename__ = "desembolso"

    id_desembolso: Mapped[int] = mapped_column(primary_key=True)
    num_desembolso: Mapped[str | None] = mapped_column(String(30), unique=True)
    id_credito: Mapped[int] = mapped_column(ForeignKey("credito_financiacion.id_credito"))
    id_cuenta_emisor: Mapped[int] = mapped_column(ForeignKey("cuenta_bancaria.id_cuenta"))
    emisor: Mapped[str] = mapped_column(String(180))
    id_cuenta_receptor: Mapped[int] = mapped_column(ForeignKey("cuenta_bancaria.id_cuenta"))
    nit_receptor: Mapped[str | None] = mapped_column(String(30))
    receptor: Mapped[str] = mapped_column(String(180))
    referencia_pago: Mapped[str | None] = mapped_column(String(80))
    fecha_desembolso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_anexo: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    capital: Mapped[float] = mapped_column(Numeric(18, 2))
    cuota: Mapped[float] = mapped_column(Numeric(18, 2))
    plazo: Mapped[int] = mapped_column(Integer)
    tasa: Mapped[float] = mapped_column(Numeric(8, 4))
    valor_seguro: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    moneda: Mapped[str] = mapped_column(String(3), default="COP")
    estado: Mapped[str] = mapped_column(ESTADO_DESEMBOLSO_DB, default="pendiente")
