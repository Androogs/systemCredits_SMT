"""Alta de solicitudes en el esquema SUMOTO y gestión de ofertas."""

import uuid

from sqlalchemy.orm import Session

from backend.models.enums import TIPOS_ID_PERSONA_JURIDICA
from backend.models.solicitud_models import (
    CausalSolicitudResponse,
    CrearSolicitudRequest,
    CrearSolicitudResponse,
    DesembolsoResponse,
    EvaluacionResumenSolicitud,
    OfertaResponse,
    SeleccionarOfertaRequest,
    SolicitudDetalleResponse,
    SolicitudResumenResponse,
)
from backend.repositories.solicitud_repository import SolicitudRepository
from backend.services.mapeos_db import OCUPACION_A_DB, TIPO_CONTRATO_A_DB
from backend.services.motor_exceptions import SolicitudNoEncontradaError


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
        decision=solicitud.decision,
        nombre_cliente=cliente.nombre_completo if cliente else "",
        num_cedula=cliente.num_cedula if cliente else "",
        tipo_documento=cliente.tipo_documento if cliente else None,
        ocupacion=cliente.ocupacion if cliente else None,
        linea_credito=solicitud.linea_credito,
        destino_credito=solicitud.destino_credito,
        plazo_deseado_meses=solicitud.plazo_deseado_meses,
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
    )


class SolicitudService:
    def __init__(self, db: Session) -> None:
        self.repo = SolicitudRepository(db)
        self._db = db

    def crear(self, req: CrearSolicitudRequest) -> CrearSolicitudResponse:
        datos_cliente = req.cliente.model_dump(mode="python", exclude={"num_cedula"})
        datos_cliente["tipo_documento"] = req.cliente.tipo_documento.value
        datos_cliente["ocupacion"] = OCUPACION_A_DB[req.cliente.ocupacion]
        datos_cliente["es_persona_natural"] = req.cliente.tipo_documento not in TIPOS_ID_PERSONA_JURIDICA
        cliente = self.repo.obtener_o_crear_cliente(req.cliente.num_cedula, datos_cliente)
        # La ocupación es dato de la situación laboral actual, no de
        # identidad: cada solicitud nueva actualiza la del cliente para
        # que el motor evalúe con la matriz correcta (empleado /
        # independiente / pensionado / FFMM).
        if cliente.ocupacion != datos_cliente["ocupacion"]:
            cliente.ocupacion = datos_cliente["ocupacion"]
        datos_laborales = req.datos_laborales.model_dump(mode="python")
        if req.datos_laborales.tipo_contrato is not None:
            datos_laborales["tipo_contrato"] = TIPO_CONTRATO_A_DB[req.datos_laborales.tipo_contrato]
        solicitud = self.repo.crear_solicitud(
            id_cliente=cliente.id_cliente,
            moneda=req.moneda,
            datos_laborales=datos_laborales,
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
        return CrearSolicitudResponse(
            id_solicitud=solicitud.id_solicitud,
            num_solicitud=solicitud.num_solicitud,
            estado=solicitud.estado,
        )

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

    def detalle(self, id_solicitud: uuid.UUID) -> SolicitudDetalleResponse:
        solicitud = self.repo.obtener_detalle(id_solicitud)
        if solicitud is None:
            raise SolicitudNoEncontradaError(f"No existe la solicitud {id_solicitud}")
        resumen = _resumen(solicitud)
        laborales = solicitud.datos_laborales
        contacto = solicitud.contacto_vivienda
        return SolicitudDetalleResponse(
            **resumen.model_dump(),
            datos_laborales=(
                {
                    "tipo_contrato": laborales.tipo_contrato,
                    "meses_continuidad": laborales.meses_continuidad,
                    "ingreso_mensual": laborales.ingreso_mensual,
                    "otros_ingresos": laborales.otros_ingresos,
                    "anios_camara_comercio": laborales.anios_camara_comercio,
                }
                if laborales
                else None
            ),
            contacto_vivienda=(
                {
                    "estrato": contacto.estrato,
                    "personas_a_cargo": contacto.personas_a_cargo,
                    "tipo_vivienda": contacto.tipo_vivienda,
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
            desembolso=_desembolso_response(
                self.repo.obtener_desembolso(id_solicitud)
            ),
        )

    def ofertas(self, id_solicitud: uuid.UUID) -> list[OfertaResponse]:
        return [_oferta_response(o) for o in self.repo.obtener_ofertas(id_solicitud)]

    def seleccionar_oferta(self, id_solicitud: uuid.UUID, payload: SeleccionarOfertaRequest) -> OfertaResponse:
        return _oferta_response(
            self.repo.seleccionar_oferta(
                id_solicitud,
                payload.id_oferta,
                monto=payload.monto,
                plazo=payload.plazo,
            )
        )
