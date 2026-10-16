"""
Excepciones del motor de decisión.

backend/middlewares/error_middleware.py traduce cada una a un código
HTTP explícito, para que la respuesta deje claro si es un dato de
entrada, una regla pendiente, un problema del buró o un bug.
"""


class MotorError(Exception):
    """Base para errores del motor."""


class ReglaNoDefinidaError(MotorError):
    """
    El motor llegó a un punto que necesita una fórmula, ponderación o
    punto de corte aún no definido por negocio. HTTP 501 (no 500),
    para dejar claro que es una regla pendiente y no un bug.
    """

    def __init__(self, detalle: str) -> None:
        super().__init__(detalle)


class ParametrosError(MotorError):
    """Parámetros del motor inválidos o incoherentes. HTTP 422."""


class ValidacionError(MotorError):
    """Datos de entrada inválidos o incompletos para evaluar. HTTP 422."""


class IdentidadNoCoincideError(ValidacionError):
    """La solicitud y los reportes del buró son de personas distintas."""


class SolicitudNoEncontradaError(MotorError):
    """La solicitud (u oferta) pedida no existe. HTTP 404."""


class ConflictoEstadoError(MotorError):
    """La operación no es válida en el estado actual del recurso. HTTP 409."""


class DataCreditoError(MotorError):
    """Error al consumir un servicio de DataCrédito Experian. HTTP 502."""

    def __init__(self, service: str, status_code: int | None, message: str):
        self.service = service
        self.status_code = status_code
        self.message = message
        super().__init__(f"[{service}] {status_code}: {message}")


class AuthError(DataCreditoError):
    """Error de autenticación OAuth2 con el proveedor."""


class ReporteBuroNoEvaluableError(MotorError):
    """
    HDC+ respondió HTTP 200 pero sin un reporte evaluable (responseCode
    distinto de 13). No se emite decisión. HTTP 422.
    """

    def __init__(self, codigo: str | None, descripcion: str | None):
        self.codigo = codigo or "sin código"
        self.descripcion = descripcion or "HDC no generó un reporte evaluable."
        if self.codigo == "02":
            instruccion = "Verifica HDC_USERNAME y HDC_PASSWORD (credenciales de servicio HDC+)."
        elif self.codigo == "10":
            instruccion = "Verifica el tipo y número de documento y el primer apellido."
        else:
            instruccion = "Confirma con Experian el código de respuesta y la configuración HDC."
        super().__init__(
            f"HDC no generó un reporte evaluable (código {self.codigo}): "
            f"{self.descripcion} {instruccion} No se emitió decisión."
        )
