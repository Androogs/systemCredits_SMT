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
    # Datos de la cédula confirmados en la revisión: los usan los
    # documentos de legalización ("expedida en…", fecha de expedición).
    fecha_expedicion: date | None = None
    ciudad_expedicion: str | None = Field(default=None, max_length=200)
    ciudad_nacimiento: str | None = Field(default=None, max_length=200)


class DatosLaboralesInput(BaseModel):
    tipo_contrato: TipoContrato | None = None
    meses_continuidad: int | None = Field(default=None, ge=0)
    ingreso_mensual: Decimal | None = Field(default=None, ge=0)
    otros_ingresos: Decimal = Field(default=Decimal(0), ge=0)
    anios_camara_comercio: Decimal | None = Field(default=None, ge=0)
    # Empleador o entidad pagadora capturado en originación: precarga el
    # nombre de empresa del formulario de formalización.
    nombre_empresa: str | None = Field(default=None, max_length=200)


class ContactoViviendaInput(BaseModel):
    estrato: int | None = Field(default=None, ge=0, le=6)
    personas_a_cargo: int | None = Field(default=None, ge=0)
    tipo_vivienda: str | None = None
    # Canales de contacto del cliente: notificaciones (email) y OTP.
    correo: str | None = Field(default=None, max_length=320)
    telefono: str | None = Field(default=None, max_length=40)


class ConsentimientoInput(BaseModel):
    """Aceptación del consentimiento Habeas Data en el paso 2. El
    backend sella la versión del texto vigente y su hash; aquí solo
    viaja el hecho de la aceptación."""

    aceptado: bool = False


class CrearSolicitudRequest(BaseModel):
    cliente: ClienteInput
    datos_laborales: DatosLaboralesInput
    contacto_vivienda: ContactoViviendaInput = ContactoViviendaInput()
    moneda: str = "COP"
    consentimiento: ConsentimientoInput | None = None
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
    fecha_vigencia: datetime | None = None
    expirada: bool = False


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


class DatosFormalizacionRequest(BaseModel):
    """Información adicional del cliente capturada en la formalización:
    se pide después de los datos del vehículo y antes de enviar el OTP.

    La dirección llega descompuesta (vía + números + letras + sector) y el
    servicio la compone en una sola cadena para `direccion`."""

    # Residencia — dirección descompuesta
    via_principal: str | None = Field(default=None, max_length=30)
    numero_via: str | None = Field(default=None, max_length=10)
    letra_via: str | None = Field(default=None, max_length=10)
    sector: str | None = Field(default=None, max_length=30)
    numero_cruce: str | None = Field(default=None, max_length=10)
    letra_cruce: str | None = Field(default=None, max_length=10)
    numero_final: str | None = Field(default=None, max_length=10)
    otras_caracteristicas: str | None = Field(default=None, max_length=120)
    barrio: str | None = Field(default=None, max_length=120)
    ciudad: str | None = Field(default=None, max_length=200)
    estrato: int | None = Field(default=None, ge=0, le=6)
    tipo_vivienda: str | None = Field(default=None, max_length=50)
    zona_rural: bool | None = None
    # Información personal
    estado_civil: str | None = Field(default=None, max_length=40)
    personas_a_cargo: int | None = Field(default=None, ge=0)
    num_hijos: int | None = Field(default=None, ge=0)
    es_cabeza_familia: bool | None = None
    # Información financiera (bienes del cliente)
    cuenta_bienes_raices: bool | None = None
    cuenta_vehiculo: bool | None = None
    tiene_moto: bool | None = None
    tiene_carro: bool | None = None
    primera_moto: bool | None = None
    # "¿Qué está financiando?" — TRUE cuando financia la moto con el crédito.
    estoy_financiando: bool | None = None
    # Información laboral
    nombre_empresa: str | None = Field(default=None, max_length=200)
    ciudad_empresa: str | None = Field(default=None, max_length=200)
    fecha_ingreso: date | None = None
    nivel_educativo: str | None = Field(default=None, max_length=100)
    profesion: str | None = Field(default=None, max_length=120)
    cargo: str | None = Field(default=None, max_length=120)
    actividad_comercial: str | None = Field(default=None, max_length=180)


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
    descripcion_estado: str | None = None
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


class ConsentimientoResponse(BaseModel):
    """Registro de una aceptación Habeas Data (Ley 1581)."""

    version_texto: str
    hash_texto: str
    canal: str
    ip: str | None
    fecha_aceptacion: datetime


class SolicitudDetalleResponse(SolicitudResumenResponse):
    datos_laborales: dict | None
    contacto_vivienda: dict | None
    causales: list[CausalSolicitudResponse]
    ofertas: list[OfertaResponse]
    desembolso: DesembolsoResponse | None = None
    consentimientos: list[ConsentimientoResponse] = []


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


class CancelarSolicitudRequest(BaseModel):
    """Anulación de la solicitud: el motivo queda en el historial de
    estados (el trigger de Postgres lo persiste como `motivo`)."""

    motivo: str = Field(min_length=3, max_length=500)


class GenerarOtpRequest(BaseModel):
    """Emisión de un OTP para la acción indicada (firma del pagaré).

    canal='whatsapp' envía por plantilla WATI al celular del cliente;
    sin teléfono válido o si el envío falla se cae a email."""

    accion: str = Field(default="firma_pagare", max_length=100)
    canal: Literal["email", "whatsapp"] = "whatsapp"


class GenerarOtpResponse(BaseModel):
    id_otp: int
    expira_en_segundos: int
    # Canal por el que realmente salió el código (whatsapp cayó a email
    # cuando el teléfono no era válido o WATI falló).
    canal: Literal["email", "whatsapp"]
    destino: str | None
    estado_envio: str
    # Solo en environment='demo': el código viaja en la respuesta para
    # mostrarlo en pantalla, sin dependencia de un proveedor externo.
    codigo_demo: str | None = None


class VerificarOtpRequest(BaseModel):
    accion: str = Field(default="firma_pagare", max_length=100)
    codigo: str = Field(min_length=6, max_length=6)


class VerificarOtpResponse(BaseModel):
    verificado: bool
    uuid_firma: UUID | None = None
