"""Utilidades de fecha compartidas (antes duplicadas en 3 módulos)."""

from datetime import date


def calcular_edad(fecha_nacimiento: date, fecha_referencia: date) -> int:
    """Edad en años cumplidos a la fecha de referencia."""
    return (
        fecha_referencia.year
        - fecha_nacimiento.year
        - ((fecha_referencia.month, fecha_referencia.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    )
