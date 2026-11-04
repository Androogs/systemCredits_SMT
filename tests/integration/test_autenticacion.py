"""Pruebas de autenticación real: login contra `usuario` en BD + JWT.

El fixture `usuarios_prueba` (conftest) siembra los tres usuarios del
entorno demo: admin@ / asesor@ / aliado@sumoto.com.co.
"""

import uuid

import jwt
import pytest
from sqlalchemy import text

from backend.db_models.session import SessionLocal

CLAVE_ADMIN = "Admin123!"
CLAVE_ASESOR = "Asesor123!"
CLAVE_ALIADO = "Aliado123!"


def _login(client, correo, contrasena):
    return client.post(
        "/api/auth/login",
        json={"correo": correo, "contrasena": contrasena},
    )


def test_login_devuelve_jwt_y_usuario(client, usuarios_prueba):
    respuesta = _login(client, "admin@sumoto.com.co", CLAVE_ADMIN)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["usuario"]["correo"] == "admin@sumoto.com.co"
    assert cuerpo["usuario"]["rol"] == "admin"

    claims = jwt.decode(
        cuerpo["access_token"], options={"verify_signature": False}
    )
    assert claims["sub"] == str(
        uuid.UUID(usuarios_prueba["admin"]["id_usuario"])
    )
    assert claims["roles"] == ["admin"]
    assert claims["exp"] - claims["iat"] == 8 * 3600


def test_login_normaliza_correo(client, usuarios_prueba):
    respuesta = _login(client, "  ADMIN@SUMOTO.COM.CO ", CLAVE_ADMIN)
    assert respuesta.status_code == 200


def test_login_asesor_trae_su_concesionario(client, usuarios_prueba):
    respuesta = _login(client, "asesor@sumoto.com.co", CLAVE_ASESOR)

    assert respuesta.status_code == 200
    usuario = respuesta.json()["usuario"]
    assert usuario["rol"] == "asesor"
    assert usuario["concesionario"]["nombre"] == "CONCESIONARIO AUTH PRUEBA"


def test_login_con_varios_roles_devuelve_el_mas_privilegiado(
    client, usuarios_prueba, monkeypatch
):
    """Con varios roles asignados, `usuario.rol` debe ser el de mayor
    privilegio (orden de AUTH_ROLES_PANEL), no el primero que devuelva
    el JOIN — de él depende qué vista compone el panel. El orden real
    del JOIN no está garantizado (en Postgres devolvió 'asesor'
    primero), así que se simula el orden adverso directamente."""
    from backend.repositories.usuario_repository import UsuarioRepository

    monkeypatch.setattr(
        UsuarioRepository,
        "roles_de",
        lambda self, _uid: ["asesor", "aliado", "cliente",
                            "contabilidad", "admin"],
    )

    respuesta = _login(client, "admin@sumoto.com.co", CLAVE_ADMIN)

    assert respuesta.status_code == 200
    usuario = respuesta.json()["usuario"]
    assert usuario["rol"] == "admin"
    assert set(usuario["roles"]) >= {"admin", "asesor", "aliado"}


def test_login_rechaza_contrasena_incorrecta(client, usuarios_prueba):
    respuesta = _login(client, "admin@sumoto.com.co", "incorrecta")

    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == "Correo o contraseña incorrectos."


def test_login_rechaza_correo_desconocido_sin_oraculo(client, usuarios_prueba):
    respuesta = _login(client, "nadie@sumoto.com.co", "x")

    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == "Correo o contraseña incorrectos."


def test_login_rechaza_usuario_no_activo(client, usuarios_prueba):
    with SessionLocal() as db:
        db.execute(
            text("UPDATE usuario SET estado='bloqueado' WHERE correo='asesor@sumoto.com.co'")
        )
        db.commit()

    respuesta = _login(client, "asesor@sumoto.com.co", CLAVE_ASESOR)
    assert respuesta.status_code == 403


def test_login_bloquea_tras_intentos_fallidos(client, usuarios_prueba):
    for _ in range(5):
        respuesta = _login(client, "asesor@sumoto.com.co", "mala")
        assert respuesta.status_code == 401

    # La contraseña correcta tampoco entra: la cuenta quedó bloqueada.
    respuesta = _login(client, "asesor@sumoto.com.co", CLAVE_ASESOR)
    assert respuesta.status_code == 403

    with SessionLocal() as db:
        bloqueado_hasta = db.execute(
            text(
                "SELECT bloqueado_hasta FROM usuario "
                "WHERE correo='asesor@sumoto.com.co'"
            )
        ).scalar_one()
    assert bloqueado_hasta is not None


def test_login_registra_auditoria(client, usuarios_prueba):
    _login(client, "admin@sumoto.com.co", CLAVE_ADMIN)
    _login(client, "admin@sumoto.com.co", "mala")

    with SessionLocal() as db:
        acciones = [
            fila[0]
            for fila in db.execute(
                text(
                    "SELECT accion FROM auditoria_usuario "
                    "WHERE id_usuario = :u ORDER BY fecha_hora"
                ),
                {"u": usuarios_prueba["admin"]["id_usuario"]},
            ).fetchall()
        ]
    assert "login_exitoso" in acciones
    assert "login_fallido" in acciones


def test_login_rechaza_rol_sin_acceso_al_panel(client, usuarios_prueba):
    """`cliente` y `contabilidad` no tienen vistas de panel: el login se
    rechaza en vez de emitir un token que 403-ee todo."""
    with SessionLocal() as db:
        id_usuario = usuarios_prueba["asesor"]["id_usuario"]
        db.execute(
            text(
                "UPDATE usuario_rol SET id_rol = ("
                "  SELECT id_rol FROM rol WHERE nombre='contabilidad') "
                "WHERE id_usuario = :u"
            ),
            {"u": id_usuario},
        )
        db.commit()

    respuesta = _login(client, "asesor@sumoto.com.co", CLAVE_ASESOR)
    assert respuesta.status_code == 403


def test_login_expira_seguridad_sin_secreto_en_produccion(
    client, usuarios_prueba, monkeypatch
):
    """Fuera de demo, JWT sin secreto configurado no emite tokens."""
    from backend.config import get_settings

    monkeypatch.setenv("ENVIRONMENT", "produccion")
    # Vacío explícito: la variable real le gana al .env del repo.
    monkeypatch.setenv("JWT_SECRETO", "")
    get_settings.cache_clear()
    try:
        respuesta = _login(client, "admin@sumoto.com.co", CLAVE_ADMIN)
    finally:
        get_settings.cache_clear()

    assert respuesta.status_code == 503
