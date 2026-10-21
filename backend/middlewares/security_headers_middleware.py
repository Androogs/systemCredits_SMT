"""Headers de seguridad HTTP en todas las respuestas.

Defensa en profundidad: el endpoint de contenido de evidencias sirve
archivos subidos por usuarios — `nosniff` impide que el navegador los
interprete como HTML/JS aunque el MIME almacenado sea incorrecto.
`X-Frame-Options: DENY` bloquea clickjacking y `Referrer-Policy:
no-referrer` evita filtrar rutas (uuid de firma, tokens de captura)
vía Referer a terceros.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        respuesta = await call_next(request)
        for nombre, valor in _HEADERS.items():
            respuesta.headers.setdefault(nombre, valor)
        return respuesta
