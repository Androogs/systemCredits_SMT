"""Catálogos comerciales: productos de aliados con sus rangos vigentes."""

from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.auth.dependencies import UsuarioActual, usuario_actual
from backend.db_models.auth_models import Asesor, Concesionario
from backend.db_models.models import AliadoFinanciero, AliadoProducto, Banco
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
