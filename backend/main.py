"""Punto de entrada FastAPI de la plataforma de originación de crédito.

Expone bajo /api las rutas del motor de decisión (Gold), solicitudes,
ofertas, parámetros y auditoría, con CORS habilitado para el frontend.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.db_models import session as db_session
from backend.middlewares.error_middleware import registrar_manejadores
from backend.middlewares.rate_limit_middleware import RateLimitMiddleware
from backend.routes import (
    auditoria_routes,
    auth_routes,
    carga_routes,
    catalogo_routes,
    comision_routes,
    evidencia_routes,
    health_routes,
    motor_routes,
    parametros_routes,
    solicitud_routes,
    usuario_routes,
    webhook_routes,
)
from backend.routes.dependencies import get_store
from backend.utils.loggers import get_logger

logger = get_logger("creditos.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(
        "Iniciando plataforma | ambiente=%s | smmlv=%s",
        settings.environment,
        settings.smmlv,
    )
    get_store().cargar()  # falla temprano si parametros.json es incoherente
    if settings.db_crear_tablas:
        db_session.crear_tablas()
    yield
    logger.info("Plataforma detenida")


def crear_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_title,
        description=(
            "Plataforma de consulta de crédito SUMOTO S.A. con la financiera "
            "aliada Inversiones Pacífico. "
            "Integra el motor de decisión Prefiltro_Cliente (BRD + PPT v4) "
            "con integración DataCrédito Experian."
        ),
        version=settings.app_version,
        lifespan=lifespan,
        # Docs y esquema solo en demo: en producción la superficie de
        # la API no se publicita (hallazgo del reporte OWASP).
        docs_url="/api-docs" if settings.environment == "demo" else None,
        redoc_url="/redoc" if settings.environment == "demo" else None,
        openapi_url=(
            "/api/openapi.json" if settings.environment == "demo" else None
        ),
    )

    from backend.middlewares.access_log_middleware import AccessLogMiddleware
    from backend.middlewares.security_headers_middleware import (
        SecurityHeadersMiddleware,
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AccessLogMiddleware)
    if settings.rate_limit_habilitado:
        app.add_middleware(
            RateLimitMiddleware,
            max_peticiones=settings.rate_limit_max_peticiones,
            ventana_seg=settings.rate_limit_ventana_seg,
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    registrar_manejadores(app)
    for modulo in (
        health_routes,
        auth_routes,
        motor_routes,
        solicitud_routes,
        auditoria_routes,
        parametros_routes,
        catalogo_routes,
        carga_routes,
        evidencia_routes,
        usuario_routes,
        comision_routes,
    ):
        app.include_router(modulo.router, prefix="/api")
    # El webhook vive fuera de /api: es una puerta externa del emisor
    # (POST /webhook/desembolso), no un recurso del panel.
    app.include_router(webhook_routes.router)
    return app


app = crear_app()
