"""Alta de solicitudes en el esquema SUMOTO y gestión de ofertas."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.db_models.models import (
    ConsentimientoHabeas,
    DatosLaborales,
    ProductoVehiculo,
    SolicitudContactoVivienda,
)
from backend.models.enums import TIPOS_ID_PERSONA_JURIDICA
from backend.models.solicitud_models import (
    CausalSolicitudResponse,
    ConsentimientoResponse,
    CrearSolicitudRequest,
    CrearSolicitudResponse,
    DatosFormalizacionRequest,
    DesembolsoResponse,
    EmbudoAliadoResponse,
    EtapaEmbudoResponse,
    EvaluacionResumenSolicitud,
    MetricasEmbudoResponse,
    OfertaResponse,
    SeleccionarOfertaRequest,
    SolicitudDetalleResponse,
    SolicitudResumenResponse,
)
from backend.repositories.solicitud_repository import SolicitudRepository, oferta_expirada
from backend.services.documento_service import DocumentoService
from backend.services.mapeos_db import OCUPACION_A_DB, TIPO_CONTRATO_A_DB
from backend.services.motor_exceptions import ConflictoEstadoError, SolicitudNoEncontradaError
from backend.services.textos_legales import VERSION_HABEAS_DATA, hash_habeas

logger = logging.getLogger(__name__)


def _componer_direccion(payload: "DatosFormalizacionRequest") -> str | None:
    """Compone la dirección colombiana a partir de los campos capturados:
    'Calle 48A Norte No. 101B-40, Casa 10'."""
    principal = " ".join(
        p
        for p in (
            payload.via_principal,
            payload.numero_via,
            payload.letra_via,
            payload.sector,
        )
        if p
    ).strip()
    cruce = " ".join(
        p for p in (payload.numero_cruce, payload.letra_cruce) if p
    ).strip()
    if cruce or payload.numero_final:
        tramo_cruce = "-".join(
            p for p in (f"No. {cruce}".rstrip(), payload.numero_final) if p
        )
        direccion = " ".join(p for p in (principal, tramo_cruce) if p)
    else:
        direccion = principal
    if payload.otras_caracteristicas:
        direccion = (
            f"{direccion}, {payload.otras_caracteristicas}"
            if direccion
            else payload.otras_caracteristicas
        )
    return direccion or None


def _vigente(filas):
    """La fila vigente más reciente de una colección versionada."""
    vigentes = [f for f in filas if f.vigente]
    if not vigentes:
        return None
    return max(vigentes, key=lambda f: f.version)


def _evaluacion_resumen(solicitud) -> EvaluacionResumenSolicitud | None:
    evaluacion = _vigente(solicitud.evaluaciones)
    if evaluacion is None:
        return None
    capacidad = _vigente(solicitud.capacidades_pago)
    return EvaluacionResumenSolicitud(
        id_evaluacion=evaluacion.id_evaluacion,
        version=evaluacion.version,
        score=evaluacion.score,
        perfil_score=evaluacion.perfil_score,
        perfil_ingreso=evaluacion.perfil_ingreso,
        decision_interna=evaluacion.decision_interna,
        endeudamiento=evaluacion.endeudamiento,
        capacidad_pago=evaluacion.capacidad_pago,
        cupo_sugerido=(
            (capacidad.cupo_aprobado or capacidad.cupo_calculado)
            if capacidad is not None
            else None
        ),
        plazo_cupo=capacidad.plazo_cupo if capacidad is not None else None,
    )


def _resumen(solicitud) -> SolicitudResumenResponse:
    cliente = solicitud.cliente
    return SolicitudResumenResponse(
        id_solicitud=solicitud.id_solicitud,
        num_solicitud=solicitud.num_solicitud,
        fecha_hora=solicitud.fecha_hora,
        estado=solicitud.estado,
        descripcion_estado=solicitud.descripcion_estado,
        decision=solicitud.decision,
        nombre_cliente=cliente.nombre_completo if cliente else "",
        num_cedula=cliente.num_cedula if cliente else "",
        tipo_documento=cliente.tipo_documento if cliente else None,
        ocupacion=cliente.ocupacion if cliente else None,
        linea_credito=solicitud.linea_credito,
        destino_credito=solicitud.destino_credito,
        plazo_deseado_meses=solicitud.plazo_deseado_meses,
        fecha_hora_firma=solicitud.fecha_hora_firma,
        evaluacion=_evaluacion_resumen(solicitud),
    )


def _desembolso_response(d) -> DesembolsoResponse | None:
    if d is None:
        return None
    return DesembolsoResponse(
        id_desembolso=d.id_desembolso,
        num_desembolso=d.num_desembolso,
        id_credito=d.id_credito,
        estado=d.estado,
        capital=d.capital,
        cuota=d.cuota,
        plazo=d.plazo,
        tasa=d.tasa,
        emisor=d.emisor,
        receptor=d.receptor,
        referencia_pago=d.referencia_pago,
        fecha_desembolso=d.fecha_desembolso,
    )


def _oferta_response(o) -> OfertaResponse:
    return OfertaResponse(
        id_oferta=o.id_oferta,
        id_aliado_producto=o.id_aliado_producto,
        elegible=o.elegible,
        motivo_no_elegible=o.motivo_no_elegible,
        seleccionada=o.seleccionada,
        tasa_ofrecida=o.tasa_ofrecida,
        plazo_ofrecido=o.plazo_ofrecido,
        cuota_mensual=o.cuota_mensual,
        monto_aprobado=o.monto_aprobado,
        fecha_vigencia=o.fecha_vigencia,
        expirada=oferta_expirada(o),
    )


class SolicitudService:
    def __init__(self, db: Session) -> None:
        self.repo = SolicitudRepository(db)
        self._db = db

    def _datos_cliente(self, cliente_in) -> dict:
        """Columnas de `cliente` a partir del input de radicación:
        resuelve tipo de documento, ocupación (catálogo DB) y ciudades
        (texto → FK `ciudad`)."""
        datos_cliente = cliente_in.model_dump(mode="python", exclude={"num_cedula"})
        datos_cliente["tipo_documento"] = cliente_in.tipo_documento.value
        datos_cliente["ocupacion"] = OCUPACION_A_DB[cliente_in.ocupacion]
        datos_cliente["es_persona_natural"] = cliente_in.tipo_documento not in TIPOS_ID_PERSONA_JURIDICA
        # Las ciudades llegan como texto ("Palmira, Valle del Cauca") y
        # se resuelven al catálogo `ciudad` (FK).
        ciudad_exp = self.repo.obtener_o_crear_ciudad(cliente_in.ciudad_expedicion)
        ciudad_nac = self.repo.obtener_o_crear_ciudad(cliente_in.ciudad_nacimiento)
        datos_cliente.pop("ciudad_expedicion")
        datos_cliente.pop("ciudad_nacimiento")
        datos_cliente["id_ciudad_expedicion"] = ciudad_exp.id_ciudad if ciudad_exp else None
        datos_cliente["id_ciudad_nacimiento"] = ciudad_nac.id_ciudad if ciudad_nac else None
        return datos_cliente

    def _rellenar_cliente(self, cliente, datos_cliente: dict) -> None:
        """Cliente ya existente: rellena los datos de cédula que falten
        (no pisa valores previos)."""
        if cliente.fecha_expedicion is None:
            cliente.fecha_expedicion = datos_cliente["fecha_expedicion"]
        if cliente.id_ciudad_expedicion is None:
            cliente.id_ciudad_expedicion = datos_cliente["id_ciudad_expedicion"]
        if cliente.id_ciudad_nacimiento is None:
            cliente.id_ciudad_nacimiento = datos_cliente["id_ciudad_nacimiento"]
        # La ocupación es dato de la situación laboral actual, no de
        # identidad: cada solicitud nueva actualiza la del cliente para
        # que el motor evalúe con la matriz correcta (empleado /
        # independiente / pensionado / FFMM).
        if cliente.ocupacion != datos_cliente["ocupacion"]:
            cliente.ocupacion = datos_cliente["ocupacion"]

    def _datos_laborales_db(self, laborales_in) -> dict:
        datos_laborales = laborales_in.model_dump(mode="python")
        if laborales_in.tipo_contrato is not None:
            datos_laborales["tipo_contrato"] = TIPO_CONTRATO_A_DB[laborales_in.tipo_contrato]
        return datos_laborales

    def crear(
        self, req: CrearSolicitudRequest, ip: str | None = None
    ) -> CrearSolicitudResponse:
        datos_cliente = self._datos_cliente(req.cliente)
        cliente = self.repo.obtener_o_crear_cliente(req.cliente.num_cedula, datos_cliente)
        self._rellenar_cliente(cliente, datos_cliente)
        solicitud = self.repo.crear_solicitud(
            id_cliente=cliente.id_cliente,
            moneda=req.moneda,
            datos_laborales=self._datos_laborales_db(req.datos_laborales),
            contacto_vivienda=req.contacto_vivienda.model_dump(),
            datos_solicitud={
                "linea_credito": req.linea_credito,
                "destino_credito": req.destino_credito,
                "plazo_deseado_meses": req.plazo_deseado_meses,
            },
        )
        if req.sesion_captura:
            from backend.services.evidencia_service import EvidenciaService

            EvidenciaService(self._db).enlazar_solicitud(
                req.sesion_captura, solicitud.id_solicitud
            )
        if req.consentimiento and req.consentimiento.aceptado:
            self.registrar_consentimiento(solicitud.id_solicitud, "web_asesor", ip)
        return CrearSolicitudResponse(
            id_solicitud=solicitud.id_solicitud,
            num_solicitud=solicitud.num_solicitud,
            estado=solicitud.estado,
        )

    def actualizar(
        self, id_solicitud: uuid.UUID, req: CrearSolicitudRequest, ip: str | None = None
    ) -> CrearSolicitudResponse:
        """Re-diligencia la radicación cuando "continuar" encuentra pasos
        pendientes (consentimiento, evidencias u otros datos): upsert
        sobre el mismo registro en vez de duplicar la solicitud. Solo
        aplica antes de la primera evaluación —o sobre una rechazada,
        donde corregir datos mal capturados (p. ej. la ocupación) y
        re-evaluar es la ruta de recuperación; nunca sobre una aprobada,
        firmada, desembolsada o cancelada."""
        solicitud = self.repo.obtener_detalle(id_solicitud)
        if solicitud is None:
            raise SolicitudNoEncontradaError(f"No existe la solicitud {id_solicitud}")
        editable = solicitud.decision is None or (
            solicitud.decision == "rechazado" and solicitud.estado == "rechazada"
        )
        if not editable:
            raise ConflictoEstadoError(
                "La solicitud ya fue evaluada; los cambios van por la ruta de reevaluación."
            )
        self._rellenar_cliente(solicitud.cliente, self._datos_cliente(req.cliente))

        datos_laborales = self._datos_laborales_db(req.datos_laborales)
        if solicitud.datos_laborales is None:
            self._db.add(
                DatosLaborales(id_solicitud=solicitud.id_solicitud, **datos_laborales)
            )
        else:
            for campo, valor in datos_laborales.items():
                setattr(solicitud.datos_laborales, campo, valor)

        contacto = req.contacto_vivienda.model_dump(mode="python")
        if solicitud.contacto_vivienda is None:
            self._db.add(
                SolicitudContactoVivienda(
                    id_solicitud=solicitud.id_solicitud, **contacto
                )
            )
        else:
            for campo, valor in contacto.items():
                setattr(solicitud.contacto_vivienda, campo, valor)

        for campo in ("linea_credito", "destino_credito", "plazo_deseado_meses"):
            valor = getattr(req, campo)
            if valor is not None:
                setattr(solicitud, campo, valor)
        if req.sesion_captura:
            from backend.services.evidencia_service import EvidenciaService

            EvidenciaService(self._db).enlazar_solicitud(
                req.sesion_captura, solicitud.id_solicitud
            )
        # Solo registra la prueba de consentimiento cuando aún no hay una:
        # re-guardar no debe apilar aceptaciones duplicadas.
        if (
            req.consentimiento
            and req.consentimiento.aceptado
            and not solicitud.consentimientos
        ):
            self.registrar_consentimiento(solicitud.id_solicitud, "web_asesor", ip)
        self._db.flush()
        return CrearSolicitudResponse(
            id_solicitud=solicitud.id_solicitud,
            num_solicitud=solicitud.num_solicitud,
            estado=solicitud.estado,
        )

    def registrar_consentimiento(
        self, id_solicitud: uuid.UUID, canal: str, ip: str | None = None
    ) -> ConsentimientoHabeas:
        """Persiste la prueba del consentimiento Habeas Data con la
        versión del texto vigente y su SHA-256 (textos_legales)."""
        consentimiento = ConsentimientoHabeas(
            id_solicitud=id_solicitud,
            version_texto=VERSION_HABEAS_DATA,
            hash_texto=hash_habeas(),
            canal=canal,
            ip=ip,
        )
        self._db.add(consentimiento)
        self._db.flush()
        return consentimiento

    def cancelar(
        self, id_solicitud: uuid.UUID, motivo: str
    ) -> SolicitudResumenResponse:
        """Anula la solicitud. Válida en cualquier estado salvo
        `desembolsada` (el dinero ya giró) y `cancelada` (idempotente
        negativo: cancelar dos veces es conflicto). El trigger
        `trg_solicitud_estado_historial` deja quién/cuándo/por qué en
        solicitud_estado_historial (motivo ← descripcion_estado)."""
        solicitud = self.repo.obtener_detalle(id_solicitud)
        if solicitud is None:
            raise SolicitudNoEncontradaError(f"No existe la solicitud {id_solicitud}")
        if solicitud.estado == "desembolsada":
            raise ConflictoEstadoError(
                "La solicitud ya fue desembolsada; no se puede cancelar. "
                "El crédito debe manejarse por el proceso de cartera."
            )
        if solicitud.estado == "cancelada":
            raise ConflictoEstadoError("La solicitud ya está cancelada.")
        solicitud.estado = "cancelada"
        solicitud.descripcion_estado = f"Cancelada: {motivo.strip()}"
        self._db.flush()
        return _resumen(solicitud)

    def listar(
        self,
        *,
        limite: int = 50,
        offset: int = 0,
        estado: str | None = None,
        decision: str | None = None,
        busqueda: str | None = None,
    ) -> list[SolicitudResumenResponse]:
        filas = self.repo.listar(
            limite=limite,
            offset=offset,
            estado=estado,
            decision=decision,
            busqueda=busqueda,
        )
        return [_resumen(s) for s in filas]

    def metricas_embudo(
        self,
        desde: datetime | None = None,
        hasta: datetime | None = None,
    ) -> MetricasEmbudoResponse:
        """Conversión del embudo originación → desembolso. Las etapas se
        derivan de los hitos persistidos: decisión del motor, oferta
        seleccionada (aliado), firma OTP y estado desembolsada."""
        c = self.repo.conteos_embudo(desde=desde, hasta=hasta)
        radicadas = c["radicadas"] or 1  # evita división por cero
        etapas = [
            ("radicadas", "Radicadas", c["radicadas"]),
            ("evaluadas", "Evaluadas", c["evaluadas"]),
            ("aprobadas", "Aprobadas", c["aprobadas"]),
            ("formalizadas", "Formalizadas (firmadas)", c["formalizadas"]),
            ("desembolsadas", "Desembolsadas", c["desembolsadas"]),
        ]
        return MetricasEmbudoResponse(
            generado_en=datetime.now(UTC),
            radicadas=c["radicadas"],
            canceladas=c["canceladas"],
            etapas=[
                EtapaEmbudoResponse(
                    clave=clave,
                    etiqueta=etiqueta,
                    total=total,
                    pct=round(total * 100 / radicadas, 1),
                )
                for clave, etiqueta, total in etapas
            ],
            por_estado=c["por_estado"],
            por_aliado=[
                EmbudoAliadoResponse(**fila)
                for fila in self.repo.conteos_por_aliado(desde=desde, hasta=hasta)
            ],
        )

    def detalle(self, id_solicitud: uuid.UUID) -> SolicitudDetalleResponse:
        solicitud = self.repo.obtener_detalle(id_solicitud)
        if solicitud is None:
            raise SolicitudNoEncontradaError(f"No existe la solicitud {id_solicitud}")
        resumen = _resumen(solicitud)
        laborales = solicitud.datos_laborales
        contacto = solicitud.contacto_vivienda
        return SolicitudDetalleResponse(
            **resumen.model_dump(),
            fecha_nacimiento=solicitud.cliente.fecha_nacimiento,
            datos_laborales=(
                {
                    "tipo_contrato": laborales.tipo_contrato,
                    "meses_continuidad": laborales.meses_continuidad,
                    "ingreso_mensual": laborales.ingreso_mensual,
                    "otros_ingresos": laborales.otros_ingresos,
                    "anios_camara_comercio": laborales.anios_camara_comercio,
                    "nombre_empresa": laborales.nombre_empresa,
                    "ciudad_empresa": (
                        ", ".join(
                            p
                            for p in (
                                laborales.ciudad_empresa.nombre,
                                laborales.ciudad_empresa.departamento,
                            )
                            if p
                        )
                        if laborales.ciudad_empresa
                        else None
                    ),
                    "fecha_ingreso": (
                        laborales.fecha_ingreso.isoformat()
                        if laborales.fecha_ingreso
                        else None
                    ),
                    "nivel_educativo": laborales.nivel_educativo,
                    "profesion": laborales.profesion,
                    "cargo": laborales.cargo,
                    "actividad_comercial": laborales.actividad_comercial,
                }
                if laborales
                else None
            ),
            contacto_vivienda=(
                {
                    "estrato": contacto.estrato,
                    "personas_a_cargo": contacto.personas_a_cargo,
                    "tipo_vivienda": contacto.tipo_vivienda,
                    "correo": contacto.correo,
                    "telefono": contacto.telefono,
                    "direccion": contacto.direccion,
                    "barrio": contacto.barrio,
                    "ciudad": (
                        ", ".join(
                            p
                            for p in (
                                contacto.ciudad.nombre,
                                contacto.ciudad.departamento,
                            )
                            if p
                        )
                        if contacto.ciudad
                        else None
                    ),
                    "zona_rural": contacto.zona_rural,
                    "estado_civil": contacto.estado_civil,
                    "num_hijos": contacto.num_hijos,
                    "es_cabeza_familia": contacto.es_cabeza_familia,
                    "cuenta_bienes_raices": contacto.cuenta_bienes_raices,
                    "cuenta_vehiculo": contacto.cuenta_vehiculo,
                    "tiene_moto": contacto.tiene_moto,
                    "tiene_carro": contacto.tiene_carro,
                    "primera_moto": contacto.primera_moto,
                    "estoy_financiando": contacto.estoy_financiando,
                }
                if contacto
                else None
            ),
            causales=[
                CausalSolicitudResponse(
                    codigo=c.codigo,
                    descripcion=c.descripcion,
                    activa=c.activa,
                )
                for c in solicitud.causales
            ],
            ofertas=[_oferta_response(o) for o in solicitud.ofertas],
            consentimientos=[
                ConsentimientoResponse(
                    version_texto=c.version_texto,
                    hash_texto=c.hash_texto,
                    canal=c.canal,
                    ip=c.ip,
                    fecha_aceptacion=c.fecha_aceptacion,
                )
                for c in sorted(
                    solicitud.consentimientos, key=lambda c: c.fecha_aceptacion
                )
            ],
            desembolso=_desembolso_response(
                self.repo.obtener_desembolso(id_solicitud)
            ),
        )

    def ofertas(self, id_solicitud: uuid.UUID) -> list[OfertaResponse]:
        return [_oferta_response(o) for o in self.repo.obtener_ofertas(id_solicitud)]

    def seleccionar_oferta(self, id_solicitud: uuid.UUID, payload: SeleccionarOfertaRequest) -> OfertaResponse:
        oferta = self.repo.seleccionar_oferta(
            id_solicitud,
            payload.id_oferta,
            monto=payload.monto,
            plazo=payload.plazo,
        )
        if payload.vehiculo is not None:
            self._guardar_vehiculo(id_solicitud, payload.vehiculo)
        self._db.flush()
        solicitud = self.repo.obtener_detalle(id_solicitud)
        if solicitud is not None and solicitud.fecha_hora_firma is not None:
            # Si el cliente ya firmó, el paquete legal se regenera con el
            # monto y vehículo finales para que no quede desactualizado.
            # El SAVEPOINT aísla el fallo para no perder la selección.
            try:
                with self._db.begin_nested():
                    DocumentoService(self._db).generar_paquete(id_solicitud)
            except Exception:
                logger.exception(
                    "No se pudo regenerar el paquete legal de la solicitud %s",
                    id_solicitud,
                )
        return _oferta_response(oferta)

    def guardar_datos_formalizacion(
        self, id_solicitud: uuid.UUID, payload: DatosFormalizacionRequest
    ) -> None:
        """Información del cliente capturada en la formalización (antes del
        OTP). Upsert sobre contacto_vivienda y datos_laborales; solo pisa
        los campos que llegan con valor."""
        solicitud = self.repo.obtener_detalle(id_solicitud)
        if solicitud is None:
            raise SolicitudNoEncontradaError(f"No existe la solicitud {id_solicitud}")

        contacto = solicitud.contacto_vivienda
        if contacto is None:
            contacto = SolicitudContactoVivienda(id_solicitud=id_solicitud)
            self._db.add(contacto)

        direccion = _componer_direccion(payload)
        if direccion:
            contacto.direccion = direccion
        if payload.ciudad and payload.ciudad.strip():
            ciudad = self.repo.obtener_o_crear_ciudad(payload.ciudad)
            contacto.id_ciudad = ciudad.id_ciudad if ciudad else None
        for campo in (
            "barrio",
            "estrato",
            "tipo_vivienda",
            "zona_rural",
            "estado_civil",
            "personas_a_cargo",
            "num_hijos",
            "es_cabeza_familia",
            "cuenta_bienes_raices",
            "cuenta_vehiculo",
            "tiene_moto",
            "tiene_carro",
            "primera_moto",
            "estoy_financiando",
        ):
            valor = getattr(payload, campo, None)
            if valor is not None:
                setattr(contacto, campo, valor)

        laborales = solicitud.datos_laborales
        if laborales is None:
            laborales = DatosLaborales(id_solicitud=id_solicitud, otros_ingresos=0)
            self._db.add(laborales)
        if payload.ciudad_empresa and payload.ciudad_empresa.strip():
            ciudad_empresa = self.repo.obtener_o_crear_ciudad(payload.ciudad_empresa)
            laborales.id_ciudad_empresa = (
                ciudad_empresa.id_ciudad if ciudad_empresa else None
            )
        for campo in (
            "nombre_empresa",
            "fecha_ingreso",
            "nivel_educativo",
            "profesion",
            "cargo",
            "actividad_comercial",
        ):
            valor = getattr(payload, campo, None)
            if valor is not None:
                setattr(laborales, campo, valor)

        self._db.flush()

    def _guardar_vehiculo(self, id_solicitud: uuid.UUID, datos) -> None:
        """Persiste el vehículo financiado capturado en la formalización.

        Desde la migración 0010 el desglose de la hoja de negocio
        (descuento, accesorios, matrícula, SOAT, impuestos, % aval) queda en
        columnas de producto_vehiculo — alimenta el documento
        'Solicitud de crédito' del paquete de legalización."""
        solicitud = self.repo.obtener_detalle(id_solicitud)
        if solicitud is None:
            return
        vehiculo = (
            self._db.query(ProductoVehiculo)
            .filter(ProductoVehiculo.id_solicitud == id_solicitud)
            .order_by(ProductoVehiculo.id_vehiculo.desc())
            .first()
        )
        if vehiculo is None:
            vehiculo = ProductoVehiculo(id_solicitud=id_solicitud, producto_a_financiar="Motocicleta")
            self._db.add(vehiculo)
        vehiculo.producto_a_financiar = datos.producto_a_financiar or vehiculo.producto_a_financiar
        for campo, atributo in (
            ("marca", "marca"),
            ("referencia", "referencia"),
            ("modelo", "modelo"),
            ("color", "color"),
            ("valor_moto_iva", "valor_moto_iva"),
            ("descuento", "descuento_pesos"),
            ("descuento_pct", "descuento_pct"),
            ("accesorios", "accesorios"),
            ("matricula", "matricula"),
            ("soat", "soat"),
            ("impuestos", "impuestos"),
            ("aval_pct", "aval_pct"),
        ):
            valor = getattr(datos, campo, None)
            if valor is not None:
                setattr(vehiculo, atributo, valor)
