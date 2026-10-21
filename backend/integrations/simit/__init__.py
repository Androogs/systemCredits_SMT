"""Pre-filtro SIMIT: deuda de tránsito de la persona (fuente PlacaPi).

El SIMIT no tiene API oficial; PlacaPi es un servicio que la normaliza.
Se usa como pre-filtro antes de consumir la consulta de buró — más
cara—: con deuda pendiente la evaluación rechaza con la causal R22 del
BRD sin gastar la llamada a Experian.
"""

from backend.integrations.simit.client import PlacApiClient, ResultadoSimit

__all__ = ["PlacApiClient", "ResultadoSimit"]
