import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import String, and_, case, cast, func, literal, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.db_models.auth_models import Asesor
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
    EvaluacionCredito,
    OfertaCredito,
    SolicitudCausal,
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


def _predicado_radicador(
    asesor_ids: set[int],
    asesor_cedula: str | None,
    persona_desde: datetime | None = None,
):
    """Eje radicador por cuenta Y por persona: `id_asesor` en las
    cuentas alcanzables y, cuando el usuario tiene cédula en su ficha,
    la solicitud debe llevar esa cédula (foto del radicador) o ninguna.
    La foto NULL (legada) solo la ve quien estaba al crearla: si la
    cuenta cambió de titular (`persona_desde`), exige fecha posterior
    al corte."""
    base = SolicitudCredito.id_asesor.in_(asesor_ids)
    if asesor_cedula is not None:
        legado = SolicitudCredito.asesor_cedula.is_(None)
        if persona_desde is not None:
            legado = and_(
                legado, SolicitudCredito.fecha_hora >= persona_desde
            )
        return and_(
            base,
            or_(
                SolicitudCredito.asesor_cedula == asesor_cedula,
                legado,
            ),
        )
    return base


def _predicado_filtro_asesor(db: Session, filtro_id_asesor: int):
    """Filtro de panel por asesor = por PERSONA: cuando el asesor tiene
    cédula en su ficha solo cuenta su producción (foto igual, o legada
    posterior al corte `persona_desde`). Sin cédula no hay cómo
    discriminar titulares y se filtra solo por la cuenta."""
    base = SolicitudCredito.id_asesor == filtro_id_asesor
    fila = (
        db.query(Asesor.num_cedula, Asesor.persona_desde)
        .filter(Asesor.id_asesor == filtro_id_asesor)
        .first()
    )
    if fila is None or not fila.num_cedula:
        return base
    legado = SolicitudCredito.asesor_cedula.is_(None)
    if fila.persona_desde is not None:
        legado = and_(legado, SolicitudCredito.fecha_hora >= fila.persona_desde)
    return and_(
        base,
        or_(SolicitudCredito.asesor_cedula == fila.num_cedula, legado),
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
        concesionario_ids: set[int] | None = None,
        asesor_ids: set[int] | None = None,
        asesor_cedula: str | None = None,
        persona_desde: datetime | None = None,
        filtro_id_concesionario: int | None = None,
        filtro_id_asesor: int | None = None,
        orden: str = "reciente",
    ) -> list[SolicitudCredito]:
        """Listado del panel: más recientes primero, con cliente y
        evaluación vigente precargadas. `concesionario_ids` y
        `asesor_ids` son el alcance del usuario autenticado por eje
        (sede / radicador): None = sin filtro en ese eje; un set
        —incluso vacío— limita a esos ids.
        `asesor_cedula` refina el eje radicador a la persona: la cuenta
        de asesor puede cambiar de dueño y cada solicitud queda ligada
        a la cédula de quien la hizo (NULL = legado, visible para
        quien herede la cuenta).
        `filtro_id_concesionario`/`filtro_id_asesor` son filtros de
        panel: se intersectan con el alcance (nunca lo amplían).
        `orden="prioridad"` pone las pendientes de evaluación primero
        — el ORDER BY corre antes del LIMIT, así la ventana siempre
        contiene la cola de trabajo."""
        query = (
            self.db.query(SolicitudCredito)
            .join(SolicitudCredito.cliente)
            .options(
                joinedload(SolicitudCredito.cliente),
                joinedload(SolicitudCredito.asesor),
                joinedload(SolicitudCredito.concesionario),
                selectinload(SolicitudCredito.evaluaciones),
                selectinload(SolicitudCredito.capacidades_pago),
            )
        )
        if concesionario_ids is not None:
            query = query.filter(
                SolicitudCredito.id_concesionario.in_(concesionario_ids)
            )
        if asesor_ids is not None:
            query = query.filter(
                _predicado_radicador(asesor_ids, asesor_cedula, persona_desde)
            )
        if filtro_id_concesionario is not None:
            query = query.filter(
                SolicitudCredito.id_concesionario == filtro_id_concesionario
            )
        if filtro_id_asesor is not None:
            query = query.filter(
                _predicado_filtro_asesor(self.db, filtro_id_asesor)
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
        ordenamiento = (
            [
                case(
                    (
                        and_(
                            SolicitudCredito.decision.is_(None),
                            SolicitudCredito.estado.in_(
                                ["creada", "en_evaluacion"]
                            ),
                        ),
                        0,
                    ),
                    else_=1,
                ),
                SolicitudCredito.fecha_hora.desc(),
            ]
            if orden == "prioridad"
            else [SolicitudCredito.fecha_hora.desc()]
        )
        return (
            query.order_by(*ordenamiento)
            .offset(offset)
            .limit(limite)
            .all()
        )

    def obtener_detalle(self, id_solicitud: uuid.UUID) -> SolicitudCredito | None:
        return (
            self.db.query(SolicitudCredito)
            .options(
                joinedload(SolicitudCredito.cliente),
                joinedload(SolicitudCredito.asesor),
                joinedload(SolicitudCredito.concesionario),
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
        # El plazo se acota al rango comercial del producto, no al
        # término evaluado: la evaluación sugirió un plazo, pero el
        # cliente puede pactar cualquier término que el producto venda
        # (la moto evaluada a 36 se puede pagar en 48). Si el producto
        # no define límites, se conserva el tope evaluado.
        producto = oferta.producto
        plazo_min_producto = (
            producto.plazo_min_meses if producto is not None else None
        )
        plazo_max_producto = (
            producto.plazo_max_meses if producto is not None else None
        )
        if monto is not None:
            if tope_monto and monto > tope_monto:
                raise ValidacionError(
                    f"El monto solicitado ({monto}) supera el cupo aprobado ({tope_monto})."
                )
            oferta.monto_aprobado = monto
        if plazo is not None:
            if plazo_min_producto is not None and plazo < plazo_min_producto:
                raise ValidacionError(
                    f"El plazo solicitado ({plazo}) está por debajo del mínimo del producto ({plazo_min_producto} meses)."
                )
            if plazo_max_producto is not None and plazo > plazo_max_producto:
                raise ValidacionError(
                    f"El plazo solicitado ({plazo}) supera el máximo del producto ({plazo_max_producto} meses)."
                )
            if (
                plazo_max_producto is None
                and tope_plazo
                and plazo > tope_plazo
            ):
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
        concesionario_ids: set[int] | None = None,
        asesor_ids: set[int] | None = None,
        asesor_cedula: str | None = None,
        persona_desde: datetime | None = None,
        filtro_id_concesionario: int | None = None,
        filtro_id_asesor: int | None = None,
    ) -> dict:
        """Agregados del embudo en una sola pasada sobre
        solicitud_credito (FILTER WHERE: Postgres 9.4+ y SQLite 3.30+).
        `desde`/`hasta` acotan por fecha_hora de radicación;
        `filtro_*` son los filtros dimensionales del panel."""
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
        if concesionario_ids is not None:
            q = q.filter(SolicitudCredito.id_concesionario.in_(concesionario_ids))
            q_estado = q_estado.filter(
                SolicitudCredito.id_concesionario.in_(concesionario_ids)
            )
        if asesor_ids is not None:
            predicado = _predicado_radicador(asesor_ids, asesor_cedula, persona_desde)
            q = q.filter(predicado)
            q_estado = q_estado.filter(predicado)
        if filtro_id_concesionario is not None:
            q = q.filter(
                SolicitudCredito.id_concesionario == filtro_id_concesionario
            )
            q_estado = q_estado.filter(
                SolicitudCredito.id_concesionario == filtro_id_concesionario
            )
        if filtro_id_asesor is not None:
            predicado = _predicado_filtro_asesor(self.db, filtro_id_asesor)
            q = q.filter(predicado)
            q_estado = q_estado.filter(predicado)
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
        concesionario_ids: set[int] | None = None,
        aliado_ids: set[int] | None = None,
        asesor_ids: set[int] | None = None,
        asesor_cedula: str | None = None,
        persona_desde: datetime | None = None,
        filtro_id_concesionario: int | None = None,
        filtro_id_asesor: int | None = None,
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
        if concesionario_ids is not None:
            q = q.filter(SolicitudCredito.id_concesionario.in_(concesionario_ids))
        if asesor_ids is not None:
            q = q.filter(
                _predicado_radicador(asesor_ids, asesor_cedula, persona_desde)
            )
        if filtro_id_concesionario is not None:
            q = q.filter(
                SolicitudCredito.id_concesionario == filtro_id_concesionario
            )
        if filtro_id_asesor is not None:
            q = q.filter(_predicado_filtro_asesor(self.db, filtro_id_asesor))
        if aliado_ids is not None:
            q = q.filter(AliadoFinanciero.id_aliado.in_(aliado_ids))
        if desde is not None:
            q = q.filter(SolicitudCredito.fecha_hora >= desde)
        if hasta is not None:
            q = q.filter(SolicitudCredito.fecha_hora < hasta)
        filas = q.group_by(AliadoFinanciero.nombre).all()
        q_capital = (
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
            .join(
                SolicitudCredito,
                CreditoFinanciacion.id_solicitud == SolicitudCredito.id_solicitud,
            )
            .filter(Desembolso.estado == "confirmado")
        )
        if concesionario_ids is not None:
            q_capital = q_capital.filter(
                SolicitudCredito.id_concesionario.in_(concesionario_ids)
            )
        if asesor_ids is not None:
            q_capital = q_capital.filter(
                _predicado_radicador(asesor_ids, asesor_cedula, persona_desde)
            )
        if filtro_id_concesionario is not None:
            q_capital = q_capital.filter(
                SolicitudCredito.id_concesionario == filtro_id_concesionario
            )
        if filtro_id_asesor is not None:
            q_capital = q_capital.filter(
                _predicado_filtro_asesor(self.db, filtro_id_asesor)
            )
        if aliado_ids is not None:
            q_capital = q_capital.filter(AliadoFinanciero.id_aliado.in_(aliado_ids))
        capital_por_aliado = dict(
            q_capital.group_by(AliadoFinanciero.nombre).all()
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

    def conteos_por_asesor(
        self,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        concesionario_ids: set[int] | None = None,
        aliado_ids: set[int] | None = None,
        asesor_ids: set[int] | None = None,
        asesor_cedula: str | None = None,
        persona_desde: datetime | None = None,
        filtro_id_concesionario: int | None = None,
        filtro_id_asesor: int | None = None,
    ) -> list[dict]:
        """Producción por PERSONA asesora, no por cuenta: cada solicitud
        se agrupa bajo la cédula de quien la radicó (`asesor_cedula`,
        la foto del momento). Las legadas sin foto caen en el titular
        actual solo cuando son posteriores al corte `persona_desde`;
        si no, forman el grupo 'titular anterior' de su cuenta (clave
        `~id_asesor`). Una cuenta sin cédula agrupa sus legadas bajo
        `#id_asesor`: sin foto no hay cómo discriminar titulares."""
        es_titular_actual = or_(
            Asesor.persona_desde.is_(None),
            SolicitudCredito.fecha_hora >= Asesor.persona_desde,
        )
        cuenta = cast(Asesor.id_asesor, String)
        persona_key = case(
            (
                SolicitudCredito.asesor_cedula.isnot(None),
                SolicitudCredito.asesor_cedula,
            ),
            (
                es_titular_actual,
                func.coalesce(Asesor.num_cedula, literal("#") + cuenta),
            ),
            else_=literal("~") + cuenta,
        )
        nombre_persona = case(
            (
                SolicitudCredito.asesor_cedula.isnot(None),
                func.coalesce(
                    SolicitudCredito.asesor_nombre, Asesor.nombre
                ),
            ),
            (
                es_titular_actual,
                func.coalesce(
                    Asesor.nombre, SolicitudCredito.asesor_nombre
                ),
            ),
            else_=SolicitudCredito.asesor_nombre,
        )
        q = (
            self.db.query(
                persona_key.label("clave"),
                func.max(nombre_persona).label("asesor"),
                func.count(SolicitudCredito.id_solicitud),
                func.count().filter(
                    SolicitudCredito.decision == "aprobado"
                ),
                func.count().filter(
                    SolicitudCredito.fecha_hora_firma.isnot(None)
                ),
                func.count().filter(
                    SolicitudCredito.estado == "desembolsada"
                ),
            )
            .outerjoin(
                Asesor, SolicitudCredito.id_asesor == Asesor.id_asesor
            )
            .group_by(persona_key)
        )
        if concesionario_ids is not None:
            q = q.filter(SolicitudCredito.id_concesionario.in_(concesionario_ids))
        if asesor_ids is not None:
            q = q.filter(
                _predicado_radicador(asesor_ids, asesor_cedula, persona_desde)
            )
        if filtro_id_concesionario is not None:
            q = q.filter(
                SolicitudCredito.id_concesionario == filtro_id_concesionario
            )
        if filtro_id_asesor is not None:
            q = q.filter(_predicado_filtro_asesor(self.db, filtro_id_asesor))
        if aliado_ids is not None:
            q = (
                q.join(
                    OfertaCredito,
                    (
                        OfertaCredito.id_solicitud
                        == SolicitudCredito.id_solicitud
                    )
                    & OfertaCredito.seleccionada.is_(True),
                )
                .join(
                    AliadoProducto,
                    OfertaCredito.id_aliado_producto
                    == AliadoProducto.id_aliado_producto,
                )
                .filter(AliadoProducto.id_aliado.in_(aliado_ids))
            )
        if desde is not None:
            q = q.filter(SolicitudCredito.fecha_hora >= desde)
        if hasta is not None:
            q = q.filter(SolicitudCredito.fecha_hora < hasta)
        filas = q.all()
        resultado = []
        for clave, nombre, radicadas, aprobadas, formalizadas, desembolsadas in filas:
            if clave is None:
                resultado.append(
                    {
                        "asesor": nombre or "Sin asesor",
                        "cedula": None,
                        "titular_anterior": False,
                        "radicadas": radicadas,
                        "aprobadas": aprobadas,
                        "formalizadas": formalizadas,
                        "desembolsadas": desembolsadas,
                    }
                )
            elif clave.startswith("~"):
                resultado.append(
                    {
                        "asesor": (
                            f"{nombre} (titular anterior)"
                            if nombre
                            else "Titular anterior"
                        ),
                        "cedula": None,
                        "titular_anterior": True,
                        "radicadas": radicadas,
                        "aprobadas": aprobadas,
                        "formalizadas": formalizadas,
                        "desembolsadas": desembolsadas,
                    }
                )
            elif clave.startswith("#"):
                resultado.append(
                    {
                        "asesor": nombre or "Sin asesor",
                        "cedula": None,
                        "titular_anterior": False,
                        "radicadas": radicadas,
                        "aprobadas": aprobadas,
                        "formalizadas": formalizadas,
                        "desembolsadas": desembolsadas,
                    }
                )
            else:
                resultado.append(
                    {
                        "asesor": nombre or "Asesor",
                        "cedula": clave,
                        "titular_anterior": False,
                        "radicadas": radicadas,
                        "aprobadas": aprobadas,
                        "formalizadas": formalizadas,
                        "desembolsadas": desembolsadas,
                    }
                )
        resultado.sort(key=lambda f: (-f["radicadas"], f["asesor"]))
        return resultado

    def conteos_por_causal(
        self,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        concesionario_ids: set[int] | None = None,
        aliado_ids: set[int] | None = None,
        asesor_ids: set[int] | None = None,
        asesor_cedula: str | None = None,
        persona_desde: datetime | None = None,
        filtro_id_concesionario: int | None = None,
        filtro_id_asesor: int | None = None,
    ) -> list[dict]:
        """Causales de rechazo vigentes agrupadas por código. Solo
        cuentan solicitudes cuya decisión actual es 'rechazado': la
        re-evaluación desactiva las causales viejas, así la métrica
        refleja el motivo por el que hoy se está perdiendo gente."""
        q = (
            self.db.query(
                SolicitudCausal.codigo,
                SolicitudCausal.descripcion,
                func.count(SolicitudCausal.id_solicitud_causal),
            )
            .join(
                SolicitudCredito,
                SolicitudCausal.id_solicitud == SolicitudCredito.id_solicitud,
            )
            .filter(
                SolicitudCausal.activa.is_(True),
                SolicitudCredito.decision == "rechazado",
            )
            .group_by(SolicitudCausal.codigo, SolicitudCausal.descripcion)
        )
        if concesionario_ids is not None:
            q = q.filter(SolicitudCredito.id_concesionario.in_(concesionario_ids))
        if asesor_ids is not None:
            q = q.filter(
                _predicado_radicador(asesor_ids, asesor_cedula, persona_desde)
            )
        if filtro_id_concesionario is not None:
            q = q.filter(
                SolicitudCredito.id_concesionario == filtro_id_concesionario
            )
        if filtro_id_asesor is not None:
            q = q.filter(_predicado_filtro_asesor(self.db, filtro_id_asesor))
        if aliado_ids is not None:
            q = (
                q.join(
                    OfertaCredito,
                    (
                        OfertaCredito.id_solicitud
                        == SolicitudCredito.id_solicitud
                    )
                    & OfertaCredito.seleccionada.is_(True),
                )
                .join(
                    AliadoProducto,
                    OfertaCredito.id_aliado_producto
                    == AliadoProducto.id_aliado_producto,
                )
                .filter(AliadoProducto.id_aliado.in_(aliado_ids))
            )
        if desde is not None:
            q = q.filter(SolicitudCredito.fecha_hora >= desde)
        if hasta is not None:
            q = q.filter(SolicitudCredito.fecha_hora < hasta)
        q = q.order_by(
            func.count(SolicitudCausal.id_solicitud_causal).desc()
        ).limit(8)
        return [
            {"codigo": codigo, "descripcion": descripcion, "total": total}
            for codigo, descripcion, total in q.all()
        ]

    def conteos_reevaluacion(
        self,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        concesionario_ids: set[int] | None = None,
        aliado_ids: set[int] | None = None,
        asesor_ids: set[int] | None = None,
        asesor_cedula: str | None = None,
        persona_desde: datetime | None = None,
        filtro_id_concesionario: int | None = None,
        filtro_id_asesor: int | None = None,
    ) -> dict:
        """Rescate por re-evaluación: solicitudes cuya evaluación
        vigente es versión >1 (rectificadas y vueltas a evaluar) y,
        de ellas, cuántas quedaron aprobadas al final."""
        q = self.db.query(
            func.count(SolicitudCredito.id_solicitud),
            func.count().filter(SolicitudCredito.decision == "aprobado"),
        ).join(
            EvaluacionCredito,
            (
                EvaluacionCredito.id_solicitud
                == SolicitudCredito.id_solicitud
            )
            & EvaluacionCredito.vigente.is_(True)
            & (EvaluacionCredito.version > 1),
        )
        if concesionario_ids is not None:
            q = q.filter(SolicitudCredito.id_concesionario.in_(concesionario_ids))
        if asesor_ids is not None:
            q = q.filter(
                _predicado_radicador(asesor_ids, asesor_cedula, persona_desde)
            )
        if filtro_id_concesionario is not None:
            q = q.filter(
                SolicitudCredito.id_concesionario == filtro_id_concesionario
            )
        if filtro_id_asesor is not None:
            q = q.filter(_predicado_filtro_asesor(self.db, filtro_id_asesor))
        if aliado_ids is not None:
            q = (
                q.join(
                    OfertaCredito,
                    (
                        OfertaCredito.id_solicitud
                        == SolicitudCredito.id_solicitud
                    )
                    & OfertaCredito.seleccionada.is_(True),
                )
                .join(
                    AliadoProducto,
                    OfertaCredito.id_aliado_producto
                    == AliadoProducto.id_aliado_producto,
                )
                .filter(AliadoProducto.id_aliado.in_(aliado_ids))
            )
        if desde is not None:
            q = q.filter(SolicitudCredito.fecha_hora >= desde)
        if hasta is not None:
            q = q.filter(SolicitudCredito.fecha_hora < hasta)
        fila = q.one()
        return {"reevaluadas": fila[0], "rescatadas": fila[1]}

    def productos_activos(self) -> list[AliadoProducto]:
        return (
            self.db.query(AliadoProducto)
            .options(selectinload(AliadoProducto.reglas))
            .filter(AliadoProducto.activo.is_(True))
            .all()
        )
