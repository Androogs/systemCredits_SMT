"""Catálogos comerciales: productos de aliados con sus rangos vigentes."""

from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db_models.models import AliadoFinanciero, AliadoProducto, Banco
from backend.db_models.session import get_db
from backend.routes.dependencies import get_tasa_mercado_service
from backend.services.tasa_mercado_service import (
    TasasMercado,
    TasaMercadoService,
)

router = APIRouter(tags=["catalogos"])


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
