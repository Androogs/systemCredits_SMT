"""Respuestas del reporte de comisiones del asesor (D134)."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ComisionFilaResponse(BaseModel):
    """Un desembolso confirmado del asesor con su comisión calculada."""

    id_desembolso: int
    num_desembolso: str | None
    num_solicitud: int | None
    nombre_cliente: str
    # Radicador de la solicitud; solo lo puebla la vista del admin.
    nombre_asesor: str | None = None
    fecha_desembolso: datetime | None
    capital: Decimal
    # Base de la comisión: capital desembolsado sin los gastos
    # administrativos de originación.
    base: Decimal
    comision: Decimal


class ComisionMesResponse(BaseModel):
    """Totales de un mes de desembolso (hora de Colombia)."""

    mes: str  # "YYYY-MM"
    desembolsos: int
    capital: Decimal
    comision: Decimal


class ComisionesResponse(BaseModel):
    """Reporte completo: filas por desembolso + totales por mes."""

    porcentaje: Decimal
    filas: list[ComisionFilaResponse]
    meses: list[ComisionMesResponse]
    total_desembolsos: int
    total_capital: Decimal
    total_base: Decimal
    total_comision: Decimal
