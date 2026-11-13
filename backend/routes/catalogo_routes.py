"""Catálogos comerciales: productos de aliados con sus rangos vigentes."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from backend.auth.dependencies import (
    UsuarioActual,
    requiere_roles,
    usuario_actual,
)
from backend.db_models.auth_models import (
    Asesor,
    Concesionario,
    Usuario,
    UsuarioMarca,
)
from backend.db_models.models import (
    AliadoFinanciero,
    AliadoProducto,
    Banco,
    CreditoFinanciacion,
    MarcaVehiculo,
    ProductoVehiculo,
    SolicitudCredito,
    VehiculoCatalogo,
)
from backend.db_models.session import get_db
from backend.routes.dependencies import get_tasa_mercado_service
from backend.services.tasa_mercado_service import (
    TasasMercado,
    TasaMercadoService,
)

router = APIRouter(tags=["catalogos"], dependencies=[Depends(usuario_actual)])


class ProductoResponse(BaseModel):
    id_aliado_producto: int
    id_aliado: int
    nombre: str
    aliado: str
    tasa_min: Decimal | None
    tasa_max: Decimal | None
    plazo_min_meses: int | None
    plazo_max_meses: int | None
    monto_min: Decimal | None
    monto_max: Decimal | None


@router.get("/productos", response_model=list[ProductoResponse])
def productos(db: Session = Depends(get_db)) -> list[ProductoResponse]:
    filas = (
        db.query(AliadoProducto, AliadoFinanciero.nombre)
        .join(AliadoFinanciero, AliadoProducto.id_aliado == AliadoFinanciero.id_aliado)
        .filter(AliadoProducto.activo.is_(True), AliadoFinanciero.activo.is_(True))
        .order_by(AliadoProducto.id_aliado_producto)
        .all()
    )
    return [
        ProductoResponse(
            id_aliado_producto=p.id_aliado_producto,
            id_aliado=p.id_aliado,
            nombre=p.nombre,
            aliado=nombre_aliado,
            tasa_min=p.tasa_min,
            tasa_max=p.tasa_max,
            plazo_min_meses=p.plazo_min_meses,
            plazo_max_meses=p.plazo_max_meses,
            monto_min=p.monto_min,
            monto_max=p.monto_max,
        )
        for p, nombre_aliado in filas
    ]


class VehiculoCatalogoResponse(BaseModel):
    """Fila del listado de precios vigente: precarga la hoja de negocio
    al elegir la referencia en la etapa de oferta."""

    id_vehiculo_catalogo: int
    marca: str
    referencia: str
    precio_lista: Decimal
    bono_pesos: Decimal | None
    soat: Decimal | None
    matricula: Decimal | None
    impuesto: Decimal | None


@router.get("/catalogos/vehiculos", response_model=list[VehiculoCatalogoResponse])
def vehiculos_catalogo(
    marca: str | None = None,
    db: Session = Depends(get_db),
) -> list[VehiculoCatalogoResponse]:
    """Listado de precios vigente, opcionalmente filtrado por marca.

    Ordenado por precio ascendente, como el listado comercial.
    """
    q = db.query(VehiculoCatalogo).filter(VehiculoCatalogo.activo.is_(True))
    if marca:
        q = q.filter(VehiculoCatalogo.marca == marca)
    return [
        VehiculoCatalogoResponse(
            id_vehiculo_catalogo=v.id_vehiculo_catalogo,
            marca=v.marca,
            referencia=v.referencia,
            precio_lista=v.precio_lista,
            bono_pesos=v.bono_pesos,
            soat=v.soat,
            matricula=v.matricula,
            impuesto=v.impuesto,
        )
        for v in q.order_by(VehiculoCatalogo.precio_lista).all()
    ]


class TasaModalidadResponse(BaseModel):
    modalidad: str
    tasa_ea: float
    tasa_mv: float
    usura_ea: float
    usura_mv: float
    vigencia_desde: str
    vigencia_hasta: str
    resolucion: str


class TasaMercadoResponse(BaseModel):
    umbral_bajo_monto: int
    fuente: str
    bajo_monto: TasaModalidadResponse
    ordinario: TasaModalidadResponse


@router.get("/tasa-mercado", response_model=TasaMercadoResponse)
def tasa_mercado(
    servicio: TasaMercadoService = Depends(get_tasa_mercado_service),
) -> TasasMercado:
    """TIBC vigente de la SFC para las dos modalidades de consumo.

    El simulador precarga la usura de consumo ordinario en m.v. (la
    referencia que publican los medios) y topa la tasa editable con la
    usura de la modalidad que aplique al monto financiado (bajo monto
    hasta 6 SMMLV, ordinario por encima). Un fallo de la fuente
    externa se traduce en 502 vía middleware.
    """
    return servicio.tasas()


class BancoResponse(BaseModel):
    id_banco: int
    codigo_ach: str | None
    nombre: str


@router.get("/bancos", response_model=list[BancoResponse])
def bancos(db: Session = Depends(get_db)) -> list[BancoResponse]:
    """Bancos activos para la cuenta receptora del desembolso."""
    return [
        BancoResponse(id_banco=b.id_banco, codigo_ach=b.codigo_ach, nombre=b.nombre)
        for b in (
            db.query(Banco)
            .filter(Banco.activo.is_(True))
            .order_by(Banco.nombre)
            .all()
        )
    ]


class OpcionesFiltroResponse(BaseModel):
    """Catálogos de los filtros dimensionales del panel (sede/asesor)."""

    concesionarios: list["ConcesionarioOpcion"]
    asesores: list["AsesorFiltroOpcion"]


class ConcesionarioOpcion(BaseModel):
    id_concesionario: int
    nombre: str


class AsesorFiltroOpcion(BaseModel):
    id_asesor: int
    nombre: str
    id_concesionario: int | None = None


@router.get("/catalogos/opciones-filtro", response_model=OpcionesFiltroResponse)
def opciones_filtro(
    usuario: UsuarioActual = Depends(usuario_actual),
    db: Session = Depends(get_db),
) -> OpcionesFiltroResponse:
    """Opciones de los filtros del panel, acotadas al alcance del usuario.

    El aliado las usa para el reporte de comisiones por radicador;
    el asesor solo se lista a sí mismo (su alcance ya es el suyo).
    """
    sedes = usuario.concesionario_ids()
    q_concesionarios = db.query(Concesionario)
    if sedes is not None:
        q_concesionarios = q_concesionarios.filter(
            Concesionario.id_concesionario.in_(sedes)
        )
    q_asesores = db.query(Asesor)
    propios = usuario.asesor_ids()
    if propios is not None:
        q_asesores = q_asesores.filter(Asesor.id_asesor.in_(propios))
    elif sedes is not None:
        q_asesores = q_asesores.filter(Asesor.id_concesionario.in_(sedes))
    return OpcionesFiltroResponse(
        concesionarios=[
            ConcesionarioOpcion(
                id_concesionario=c.id_concesionario, nombre=c.nombre
            )
            for c in q_concesionarios.order_by(Concesionario.nombre).all()
        ],
        asesores=[
            AsesorFiltroOpcion(
                id_asesor=a.id_asesor,
                nombre=a.nombre,
                id_concesionario=a.id_concesionario,
            )
            for a in q_asesores.order_by(Asesor.nombre).all()
        ],
    )


class MarcaResumen(BaseModel):
    """Resumen por marca para Ajustes → Concesionarios: sedes y asesores
    que la operan, solicitudes radicadas, créditos y monto ya
    financiado."""

    marca: str
    sedes: list[str]
    asesores: int
    radicadas: int
    creditos: int
    monto_usado: float


class MarcaCrearBody(BaseModel):
    nombre: str


def _clave_marca(nombre: str) -> str:
    return nombre.strip().upper()


# Submarcas distribuidas por Auteco (igual que SUBMARCAS_AUTECO del
# frontend): su actividad se consolida en la tarjeta del concesionario
# padre — TVS, Victory, etc. no son concesionarios propios.
_MARCA_PADRE = {
    "CERONTE": "Auteco",
    "KYMCO": "Auteco",
    "TVS": "Auteco",
    "VICTORY": "Auteco",
    "ZONTES": "Auteco",
}


def _clave_padre(clave: str) -> str:
    return _MARCA_PADRE.get(clave, clave).upper()


def _resumen_marcas(db: Session) -> list[MarcaResumen]:
    """Marcas aliadas con su operación real.

    La marca existe si está en el catálogo (``marca_vehiculo`` /
    ``vehiculo_catalogo``), si ya se radicó con ella
    (``producto_vehiculo``) o si algún usuario la lleva en su ficha.
    El monto usado suma ``valor_financiacion`` de los créditos — la misma
    convención que Analítica (crédito registrado o solicitud
    desembolsada)."""
    clave_base = func.upper(func.trim(ProductoVehiculo.marca))
    clave = case(
        (clave_base.in_(tuple(_MARCA_PADRE)), "AUTECO"), else_=clave_base
    )
    nombres: dict[str, str] = {}
    for (m,) in (
        db.query(VehiculoCatalogo.marca)
        .filter(VehiculoCatalogo.activo.is_(True))
        .distinct()
    ):
        k = _clave_marca(m)
        nombres.setdefault(_clave_padre(k), _MARCA_PADRE.get(k, m.strip()))
    for (m,) in db.query(MarcaVehiculo.nombre).filter(
        MarcaVehiculo.activo.is_(True)
    ):
        k = _clave_marca(m)
        nombres.setdefault(_clave_padre(k), _MARCA_PADRE.get(k, m.strip()))

    hay_marca = and_(
        ProductoVehiculo.marca.is_not(None),
        func.trim(ProductoVehiculo.marca) != "",
    )
    actividad = (
        db.query(
            clave.label("k"),
            func.min(ProductoVehiculo.marca).label("raw"),
            func.count(func.distinct(SolicitudCredito.id_solicitud)).label(
                "rad"
            ),
        )
        .select_from(ProductoVehiculo)
        .join(
            SolicitudCredito,
            ProductoVehiculo.id_solicitud == SolicitudCredito.id_solicitud,
        )
        .filter(hay_marca)
        .group_by(clave)
        .all()
    )
    for fila in actividad:
        nombres.setdefault(fila.k, fila.raw.strip())

    sedes: dict[str, set[str]] = {}
    asesores: dict[str, set[int]] = {}
    # Sedes oficiales del catálogo: cada concesionario con marca declarada
    # aporta su etiqueta de sede; la marca sin sedes queda con lista
    # vacía (el punto de venta existe pero no tiene sede propia).
    for k, sede_etiqueta, marca_nombre in (
        db.query(
            func.upper(func.trim(Concesionario.marca)),
            Concesionario.sede,
            Concesionario.marca,
        )
        .filter(Concesionario.marca.is_not(None))
        .all()
    ):
        k = _clave_padre(k)
        nombres.setdefault(k, _MARCA_PADRE.get(k, marca_nombre))
        if sede_etiqueta:
            sedes.setdefault(k, set()).add(sede_etiqueta)
    # Sedes que radican cada marca: solo puntos de venta con etiqueta de
    # sede declarada; una radicación en la matriz no es "sede" de marca.
    for k, nombre_sede in (
        db.query(clave.label("k"), Concesionario.sede)
        .select_from(ProductoVehiculo)
        .join(
            SolicitudCredito,
            ProductoVehiculo.id_solicitud == SolicitudCredito.id_solicitud,
        )
        .join(
            Concesionario,
            SolicitudCredito.id_concesionario
            == Concesionario.id_concesionario,
        )
        .filter(hay_marca, Concesionario.sede.is_not(None))
        .distinct()
    ):
        sedes.setdefault(k, set()).add(nombre_sede)
    for k, id_asesor in (
        db.query(clave.label("k"), SolicitudCredito.id_asesor)
        .select_from(ProductoVehiculo)
        .join(
            SolicitudCredito,
            ProductoVehiculo.id_solicitud == SolicitudCredito.id_solicitud,
        )
        .filter(hay_marca, SolicitudCredito.id_asesor.is_not(None))
        .distinct()
    ):
        asesores.setdefault(k, set()).add(id_asesor)

    # La etiqueta de sede pertenece a la marca principal del usuario;
    # el conjunto completo (usuario_marca) lo cuenta como asesor de
    # todas las marcas que atiende.
    clave_usuario = func.upper(func.trim(Usuario.marca))
    for k, sede in (
        db.query(clave_usuario.label("k"), Usuario.sede)
        .filter(
            Usuario.marca.is_not(None),
            Usuario.sede.is_not(None),
            func.trim(Usuario.sede) != "",
        )
        .distinct()
    ):
        k = _clave_padre(k)
        nombres.setdefault(k, _MARCA_PADRE.get(k, k.title()))
        sedes.setdefault(k, set()).add(sede.strip())
    clave_marca_usuario = func.upper(func.trim(UsuarioMarca.marca))
    for k, id_asesor in (
        db.query(clave_marca_usuario.label("k"), Asesor.id_asesor)
        .join(UsuarioMarca, UsuarioMarca.id_usuario == Asesor.id_usuario)
        .distinct()
    ):
        k = _clave_padre(k)
        nombres.setdefault(k, _MARCA_PADRE.get(k, k.title()))
        asesores.setdefault(k, set()).add(id_asesor)

    financiado = (
        db.query(
            clave.label("k"),
            func.count(func.distinct(SolicitudCredito.id_solicitud)).label(
                "creditos"
            ),
            func.coalesce(
                func.sum(CreditoFinanciacion.valor_financiacion), 0
            ).label("monto"),
        )
        .select_from(ProductoVehiculo)
        .join(
            SolicitudCredito,
            ProductoVehiculo.id_solicitud == SolicitudCredito.id_solicitud,
        )
        .outerjoin(
            CreditoFinanciacion,
            CreditoFinanciacion.id_vehiculo == ProductoVehiculo.id_vehiculo,
        )
        .filter(
            hay_marca,
            or_(
                CreditoFinanciacion.id_credito.is_not(None),
                SolicitudCredito.estado == "desembolsada",
            ),
        )
        .group_by(clave)
        .all()
    )
    creditos = {f.k: int(f.creditos) for f in financiado}
    montos = {f.k: float(f.monto) for f in financiado}
    radicadas = {f.k: int(f.rad) for f in actividad}
    return sorted(
        (
            MarcaResumen(
                marca=nombre,
                sedes=sorted(sedes.get(k, set()), key=str.lower),
                asesores=len(asesores.get(k, set())),
                radicadas=radicadas.get(k, 0),
                creditos=creditos.get(k, 0),
                monto_usado=round(montos.get(k, 0.0), 2),
            )
            for k, nombre in nombres.items()
        ),
        key=lambda m: (-m.monto_usado, m.marca.lower()),
    )


@router.get(
    "/catalogos/marcas-resumen",
    response_model=list[MarcaResumen],
    dependencies=[Depends(requiere_roles("admin"))],
)
def marcas_resumen(db: Session = Depends(get_db)) -> list[MarcaResumen]:
    return _resumen_marcas(db)


@router.post(
    "/catalogos/marcas",
    response_model=list[MarcaResumen],
    dependencies=[Depends(requiere_roles("admin"))],
)
def crear_marca(
    body: MarcaCrearBody, db: Session = Depends(get_db)
) -> list[MarcaResumen]:
    """Alta de marca en el catálogo (Ajustes → Concesionarios)."""
    nombre = body.nombre.strip()
    if not nombre:
        raise HTTPException(400, "El nombre de la marca es obligatorio.")
    existente = (
        db.query(MarcaVehiculo)
        .filter(func.upper(MarcaVehiculo.nombre) == nombre.upper())
        .first()
    )
    if existente is None:
        db.add(MarcaVehiculo(nombre=nombre, activo=True))
        db.commit()
    elif not existente.activo:
        existente.activo = True
        db.commit()
    return _resumen_marcas(db)
