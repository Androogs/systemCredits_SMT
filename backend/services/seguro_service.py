"""Seguro de vida deudores incluido en la cuota.

La prima es un porcentaje mensual sobre el saldo financiado (0,35 %
según el negocio; la línea 'VALOR SEGURO DE VIDA' de la solicitud
impresa):

    cuota_seguro = saldo_financiado * tasa_prima / 100
    valor_seguro_vida = cuota_seguro * plazo

La cuota que ve el cliente (oferta, pagaré, carta) es siempre la
cuota TOTAL: anualidad del crédito + cuota_seguro.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.db_models.models import SeguroProducto

_CIENTO = Decimal(100)


def seguro_vida_vigente(db: Session) -> SeguroProducto | None:
    """Producto de seguro de vida activo; None si el catálogo no tiene
    ninguno configurado (la cuota entonces es solo la anualidad)."""
    return (
        db.query(SeguroProducto)
        .filter(
            SeguroProducto.tipo == "vida_decreciente",
            SeguroProducto.activo.is_(True),
            SeguroProducto.tasa_prima.is_not(None),
        )
        .order_by(SeguroProducto.id_seguro_producto)
        .first()
    )


def cuota_seguro(monto: Decimal | int | float | None, tasa_prima_pct: Decimal | float | None) -> Decimal:
    """Prima mensual: porcentaje del saldo financiado inicial."""
    if monto is None or tasa_prima_pct is None:
        return Decimal(0)
    return Decimal(str(monto)) * Decimal(str(tasa_prima_pct)) / _CIENTO
