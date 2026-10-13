"""DTOs para crear solicitudes en el esquema SUMOTO y gestionar ofertas."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.models.enums import Ocupacion, TipoContrato, TipoIdentificacion


class ClienteInput(BaseModel):
    tipo_documento: TipoIdentificacion
    num_cedula: str = Field(min_length=1, max_length=40)
    nombre_completo: str = Field(min_length=1, max_length=200)
    primer_apellido: str = Field(min_length=1, max_length=60)
    fecha_nacimiento: date
    ocupacion: Ocupacion
    nacionalidad: str = "Colombia"


class DatosLaboralesInput(BaseModel):
    tipo_contrato: TipoContrato | None = None
    meses_continuidad: int | None = Field(default=None, ge=0)
    ingreso_mensual: Decimal | None = Field(default=None, ge=0)
    otros_ingresos: Decimal = Field(default=Decimal(0), ge=0)
    anios_camara_comercio: Decimal | None = Field(default=None, ge=0)


class ContactoViviendaInput(BaseModel):
    estrato: int | None = Field(default=None, ge=0, le=6)
    personas_a_cargo: int | None = Field(default=None, ge=0)
    tipo_vivienda: str | None = None


class CrearSolicitudRequest(BaseModel):
    cliente: ClienteInput
    datos_laborales: DatosLaboralesInput
    contacto_vivienda: ContactoViviendaInput = ContactoViviendaInput()
    moneda: str = "COP"
    # Producto capturado en el paso "Crear solicitud" de originación.
    linea_credito: str | None = Field(default=None, max_length=60)
    destino_credito: str | None = Field(default=None, max_length=80)
    plazo_deseado_meses: int | None = Field(default=None, ge=1)
    # Token de la sesión de captura remota (paso 3): enlaza las evidencias
    # documentales subidas por el cliente a esta solicitud.
    sesion_captura: str | None = Field(default=None, max_length=64)


class CrearSolicitudResponse(BaseModel):
    id_solicitud: UUID
    # Lo genera la base de datos (secuencia en schema.sql); puede venir
    # vacío en motores sin esa secuencia (p. ej. SQLite de pruebas).
    num_solicitud: int | None
    estado: str


class OfertaResponse(BaseModel):
    id_oferta: int
    id_aliado_producto: int
    elegible: bool
    motivo_no_elegible: str | None
    seleccionada: bool
    tasa_ofrecida: Decimal | None = None
    plazo_ofrecido: int | None = None
    cuota_mensual: Decimal | None = None
    monto_aprobado: Decimal | None = None


class VehiculoFinanciadoRequest(BaseModel):
    """Vehículo que financia el crédito: se captura al aceptar la oferta
    (formalización) y queda persistido para el desembolso."""

    producto_a_financiar: str = "Motocicleta"
    marca: str | None = Field(default=None, max_length=100)
    referencia: str | None = Field(default=None, max_length=120)
    modelo: str | None = Field(default=None, max_length=30)
    color: str | None = Field(default=None, max_length=60)
    valor_moto_iva: Decimal | None = Field(default=None, ge=0)
    descuento: Decimal | None = Field(default=None, ge=0)
    descuento_pct: Decimal | None = Field(default=None, ge=0, le=100)
    accesorios: Decimal | None = Field(default=None, ge=0)
    matricula: Decimal | None = Field(default=None, ge=0)
    soat: Decimal | None = Field(default=None, ge=0)
    aval_pct: Decimal | None = Field(default=None, ge=0, le=100)


class SeleccionarOfertaRequest(BaseModel):
    id_oferta: int
    """Monto que el cliente decide tomar; <= monto_aprobado de la oferta.
    Si se omite se toma el monto aprobado completo."""
    monto: Decimal | None = Field(default=None, gt=0)
    """Plazo pactado en meses; <= plazo_ofrecido de la oferta.
    Si se omite se conserva el plazo ofrecido."""
    plazo: int | None = Field(default=None, gt=0)
    """Datos del vehículo a financiar, capturados en la formalización."""
    vehiculo: VehiculoFinanciadoRequest | None = None


class EnviarEstudioRequest(BaseModel):
    """El asesor escala una solicitud rechazada a estudio manual.

    La solicitud pasa a `en_revision` y el comité la resuelve con
    /resolver. El comentario queda en `descripcion_estado`.
    """

    comentario: str | None = Field(default=None, max_length=500)


class ResolverSolicitudRequest(BaseModel):
    """Decisión del comité sobre una solicitud en revisión (causales E/RC).

    El motor deja la solicitud en `en_revision`; el comité la cierra
    aprobando o rechazando manualmente. El comentario queda en
    `descripcion_estado` para trazabilidad.
    """

    decision: Literal["aprobado", "rechazado"]
    comentario: str | None = Field(default=None, max_length=500)
    """Monto que el comité decide aprobar; si se omite se usa el cupo
    calculado por el motor en la evaluación vigente."""
    monto_aprobado: Decimal | None = Field(default=None, gt=0)
    """Plazo en meses de la oferta generada por el comité; si se omite
    se usa el plazo del cupo o el deseado en la solicitud."""
    plazo_meses: int | None = Field(default=None, ge=1)


class EvaluacionResumenSolicitud(BaseModel):
    """La evaluación vigente de la solicitud (una sola versión activa)."""

    id_evaluacion: int
    version: int
    score: Decimal | None
    perfil_score: str | None
    perfil_ingreso: str | None
    decision_interna: str | None
    endeudamiento: Decimal | None
    capacidad_pago: Decimal | None
    cupo_sugerido: Decimal | None
    plazo_cupo: int | None


class SolicitudResumenResponse(BaseModel):
    id_solicitud: UUID
    num_solicitud: int | None
    fecha_hora: datetime
    estado: str
    decision: str | None
    nombre_cliente: str
    num_cedula: str
    tipo_documento: str | None
    ocupacion: str | None
    linea_credito: str | None
    destino_credito: str | None
    plazo_deseado_meses: int | None
    evaluacion: EvaluacionResumenSolicitud | None


class CausalSolicitudResponse(BaseModel):
    codigo: str
    descripcion: str
    activa: bool


class DesembolsoResponse(BaseModel):
    id_desembolso: int
    num_desembolso: str | None
    id_credito: int
    estado: str
    capital: Decimal
    cuota: Decimal
    plazo: int
    tasa: Decimal
    emisor: str
    receptor: str
    referencia_pago: str | None
    fecha_desembolso: datetime | None


class SolicitudDetalleResponse(SolicitudResumenResponse):
    datos_laborales: dict | None
    contacto_vivienda: dict | None
    causales: list[CausalSolicitudResponse]
    ofertas: list[OfertaResponse]
    desembolso: DesembolsoResponse | None = None


class VehiculoDesembolsoRequest(BaseModel):
    """Vehículo a financiar; solo es obligatorio la primera vez que se
    formaliza la solicitud (las columnas NOT NULL del esquema ya vienen
    de la oferta seleccionada)."""

    producto_a_financiar: str = "Motocicleta"
    marca: str | None = None
    referencia: str | None = None
    modelo: str | None = None
    color: str | None = None
    valor_moto_iva: Decimal | None = Field(default=None, ge=0)


class RegistrarDesembolsoRequest(BaseModel):
    """Confirmación del desembolso: cuenta de ahorros del cliente
    (receptor) y referencia de la transferencia del aliado."""

    codigo_ach_banco: str = Field(min_length=1, max_length=10)
    numero_cuenta_cliente: str = Field(min_length=4, max_length=40)
    titular_cuenta: str | None = Field(default=None, max_length=180)
    referencia_pago: str | None = Field(default=None, max_length=80)
    vehiculo: VehiculoDesembolsoRequest | None = None
