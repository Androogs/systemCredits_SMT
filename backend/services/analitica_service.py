"""Analítica de efectividad y perfil del cliente (insumo de campañas).

Agrega las solicitudes sobre dimensiones operativas y de perfil:
efectividad por sede/marca/asesor, mezcla de score e ingreso por sede,
causales de rechazo y segmentación para campañas (procedencia, edad,
estrato, vivienda, moto, marca, etc.).

Semántica de conteos (coherente con el embudo del panel):

- radicadas:  solicitudes del rango (por fecha de radicación).
- aprobadas:  decision='aprobado' (incluye las que luego fueron
              crédito: desembolsadas/facturadas).
- creditos:   solicitudes con credito_financiacion o estado
              'desembolsada'.
- rechazadas: decision='rechazado'.
- formalizadas: con fecha_hora_firma.
- efectividad: creditos / radicadas.
- saldo_aprobado: suma del cupo_aprobado vigente de las aprobadas
              (o valor_financiacion del crédito si no hay cupo).

La segmentación se calcula en memoria sobre el rango pedido (el log
histórico ronda las ~6 mil filas; una consulta por dimensión sería más
cara y menos legible).
"""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.db_models.models import (
    CapacidadPago,
    CreditoFinanciacion,
    EvaluacionCredito,
    ProductoVehiculo,
    SolicitudCredito,
)
from backend.models.analitica_models import (
    AnaliticaResponse,
    CausalSede,
    CausalTotal,
    DimensionSegmentos,
    FilaAsesor,
    FilaEfectividad,
    PerfilSede,
    Segmento,
)

SIN_DATO = "Sin dato"

ETIQUETAS = {
    "fuerzas_militares": "Fuerzas Militares",
    "obra_labor": "Obra o Labor",
    "no_aplica": "No aplica",
}


def _etiqueta(v: object) -> str:
    """Normaliza un valor de dimensión para mostrarlo ('SOLTERO' →
    'Soltero', 'obra_labor' → 'Obra o Labor', vacío → 'Sin dato')."""
    if v is None:
        return SIN_DATO
    s = str(v).strip().rstrip(".")
    if not s or s.lower() in ("none", "nan", "null"):
        return SIN_DATO
    s = " ".join(s.split())
    if s in ETIQUETAS:
        return ETIQUETAS[s]
    key = s.lower()
    if key in ETIQUETAS:
        return ETIQUETAS[key]
    if s.isupper():
        return s.capitalize() if s.isalpha() else s.title()
    return s


def _si_no(v: bool | None) -> str:
    if v is None:
        return SIN_DATO
    return "Sí" if v else "No"


def _vigente(items: list):
    """Primera fila vigente de una colección versionada (o la última)."""
    vig = [i for i in items if getattr(i, "vigente", True)]
    return vig[-1] if vig else (items[-1] if items else None)


def _edad(s: SolicitudCredito) -> int | None:
    nac = s.cliente.fecha_nacimiento if s.cliente else None
    if not nac or nac.year < 1920 or not s.fecha_hora:
        return None
    return int((s.fecha_hora.date() - nac).days / 365.25)


def _banda_edad(s: SolicitudCredito) -> str:
    e = _edad(s)
    if e is None:
        return SIN_DATO
    if e < 18:
        return "Menor de 18"
    if e <= 25:
        return "18 - 25"
    if e <= 35:
        return "26 - 35"
    if e <= 45:
        return "36 - 45"
    return "46 o más"


class AnaliticaService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    def _solicitudes(
        self, desde: datetime | None, hasta: datetime | None
    ) -> list[SolicitudCredito]:
        q = (
            select(SolicitudCredito)
            .options(
                joinedload(SolicitudCredito.cliente),
                joinedload(SolicitudCredito.concesionario),
                joinedload(SolicitudCredito.datos_laborales),
                joinedload(SolicitudCredito.contacto_vivienda),
                selectinload(SolicitudCredito.evaluaciones),
                selectinload(SolicitudCredito.capacidades_pago),
                selectinload(SolicitudCredito.causales),
            )
            .order_by(SolicitudCredito.fecha_hora)
        )
        if desde is not None:
            q = q.where(SolicitudCredito.fecha_hora >= desde)
        if hasta is not None:
            q = q.where(SolicitudCredito.fecha_hora < hasta)
        return list(self.db.scalars(q).unique().all())

    def _contexto(self, solicitudes: list[SolicitudCredito]):
        ids = [s.id_solicitud for s in solicitudes]
        vehiculos: dict = {}
        if ids:
            for v in self.db.scalars(
                select(ProductoVehiculo).where(
                    ProductoVehiculo.id_solicitud.in_(ids)
                )
            ):
                vehiculos[v.id_solicitud] = v
        credito_ids: set = set()
        saldo_credito: dict = {}
        if ids:
            for cr in self.db.scalars(
                select(CreditoFinanciacion).where(
                    CreditoFinanciacion.id_solicitud.in_(ids)
                )
            ):
                credito_ids.add(cr.id_solicitud)
                saldo_credito[cr.id_solicitud] = (
                    saldo_credito.get(cr.id_solicitud, 0.0)
                    + float(cr.valor_financiacion or 0)
                )
        # Un desembolso sin fila en credito_financiacion igual cuenta
        # como crédito (semillas demo antiguas no creaban el crédito).
        for s in solicitudes:
            if s.estado == "desembolsada":
                credito_ids.add(s.id_solicitud)
        return vehiculos, credito_ids, saldo_credito

    # ------------------------------------------------------------------
    def _conteos(self, grupo: list[SolicitudCredito], credito_ids: set):
        rad = len(grupo)
        apr = sum(1 for s in grupo if s.decision == "aprobado")
        cred = sum(1 for s in grupo if s.id_solicitud in credito_ids)
        rec = sum(1 for s in grupo if s.decision == "rechazado")
        firm = sum(1 for s in grupo if s.fecha_hora_firma is not None)
        saldo = 0.0
        for s in grupo:
            if s.decision != "aprobado":
                continue
            cap: CapacidadPago | None = _vigente(s.capacidades_pago)
            if cap and cap.cupo_aprobado:
                saldo += float(cap.cupo_aprobado)
        return rad, apr, cred, rec, firm, saldo

    def _fila_efectividad(
        self, nombre: str, grupo: list[SolicitudCredito], credito_ids: set
    ) -> FilaEfectividad:
        rad, apr, cred, rec, _, saldo = self._conteos(grupo, credito_ids)
        return FilaEfectividad(
            nombre=nombre,
            radicadas=rad,
            aprobadas=apr,
            efectividad=round(cred / rad * 100, 1) if rad else 0.0,
            creditos=cred,
            rechazadas=rec,
            saldo_aprobado=round(saldo, 2),
        )

    # ------------------------------------------------------------------
    def obtener(
        self, desde: date | None, hasta: date | None
    ) -> AnaliticaResponse:
        d_desde = datetime.combine(desde, datetime.min.time()) if desde else None
        d_hasta = (
            datetime.combine(hasta + timedelta(days=1), datetime.min.time())
            if hasta
            else None
        )
        solicitudes = self._solicitudes(d_desde, d_hasta)
        vehiculos, credito_ids, _ = self._contexto(solicitudes)

        def sede(s: SolicitudCredito) -> str:
            return s.concesionario.nombre if s.concesionario else "Sin sede"

        def veh(s: SolicitudCredito) -> ProductoVehiculo | None:
            return vehiculos.get(s.id_solicitud)

        def marca(s: SolicitudCredito) -> str:
            # Marca del vehículo a financiar; sin vehículo → 'Sin dato'
            # (el cargue histórico no siempre trae prenda).
            return _etiqueta(veh(s).marca if veh(s) else None)

        por_grupo: dict[str, list[SolicitudCredito]] = defaultdict(list)
        por_marca: dict[str, list[SolicitudCredito]] = defaultdict(list)
        por_asesor: dict[str, list[SolicitudCredito]] = defaultdict(list)
        cedulas: dict[str, str] = {}
        for s in solicitudes:
            por_grupo[sede(s)].append(s)
            por_marca[marca(s)].append(s)
            clave = s.asesor_cedula or s.asesor_nombre or "Sin asesor"
            por_asesor[clave].append(s)
            if s.asesor_cedula:
                cedulas[clave] = s.asesor_cedula

        filas_sede = sorted(
            (self._fila_efectividad(n, g, credito_ids) for n, g in por_grupo.items()),
            key=lambda f: -f.radicadas,
        )
        filas_marca = sorted(
            (self._fila_efectividad(n, g, credito_ids) for n, g in por_marca.items()),
            # 'Sin dato' (prenda sin vehículo) no es segmento accionable:
            # va al final sin importar su volumen.
            key=lambda f: (f.nombre == SIN_DATO, -f.radicadas),
        )

        filas_asesor = []
        for clave, g in por_asesor.items():
            rad, apr, cred, _, firm, saldo = self._conteos(g, credito_ids)
            filas_asesor.append(
                FilaAsesor(
                    asesor=g[0].asesor_nombre or clave,
                    cedula=cedulas.get(clave),
                    radicadas=rad,
                    creditos=cred,
                    efectividad=round(cred / rad * 100, 1) if rad else 0.0,
                    aprobadas=apr,
                    formalizadas=firm,
                    saldo_aprobado=round(saldo, 2),
                )
            )
        filas_asesor.sort(key=lambda f: -f.creditos)

        # --- Perfil por sede -------------------------------------------
        perfil_sede: list[PerfilSede] = []
        for nombre, g in sorted(por_grupo.items(), key=lambda kv: -len(kv[1])):
            score: dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0, "sin_evaluar": 0}
            ingreso: dict[str, int] = {
                "ALTO": 0, "MEDIO": 0, "BAJO": 0, "GRIS": 0, "sin_evaluar": 0
            }
            ocupacion: dict[str, int] = defaultdict(int)
            edades = []
            for s in g:
                ev: EvaluacionCredito | None = _vigente(s.evaluaciones)
                if ev and ev.perfil_score:
                    score[ev.perfil_score] = score.get(ev.perfil_score, 0) + 1
                else:
                    score["sin_evaluar"] += 1
                if ev and ev.perfil_ingreso:
                    ingreso[ev.perfil_ingreso] = ingreso.get(ev.perfil_ingreso, 0) + 1
                else:
                    ingreso["sin_evaluar"] += 1
                ocup = (s.cliente.ocupacion if s.cliente else None) or "sin_dato"
                ocupacion[ocup] += 1
                e = _edad(s)
                if e is not None:
                    edades.append(e)
            perfil_sede.append(
                PerfilSede(
                    nombre=nombre,
                    radicadas=len(g),
                    edad_promedio=(
                        round(sum(edades) / len(edades), 1) if edades else None
                    ),
                    score=score,
                    ingreso=ingreso,
                    ocupacion=dict(ocupacion),
                )
            )

        # --- Causales por sede (top 5 activas en rechazadas) -----------
        causales_sede: list[CausalSede] = []
        for nombre, g in sorted(por_grupo.items(), key=lambda kv: -len(kv[1])):
            conteo: dict[tuple[str, str], int] = defaultdict(int)
            rechazadas = 0
            for s in g:
                if s.decision != "rechazado":
                    continue
                rechazadas += 1
                for c in s.causales:
                    if c.activa:
                        conteo[(c.codigo, c.descripcion)] += 1
            top = sorted(conteo.items(), key=lambda kv: -kv[1])[:5]
            causales_sede.append(
                CausalSede(
                    nombre=nombre,
                    rechazadas=rechazadas,
                    causales=[
                        CausalTotal(codigo=k[0], descripcion=k[1], total=t)
                        for k, t in top
                    ],
                )
            )

        # --- Segmentos para campañas ------------------------------------
        dimensiones: list[tuple[str, object]] = [
            (
                "Procedencia de la solicitud",
                lambda s: "Cargue histórico"
                if s.origen == "cargue_historico"
                else "Flujo normal",
            ),
            ("Edad al radicar", _banda_edad),
            ("Estado civil", lambda s: _etiqueta(
                s.contacto_vivienda.estado_civil if s.contacto_vivienda else None
            )),
            ("Estrato", lambda s: _etiqueta(
                s.contacto_vivienda.estrato if s.contacto_vivienda else None
            )),
            ("Número de hijos", lambda s: (
                SIN_DATO
                if not s.contacto_vivienda or s.contacto_vivienda.num_hijos is None
                else "3 o más"
                if s.contacto_vivienda.num_hijos >= 3
                else str(s.contacto_vivienda.num_hijos)
            )),
            ("Personas a cargo", lambda s: (
                SIN_DATO
                if not s.contacto_vivienda
                or s.contacto_vivienda.personas_a_cargo is None
                else "0"
                if s.contacto_vivienda.personas_a_cargo == 0
                else "1 - 2"
                if s.contacto_vivienda.personas_a_cargo <= 2
                else "3 o más"
            )),
            ("Zona", lambda s: (
                SIN_DATO
                if not s.contacto_vivienda or s.contacto_vivienda.zona_rural is None
                else "Rural" if s.contacto_vivienda.zona_rural else "Urbana"
            )),
            ("Cabeza de familia", lambda s: _si_no(
                s.contacto_vivienda.es_cabeza_familia if s.contacto_vivienda else None
            )),
            ("Tipo de vivienda", lambda s: _etiqueta(
                s.contacto_vivienda.tipo_vivienda if s.contacto_vivienda else None
            )),
            ("Ya tiene moto", lambda s: _si_no(
                s.contacto_vivienda.tiene_moto if s.contacto_vivienda else None
            )),
            ("Primera moto", lambda s: _si_no(
                s.contacto_vivienda.primera_moto if s.contacto_vivienda else None
            )),
            ("Ocupación", lambda s: _etiqueta(
                s.cliente.ocupacion if s.cliente else None
            )),
            ("Tipo de contrato", lambda s: _etiqueta(
                s.datos_laborales.tipo_contrato if s.datos_laborales else None
            )),
            ("Nivel educativo", lambda s: _etiqueta(
                s.datos_laborales.nivel_educativo if s.datos_laborales else None
            )),
            ("Profesión", lambda s: _etiqueta(
                s.datos_laborales.profesion if s.datos_laborales else None
            )),
            ("Cargo", lambda s: _etiqueta(
                s.datos_laborales.cargo if s.datos_laborales else None
            )),
            ("Marca", lambda s: _etiqueta(veh(s).marca if veh(s) else None)),
            ("Referencia", lambda s: _etiqueta(veh(s).referencia if veh(s) else None)),
            ("Modelo", lambda s: _etiqueta(veh(s).modelo if veh(s) else None)),
            ("Color", lambda s: _etiqueta(veh(s).color if veh(s) else None)),
        ]

        segmentos: list[DimensionSegmentos] = []
        for nombre_dim, clave_fn in dimensiones:
            grupos: dict[str, list[SolicitudCredito]] = defaultdict(list)
            for s in solicitudes:
                grupos[clave_fn(s)].append(s)
            filas = []
            for seg, g in grupos.items():
                rad, apr, cred, _, _, _ = self._conteos(g, credito_ids)
                filas.append(
                    Segmento(segmento=seg, radicadas=rad, aprobadas=apr, creditos=cred)
                )
            filas.sort(key=lambda f: (f.segmento == SIN_DATO, -f.radicadas))
            segmentos.append(DimensionSegmentos(dimension=nombre_dim, segmentos=filas))

        return AnaliticaResponse(
            generado_en=datetime.now(timezone.utc),
            desde=desde,
            hasta=hasta,
            historico_completo=desde is None and hasta is None,
            total_radicadas=len(solicitudes),
            por_sede=filas_sede,
            por_marca=filas_marca,
            por_asesor=filas_asesor,
            perfil_por_sede=perfil_sede,
            causales_por_sede=causales_sede,
            segmentos=segmentos,
        )
