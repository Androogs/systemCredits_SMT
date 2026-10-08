"""Rate limiting por IP sobre métodos mutadores (D64)."""

import asyncio

from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.middlewares.rate_limit_middleware import RateLimitMiddleware


def _request(method: str = "POST", ip: str = "10.0.0.1") -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/api/solicitudes",
            "client": (ip, 5000),
            "headers": [],
        }
    )


async def _ok(_request):
    return JSONResponse({"ok": True})


def _despachar(middleware: RateLimitMiddleware, request: Request):
    return asyncio.run(middleware.dispatch(request, _ok))


def test_deja_pasar_peticiones_bajo_el_limite():
    mw = RateLimitMiddleware(app=None, max_peticiones=3, ventana_seg=60)
    for _ in range(3):
        respuesta = _despachar(mw, _request())
        assert respuesta.status_code == 200


def test_bloquea_con_429_al_superar_el_limite():
    mw = RateLimitMiddleware(app=None, max_peticiones=2, ventana_seg=60)
    _despachar(mw, _request())
    _despachar(mw, _request())
    respuesta = _despachar(mw, _request())
    assert respuesta.status_code == 429
    assert respuesta.headers["Retry-After"] is not None


def test_el_limite_es_por_ip():
    mw = RateLimitMiddleware(app=None, max_peticiones=1, ventana_seg=60)
    assert _despachar(mw, _request(ip="1.1.1.1")).status_code == 200
    assert _despachar(mw, _request(ip="2.2.2.2")).status_code == 200
    assert _despachar(mw, _request(ip="1.1.1.1")).status_code == 429


def test_gets_no_cuentan_para_el_limite():
    mw = RateLimitMiddleware(app=None, max_peticiones=1, ventana_seg=60)
    for _ in range(10):
        assert _despachar(mw, _request(method="GET")).status_code == 200


def test_testclient_queda_exento():
    mw = RateLimitMiddleware(app=None, max_peticiones=1, ventana_seg=60)
    for _ in range(5):
        assert _despachar(mw, _request(ip="testclient")).status_code == 200
