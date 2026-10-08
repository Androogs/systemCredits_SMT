"""Rate limiting por IP sobre métodos mutadores (POST/PUT/PATCH/DELETE).

Ventana deslizante en memoria, sin dependencias externas: suficiente para el
monolito modular del MVP. Con múltiples réplicas o workers debe moverse a un
almacén compartido (Redis — ver cronograma D94).

Los tests con TestClient (`client.host == "testclient"`) quedan exentos para
no falsear la suite; la lógica se prueba inyectando scopes con IP propia.
"""

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

METODOS_LIMITADOS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_peticiones: int, ventana_seg: float) -> None:
        super().__init__(app)
        self._max = max_peticiones
        self._ventana = ventana_seg
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.method not in METODOS_LIMITADOS:
            return await call_next(request)

        cliente = request.client.host if request.client else "desconocido"
        if cliente == "testclient":
            return await call_next(request)

        ahora = time.monotonic()
        hits = self._hits[cliente]
        while hits and ahora - hits[0] > self._ventana:
            hits.popleft()
        if not hits:
            self._hits.pop(cliente, None)  # no acumular IPs vacías
            hits = self._hits[cliente]

        if len(hits) >= self._max:
            espera = max(1, int(self._ventana - (ahora - hits[0])))
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit",
                    "detail": f"Demasiadas peticiones. Intenta de nuevo en {espera} segundos.",
                },
                headers={"Retry-After": str(espera)},
            )

        hits.append(ahora)
        return await call_next(request)
