"""
Traducción de excepciones del motor a respuestas HTTP explícitas.

    ValidacionError / IdentidadNoCoincideError  -> 422
    ParametrosError                             -> 422
    ReporteBuroNoEvaluableError                 -> 422
    SolicitudNoEncontradaError                  -> 404
    ReglaNoDefinidaError                        -> 501 (regla de negocio pendiente, no bug)
    DataCreditoError / AuthError                -> 502
    Cualquier otra                              -> 500 (se registra con traza)
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.services.motor_exceptions import (
    ConflictoEstadoError,
    DataCreditoError,
    ParametrosError,
    ReglaNoDefinidaError,
    ReporteBuroNoEvaluableError,
    SolicitudNoEncontradaError,
    ValidacionError,
)
from backend.utils.loggers import get_logger

logger = get_logger("motor_decision.errores")

_MAPA = [
    (SolicitudNoEncontradaError, 404, "no_encontrado"),
    (ValidacionError, 422, "validacion"),
    (ParametrosError, 422, "parametros_invalidos"),
    (ReporteBuroNoEvaluableError, 422, "reporte_buro_no_evaluable"),
    (ConflictoEstadoError, 409, "conflicto_estado"),
    (ReglaNoDefinidaError, 501, "regla_no_definida"),
    (DataCreditoError, 502, "error_datacredito"),
]


def registrar_manejadores(app: FastAPI) -> None:
    for tipo, status, codigo in _MAPA:

        def _handler(request: Request, exc: Exception, status=status, codigo=codigo) -> JSONResponse:
            logger.warning("%s en %s: %s", codigo, request.url.path, exc)
            return JSONResponse(status_code=status, content={"error": codigo, "detail": str(exc)})

        app.add_exception_handler(tipo, _handler)

    @app.exception_handler(Exception)
    def _no_controlada(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Error no controlado en %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "error_interno", "detail": "Error interno del motor. Revisa los logs."},
        )
