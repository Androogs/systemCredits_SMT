"""Matriz de autorización: 401 sin sesión, 403 rol insuficiente,
alcance por rol, y endpoints deliberadamente públicos."""

from backend.services.jwt_service import JwtService
from backend.config import get_settings


def test_solicitudes_sin_token_responde_401(client_sin_auth):
    assert client_sin_auth.get("/api/solicitudes").status_code == 401


def test_token_basura_responde_401(client_sin_auth):
    respuesta = client_sin_auth.get(
        "/api/solicitudes", headers={"Authorization": "Bearer no-es-jwt"}
    )
    assert respuesta.status_code == 401


def test_token_expirado_responde_401(client_sin_auth, usuarios_prueba):
    import uuid
    from datetime import datetime, timedelta, timezone

    import jwt as pyjwt

    settings = get_settings()
    ahora = datetime.now(timezone.utc)
    token = pyjwt.encode(
        {
            "sub": str(uuid.uuid5(uuid.NAMESPACE_DNS, "a")),
            "roles": ["admin"],
            "iat": int((ahora - timedelta(hours=9)).timestamp()),
            "exp": int((ahora - timedelta(hours=1)).timestamp()),
        },
        settings.jwt_secreto_efectivo(),
        algorithm="HS256",
    )
    respuesta = client_sin_auth.get(
        "/api/solicitudes", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 401


def test_admin_accede_parametros(client):
    assert client.get("/api/parametros").status_code == 200


def test_asesor_no_accede_parametros(client_asesor):
    assert client_asesor.get("/api/parametros").status_code == 403
    assert client_asesor.put("/api/parametros", json={}).status_code == 403


def test_asesor_no_accede_auditoria(client_asesor):
    assert client_asesor.get("/api/auditoria").status_code == 403


def test_aliado_no_accede_parametros_ni_auditoria(client_aliado):
    assert client_aliado.get("/api/parametros").status_code == 403
    assert client_aliado.get("/api/auditoria").status_code == 403


def test_aliado_no_puede_mutar_solicitudes(client_aliado):
    """Rol de solo lectura: las mutaciones responden 403 aunque el
    cuerpo sea inválido (la autorización corre antes que la validación)."""
    assert client_aliado.post("/api/solicitudes", json={}).status_code == 403


def test_asesor_lista_solicitudes(client_asesor):
    assert client_asesor.get("/api/solicitudes").status_code == 200


def test_aliado_lista_solicitudes(client_aliado):
    assert client_aliado.get("/api/solicitudes").status_code == 200


def test_catalogo_requiere_sesion(client_sin_auth, client_asesor):
    assert client_sin_auth.get("/api/bancos").status_code == 401
    assert client_asesor.get("/api/bancos").status_code == 200


def test_motor_requiere_rol_operativo(client_sin_auth, client_aliado, client_asesor):
    assert client_sin_auth.get("/api/motor/escenarios").status_code == 401
    assert client_aliado.get("/api/motor/escenarios").status_code == 403
    assert client_asesor.get("/api/motor/escenarios").status_code == 200


def test_endpoints_publicos_siguen_abiertos(client_sin_auth):
    """Estos puntos no llevan sesión por diseño (ver matriz del spec):
    ninguno debe responder 401 por falta de token."""
    assert client_sin_auth.get("/api/health").status_code == 200
    # Login: la ruta existe y valida credenciales, no sesión.
    assert (
        client_sin_auth.post(
            "/api/auth/login", json={"correo": "x@y.co", "contrasena": "z"}
        ).status_code
        == 401  # credenciales malas, no sesión requerida
    )
    # Captura pública: token de sesión inválido → no es 401 (es 404 del
    # recurso), la puerta es el propio token del enlace.
    respuesta = client_sin_auth.get("/api/captura/token-inexistente")
    assert respuesta.status_code != 401
