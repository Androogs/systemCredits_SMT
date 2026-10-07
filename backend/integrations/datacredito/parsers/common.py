"""Helpers comunes para los parsers de Experian (HDC+ y Valor Ingreso)."""

from decimal import Decimal, InvalidOperation
from typing import Any


def _dec(value: Any, default: Decimal | None = Decimal(0)) -> Decimal | None:
    """Convierte un valor a Decimal de forma segura."""
    if value is None or value == "" or value == "-1":
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _int(value: Any, default: int | None = 0) -> int | None:
    """Convierte un valor a int de forma segura."""
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _str(value: Any) -> str | None:
    """Normaliza códigos que el proveedor puede serializar como números."""
    if value is None or value == "":
        return None
    return str(value)
