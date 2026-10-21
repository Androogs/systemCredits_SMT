"""Access log estructurado: una línea JSON por request HTTP.

Emite metodo, endpoint, status y duración; si la ruta es de una
solicitud (/api/solicitudes/{uuid}/...) extrae `id_solicitud` para
correlacionar la trazabilidad del ciclo de originación en los logs
(`docker logs | jq 'select(.id_solicitud=="…")'`).
"""

import re
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.utils.loggers import get_logger

logger = get_logger("creditos.http")

_RUTA_SOLICITUD = re.compile(r"/api/solicitudes/([0-9a-fA-F-]{36})(?:/|$)")

# Preflight CORS y health: ruido sin valor de trazabilidad.
_METODOS_OMITIDOS = frozenset({"OPTIONS"})
_RUTAS_OMITIDAS = frozenset({"/api/health"})


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if (
            request.method in _METODOS_OMITIDOS
            or request.url.path in _RUTAS_OMITIDAS
        ):
            return await call_next(request)

        inicio = time.perf_counter()
        respuesta = await call_next(request)
        duracion_ms = round((time.perf_counter() - inicio) * 1000, 1)

        extra = {
            "metodo": request.method,
            "endpoint": request.url.path,
            "status": respuesta.status_code,
            "duracion_ms": duracion_ms,
        }
        if match := _RUTA_SOLICITUD.search(request.url.path):
            extra["id_solicitud"] = match.group(1)

        if respuesta.status_code >= 500:
            logger.error("HTTP %s", respuesta.status_code, extra=extra)
        else:
            logger.info("HTTP %s", respuesta.status_code, extra=extra)
        return respuesta
