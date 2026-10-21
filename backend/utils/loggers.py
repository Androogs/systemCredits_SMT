"""Logging de la plataforma.

Por defecto cada línea es un documento JSON (D96: logs estructurados
para trazabilidad — búsqueda con `docker logs | jq` sin infra extra).
`LOG_FORMAT=texto` devuelve el formato plano legible en desarrollo.

Los campos de contexto viajan con ``extra={}``:
``logger.info("Evaluada", extra={"id_solicitud": ..., "endpoint": ...})``
"""

import json
import logging
import os
from datetime import UTC, datetime

# Atributos propios de LogRecord: todo lo demás que llegue vía
# ``extra={}`` se propaga al documento JSON (id_solicitud, endpoint,
# usuario, metodo, status, duracion_ms, ...).
_RESERVADOS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None)))


class JsonFormatter(logging.Formatter):
    """Un documento JSON por línea: {ts, nivel, logger, mensaje, ...extras}."""

    def format(self, record: logging.LogRecord) -> str:
        doc: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
        }
        for campo, valor in record.__dict__.items():
            if campo not in _RESERVADOS and valor is not None:
                doc[campo] = valor
        if record.exc_info:
            doc["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(doc, ensure_ascii=False, default=str)


_FORMATO_TEXTO = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def get_logger(name: str, handler: logging.Handler | None = None) -> logging.Logger:
    logger = logging.getLogger(name)

    destino = handler if handler is not None else logging.StreamHandler()
    if os.getenv("LOG_FORMAT", "json").lower() == "texto":
        destino.setFormatter(logging.Formatter(_FORMATO_TEXTO))
    else:
        destino.setFormatter(JsonFormatter())

    # En tests se pasa un handler propio: se aplica de todas formas y se
    # reemplazan los existentes para no duplicar líneas entre casos.
    if handler is not None or not logger.handlers:
        if handler is not None:
            logger.handlers = [destino]
        else:
            logger.addHandler(destino)
        logger.setLevel(logging.INFO)

    return logger
