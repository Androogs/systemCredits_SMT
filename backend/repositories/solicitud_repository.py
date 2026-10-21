import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.db_models.models import (
    AliadoFinanciero,
    AliadoProducto,
    CapacidadPago,
    Ciudad,
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
from backend.services.seguro_service import cuota_seguro, seguro_vida_vigente
from backend.services.motor_exceptions import (
    ConflictoEstadoError,
    SolicitudNoEncontradaError,
    ValidacionError,
)


def oferta_expirada(oferta: OfertaCredito, ahora: datetime | None = None) -> bool:
    """True si la oferta pasó su fecha_vigencia.

    Una oferta sin vigencia registrada (previa a la migración) se
    considera vigente: el UPDATE de la migración 0008 la rellena, así
    que None solo aparece en flujos ajenos a _generar_ofertas.
    """
    if oferta.fecha_vigencia is None:
        return False
    vigencia = oferta.fecha_vigencia
    if vigencia.tzinfo is None:
        vigencia = vigencia.replace(tzinfo=UTC)
    return (ahora or datetime.now(UTC)) > vigencia


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
                selectinload(SolicitudCredito.consentimientos),
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

    def obtener_o_crear_ciudad(self, texto: str | None) -> Ciudad | None:
        """Resuelve 'Palmira, Valle del Cauca' (o solo 'Palmira') contra
        el catálogo `ciudad`; crea la fila si no existe."""
        if not texto or not texto.strip():
            return None
        partes = [p.strip() for p in texto.rsplit(",", 1)]
        nombre = partes[0]
        departamento = partes[1] if len(partes) > 1 else "Colombia"
        ciudad = (
            self.db.query(Ciudad)
            .filter(Ciudad.nombre == nombre, Ciudad.departamento == departamento)
            .one_or_none()
        )
        if ciudad is not None:
            return ciudad
        ciudad = Ciudad(nombre=nombre, departamento=departamento)
        self.db.add(ciudad)
        self.db.flush()
        return ciudad

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
        if oferta_expirada(oferta):
            raise ConflictoEstadoError(
                "La oferta expiró el "
                f"{oferta.fecha_vigencia:%Y-%m-%d %H:%M} UTC; "
                "genera una nueva evaluación para renovarla."
            )

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
            # La cuota de la oferta es TOTAL: anualidad + seguro de
            # vida, la misma fórmula con que se generó en la evaluación.
            # Sin la prima, la cuota quedaba ~0.35% del monto por debajo
            # de lo que el cliente vio al aceptar.
            cuota = cuota_anualidad(
                Decimal(str(oferta.monto_aprobado or 0)),
                Decimal(str(oferta.tasa_ofrecida)),
                int(oferta.plazo_ofrecido or 0),
            )
            seguro = seguro_vida_vigente(self.db)
            if seguro is not None:
                cuota += cuota_seguro(
                    Decimal(str(oferta.monto_aprobado or 0)),
                    Decimal(str(seguro.tasa_prima)),
                )
            oferta.cuota_mensual = cuota

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

    def conteos_embudo(
        self,
        desde: datetime | None = None,
        hasta: datetime | None = None,
    ) -> dict:
        """Agregados del embudo en una sola pasada sobre
        solicitud_credito (FILTER WHERE: Postgres 9.4+ y SQLite 3.30+).
        `desde`/`hasta` acotan por fecha_hora de radicación."""
        q = self.db.query(
            func.count(SolicitudCredito.id_solicitud),
            func.count().filter(SolicitudCredito.decision.isnot(None)),
            func.count().filter(SolicitudCredito.decision == "aprobado"),
            func.count().filter(
                SolicitudCredito.fecha_hora_firma.isnot(None)
            ),
            func.count().filter(
                SolicitudCredito.estado == "desembolsada"
            ),
            func.count().filter(SolicitudCredito.estado == "cancelada"),
        )
        q_estado = self.db.query(
            SolicitudCredito.estado, func.count()
        ).group_by(SolicitudCredito.estado)
        if desde is not None:
            q = q.filter(SolicitudCredito.fecha_hora >= desde)
            q_estado = q_estado.filter(SolicitudCredito.fecha_hora >= desde)
        if hasta is not None:
            q = q.filter(SolicitudCredito.fecha_hora < hasta)
            q_estado = q_estado.filter(SolicitudCredito.fecha_hora < hasta)
        fila = q.one()
        por_estado = dict(q_estado.all())
        return {
            "radicadas": fila[0],
            "evaluadas": fila[1],
            "aprobadas": fila[2],
            "formalizadas": fila[3],
            "desembolsadas": fila[4],
            "canceladas": fila[5],
            "por_estado": por_estado,
        }

    def conteos_por_aliado(
        self,
        desde: datetime | None = None,
        hasta: datetime | None = None,
    ) -> list[dict]:
        """Conversión por aliado financiero. La solicitud solo conoce a su
        aliado cuando el cliente selecciona la oferta (post-aprobación);
        el capital desembolsado se agrega desde credito_financiacion,
        que guarda el aliado ganador al formalizar."""
        q = (
            self.db.query(
                AliadoFinanciero.nombre,
                func.count(SolicitudCredito.id_solicitud),
                func.count().filter(
                    SolicitudCredito.fecha_hora_firma.isnot(None)
                ),
                func.count().filter(
                    SolicitudCredito.estado == "desembolsada"
                ),
            )
            .join(
                OfertaCredito,
                (OfertaCredito.id_solicitud == SolicitudCredito.id_solicitud)
                & OfertaCredito.seleccionada.is_(True),
            )
            .join(
                AliadoProducto,
                OfertaCredito.id_aliado_producto
                == AliadoProducto.id_aliado_producto,
            )
            .join(
                AliadoFinanciero,
                AliadoProducto.id_aliado == AliadoFinanciero.id_aliado,
            )
        )
        if desde is not None:
            q = q.filter(SolicitudCredito.fecha_hora >= desde)
        if hasta is not None:
            q = q.filter(SolicitudCredito.fecha_hora < hasta)
        filas = q.group_by(AliadoFinanciero.nombre).all()
        capital_por_aliado = dict(
            self.db.query(
                AliadoFinanciero.nombre,
                func.coalesce(func.sum(Desembolso.capital), 0),
            )
            .join(
                CreditoFinanciacion,
                Desembolso.id_credito == CreditoFinanciacion.id_credito,
            )
            .join(
                AliadoFinanciero,
                CreditoFinanciacion.id_aliado_financiero
                == AliadoFinanciero.id_aliado,
            )
            .filter(Desembolso.estado == "confirmado")
            .group_by(AliadoFinanciero.nombre)
            .all()
        )
        return [
            {
                "aliado": nombre,
                "con_oferta": con_oferta,
                "formalizadas": formalizadas,
                "desembolsadas": desembolsadas,
                "valor_desembolsado": capital_por_aliado.get(nombre, 0),
            }
            for nombre, con_oferta, formalizadas, desembolsadas in filas
        ]

    def productos_activos(self) -> list[AliadoProducto]:
        return (
            self.db.query(AliadoProducto)
            .options(selectinload(AliadoProducto.reglas))
            .filter(AliadoProducto.activo.is_(True))
            .all()
        )
