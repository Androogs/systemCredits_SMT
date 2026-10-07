import uuid
from decimal import Decimal

from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.db_models.models import (
    AliadoProducto,
    CapacidadPago,
    Cliente,
    Cotizante,
    CreditoFinanciacion,
    DatosLaborales,
    Desembolso,
    OfertaCredito,
    SolicitudContactoVivienda,
    SolicitudCredito,
)
from backend.services.finanzas import cuota_anualidad
from backend.services.motor_exceptions import SolicitudNoEncontradaError, ValidacionError


class SolicitudRepository:
    """
    Lectura/escritura de solicitud_credito y sus relaciones directas.
    Centraliza los joins que el motor de decisión necesita para no
    repetir queries dispersas en los services.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_con_datos_para_evaluar(
        self,
        id_solicitud: uuid.UUID,
    ) -> SolicitudCredito | None:
        return (
            self.db.query(SolicitudCredito)
            .options(
                joinedload(SolicitudCredito.cliente),
                joinedload(SolicitudCredito.datos_laborales),
                joinedload(SolicitudCredito.contacto_vivienda),
                selectinload(SolicitudCredito.cotizantes).selectinload(Cotizante.ingresos_mensuales),
            )
            .filter(SolicitudCredito.id_solicitud == id_solicitud)
            .one_or_none()
        )

    def listar(
        self,
        *,
        limite: int = 50,
        offset: int = 0,
        estado: str | None = None,
        decision: str | None = None,
        busqueda: str | None = None,
    ) -> list[SolicitudCredito]:
        """Listado del panel: más recientes primero, con cliente y
        evaluación vigente precargadas."""
        query = (
            self.db.query(SolicitudCredito)
            .join(SolicitudCredito.cliente)
            .options(
                joinedload(SolicitudCredito.cliente),
                selectinload(SolicitudCredito.evaluaciones),
                selectinload(SolicitudCredito.capacidades_pago),
            )
        )
        if estado:
            query = query.filter(SolicitudCredito.estado == estado)
        if decision:
            query = query.filter(SolicitudCredito.decision == decision)
        if busqueda and busqueda.strip():
            like = f"%{busqueda.strip()}%"
            query = query.filter(
                or_(
                    Cliente.nombre_completo.ilike(like),
                    Cliente.num_cedula.ilike(like),
                    cast(SolicitudCredito.num_solicitud, String).ilike(like),
                )
            )
        return (
            query.order_by(SolicitudCredito.fecha_hora.desc())
            .offset(offset)
            .limit(limite)
            .all()
        )

    def obtener_detalle(self, id_solicitud: uuid.UUID) -> SolicitudCredito | None:
        return (
            self.db.query(SolicitudCredito)
            .options(
                joinedload(SolicitudCredito.cliente),
                joinedload(SolicitudCredito.datos_laborales),
                joinedload(SolicitudCredito.contacto_vivienda),
                selectinload(SolicitudCredito.evaluaciones),
                selectinload(SolicitudCredito.capacidades_pago),
                selectinload(SolicitudCredito.causales),
                selectinload(SolicitudCredito.ofertas),
            )
            .filter(SolicitudCredito.id_solicitud == id_solicitud)
            .one_or_none()
        )

    def actualizar_decision(
        self,
        id_solicitud: uuid.UUID,
        decision: str,
        estado: str | None = None,
        descripcion_estado: str | None = None,
    ) -> None:
        solicitud = self.db.query(SolicitudCredito).filter(SolicitudCredito.id_solicitud == id_solicitud).one_or_none()
        if solicitud is None:
            raise SolicitudNoEncontradaError(f"No existe la solicitud {id_solicitud}")
        solicitud.decision = decision
        if estado is not None:
            solicitud.estado = estado
        if descripcion_estado is not None:
            solicitud.descripcion_estado = descripcion_estado
        self.db.flush()

    def obtener_o_crear_cliente(
        self,
        num_cedula: str,
        datos_cliente: dict,
    ) -> Cliente:
        """
        Busca por num_cedula (único en el esquema); si no existe,
        crea el cliente. No actualiza datos de un cliente existente
        aquí a propósito: eso debería ser una operación explícita
        de "actualizar cliente", no un side-effect de crear una
        solicitud nueva.
        """
        cliente = self.db.query(Cliente).filter(Cliente.num_cedula == num_cedula).one_or_none()
        if cliente is not None:
            return cliente

        cliente = Cliente(num_cedula=num_cedula, **datos_cliente)
        self.db.add(cliente)
        self.db.flush()  # necesitamos cliente.id_cliente
        return cliente

    def crear_solicitud(
        self,
        id_cliente: int,
        moneda: str,
        datos_laborales: dict,
        contacto_vivienda: dict,
        datos_solicitud: dict | None = None,
    ) -> SolicitudCredito:
        solicitud = SolicitudCredito(
            id_cliente=id_cliente,
            moneda=moneda,
            **{k: v for k, v in (datos_solicitud or {}).items() if v is not None},
        )
        self.db.add(solicitud)
        self.db.flush()  # necesitamos id_solicitud

        self.db.add(
            DatosLaborales(
                id_solicitud=solicitud.id_solicitud,
                **datos_laborales,
            )
        )
        self.db.add(
            SolicitudContactoVivienda(
                id_solicitud=solicitud.id_solicitud,
                **contacto_vivienda,
            )
        )

        self.db.flush()
        return solicitud

    def obtener_ofertas(
        self,
        id_solicitud: uuid.UUID,
    ) -> list[OfertaCredito]:
        return self.db.query(OfertaCredito).filter(OfertaCredito.id_solicitud == id_solicitud).all()

    def obtener_oferta(
        self,
        id_solicitud: uuid.UUID,
        id_oferta: int,
    ) -> OfertaCredito | None:
        return (
            self.db.query(OfertaCredito)
            .filter(
                OfertaCredito.id_solicitud == id_solicitud,
                OfertaCredito.id_oferta == id_oferta,
            )
            .one_or_none()
        )

    def seleccionar_oferta(
        self,
        id_solicitud: uuid.UUID,
        id_oferta: int,
        monto: Decimal | None = None,
        plazo: int | None = None,
    ) -> OfertaCredito:
        oferta = self.obtener_oferta(id_solicitud, id_oferta)
        if oferta is None:
            raise SolicitudNoEncontradaError(f"No existe la oferta {id_oferta} para la solicitud {id_solicitud}")
        if not oferta.elegible:
            raise ValidacionError(f"No se puede seleccionar una oferta no elegible: {oferta.motivo_no_elegible}")

        # El cliente puede tomar menos del cupo aprobado o un plazo más
        # corto; nunca más de lo evaluado. El tope real es la capacidad
        # vigente (cupo_aprobado/plazo_cupo), no monto_aprobado, que ya
        # pudo haber sido recortado por una selección anterior.
        capacidad = (
            self.db.query(CapacidadPago)
            .filter(
                CapacidadPago.id_solicitud == id_solicitud,
                CapacidadPago.vigente.is_(True),
            )
            .one_or_none()
        )
        tope_monto = (
            Decimal(str(capacidad.cupo_aprobado or capacidad.cupo_calculado))
            if capacidad is not None and (capacidad.cupo_aprobado or capacidad.cupo_calculado)
            else Decimal(str(oferta.monto_aprobado or 0))
        )
        tope_plazo = (
            int(capacidad.plazo_cupo)
            if capacidad is not None and capacidad.plazo_cupo
            else oferta.plazo_ofrecido
        )
        if monto is not None:
            if tope_monto and monto > tope_monto:
                raise ValidacionError(
                    f"El monto solicitado ({monto}) supera el cupo aprobado ({tope_monto})."
                )
            oferta.monto_aprobado = monto
        if plazo is not None:
            if tope_plazo and plazo > tope_plazo:
                raise ValidacionError(
                    f"El plazo solicitado ({plazo}) supera el plazo ofrecido ({tope_plazo})."
                )
            oferta.plazo_ofrecido = plazo
        if (monto is not None or plazo is not None) and oferta.tasa_ofrecida is not None:
            oferta.cuota_mensual = cuota_anualidad(
                Decimal(str(oferta.monto_aprobado or 0)),
                Decimal(str(oferta.tasa_ofrecida)),
                int(oferta.plazo_ofrecido or 0),
            )

        # Desmarcar cualquier otra oferta seleccionada previamente
        # para esta solicitud (solo puede haber una activa a la vez).
        for otra in self.obtener_ofertas(id_solicitud):
            if otra.id_oferta != id_oferta and otra.seleccionada:
                otra.seleccionada = False

        oferta.seleccionada = True
        self.db.flush()
        return oferta

    def obtener_desembolso(self, id_solicitud: uuid.UUID) -> Desembolso | None:
        return (
            self.db.query(Desembolso)
            .join(CreditoFinanciacion, Desembolso.id_credito == CreditoFinanciacion.id_credito)
            .filter(CreditoFinanciacion.id_solicitud == id_solicitud)
            .one_or_none()
        )

    def guardar_ofertas(self, ofertas: list[OfertaCredito]) -> list[OfertaCredito]:
        """Reemplaza las ofertas NO seleccionadas de la solicitud por las nuevas."""
        if not ofertas:
            return []
        id_solicitud = ofertas[0].id_solicitud
        for previa in self.obtener_ofertas(id_solicitud):
            if not previa.seleccionada:
                self.db.delete(previa)
        self.db.flush()
        self.db.add_all(ofertas)
        self.db.flush()
        return ofertas

    def productos_activos(self) -> list[AliadoProducto]:
        return (
            self.db.query(AliadoProducto)
            .options(selectinload(AliadoProducto.reglas))
            .filter(AliadoProducto.activo.is_(True))
            .all()
        )
