"""Logs estructurados JSON (D96 re-scoped): cada línea es un documento
consultable por jq/docker logs con el contexto de la trazabilidad."""

import io
import json
import logging

from backend.utils import loggers


def _capturar(nombre: str, monkeypatch, formato: str | None = None) -> io.StringIO:
    monkeypatch.delenv("LOG_FORMAT", raising=False)
    if formato is not None:
        monkeypatch.setenv("LOG_FORMAT", formato)
    salida = io.StringIO()
    logger = loggers.get_logger(nombre, handler=logging.StreamHandler(salida))
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return salida


def test_log_emite_json_con_campos_base(monkeypatch):
    salida = _capturar("test.json", monkeypatch)
    logger = logging.getLogger("test.json")
    logger.info("HDC+ respondió | status=%s", 200)

    doc = json.loads(salida.getvalue())
    assert doc["nivel"] == "INFO"
    assert doc["logger"] == "test.json"
    assert doc["mensaje"] == "HDC+ respondió | status=200"
    assert doc["ts"].endswith("+00:00") or "T" in doc["ts"]


def test_log_json_incluye_campos_de_contexto_extra(monkeypatch):
    salida = _capturar("test.ctx", monkeypatch)
    logger = logging.getLogger("test.ctx")
    logger.info(
        "Solicitud evaluada",
        extra={"id_solicitud": "abc-123", "endpoint": "/api/solicitudes/abc/evaluar"},
    )

    doc = json.loads(salida.getvalue())
    assert doc["id_solicitud"] == "abc-123"
    assert doc["endpoint"] == "/api/solicitudes/abc/evaluar"


def test_log_json_serializa_excepciones(monkeypatch):
    salida = _capturar("test.exc", monkeypatch)
    logger = logging.getLogger("test.exc")
    try:
        raise ValueError("fallo de prueba")
    except ValueError:
        logger.exception("Error en evaluación")

    doc = json.loads(salida.getvalue())
    assert "ValueError" in doc["excepcion"]
    assert "fallo de prueba" in doc["excepcion"]


def test_log_formato_texto_sigue_disponible(monkeypatch):
    salida = _capturar("test.txt", monkeypatch, formato="texto")
    logger = logging.getLogger("test.txt")
    logger.info("mensaje plano")

    linea = salida.getvalue()
    assert "mensaje plano" in linea
    assert not linea.lstrip().startswith("{")
