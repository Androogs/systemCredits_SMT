"""Reintentos con backoff exponencial y circuit breaker para DataCrédito.

Solo se reintentan errores transitorios: fallos de red (timeout, DNS,
conexión) y respuestas 408/429/5xx. Un 4xx o un JSON inválido propagan
de inmediato: repetir un request mal formado no sirve.

El circuit breaker cuenta llamadas fallidas consecutivas (después de
agotar reintentos); al llegar al umbral abre el circuito durante la
espera configurada y las llamadas siguientes fallan en el acto en vez
de golpear un Experian caído. Un éxito lo reinicia.
"""

import threading
import time
from collections.abc import Callable
from typing import TypeVar

from backend.config import Settings
from backend.services.motor_exceptions import DataCreditoError
from backend.utils.loggers import get_logger

logger = get_logger("motor_decision.datacredito.resiliencia")

T = TypeVar("T")

_REINTENTABLES = {408, 429, 500, 502, 503, 504}


def _es_reintentable(error: DataCreditoError) -> bool:
    return error.status_code is None or error.status_code in _REINTENTABLES


class CircuitBreaker:
    """Abre el circuito tras `max_fallos` fallos consecutivos."""

    def __init__(self, servicio: str, max_fallos: int, espera_segundos: float) -> None:
        self.servicio = servicio
        self.max_fallos = max_fallos
        self.espera_segundos = espera_segundos
        self._fallos = 0
        self._abierto_hasta = 0.0
        self._lock = threading.Lock()

    def verificar(self) -> None:
        with self._lock:
            restante = self._abierto_hasta - time.monotonic()
        if restante > 0:
            raise DataCreditoError(
                self.servicio,
                None,
                f"Circuit breaker abierto: {self.servicio} acumula fallos; "
                f"reintentar en {restante:.0f}s",
            )

    def exito(self) -> None:
        with self._lock:
            self._fallos = 0
            self._abierto_hasta = 0.0

    def fallo(self) -> None:
        with self._lock:
            self._fallos += 1
            if self._fallos >= self.max_fallos:
                self._abierto_hasta = time.monotonic() + self.espera_segundos
                self._fallos = 0
                logger.warning(
                    "Circuit breaker ABIERTO | servicio=%s espera=%ss",
                    self.servicio,
                    self.espera_segundos,
                )


_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def _breaker(servicio: str, settings: Settings) -> CircuitBreaker:
    with _breakers_lock:
        if servicio not in _breakers:
            _breakers[servicio] = CircuitBreaker(
                servicio,
                settings.experian_circuito_fallos,
                settings.experian_circuito_espera_seg,
            )
        return _breakers[servicio]


def llamar_con_resiliencia(
    servicio: str,
    settings: Settings,
    llamada: Callable[[], T],
) -> T:
    """
    Ejecuta `llamada` con reintentos + circuit breaker. La función debe
    lanzar `DataCreditoError` tanto para errores de red como para
    respuestas HTTP no exitosas.
    """
    breaker = _breaker(servicio, settings)
    breaker.verificar()
    intentos_totales = 1 + settings.experian_reintentos
    ultimo_error: DataCreditoError | None = None
    for intento in range(1, intentos_totales + 1):
        try:
            resultado = llamada()
        except DataCreditoError as exc:
            if not _es_reintentable(exc):
                raise
            ultimo_error = exc
            if intento < intentos_totales:
                espera = settings.experian_espera_reintento_seg * (2 ** (intento - 1))
                logger.warning(
                    "%s falló (intento %s/%s), reintento en %.1fs | %s",
                    servicio,
                    intento,
                    intentos_totales,
                    espera,
                    exc.message,
                )
                time.sleep(espera)
            continue
        breaker.exito()
        return resultado
    breaker.fallo()
    raise ultimo_error  # type: ignore[misc]
