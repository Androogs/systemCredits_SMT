"""Refresh tokens con rotación/revocación (D125) y recuperación de
clave por correo con token de un solo uso (D124).

El token plano solo viaja al cliente por correo; en BD solo vive su
hash sha256 — las pruebas siembran filas con el hash de un token
conocido para ejercitar la verificación.
"""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from backend.db_models.session import SessionLocal

CLAVE_ASESOR = "Asesor123!"
CLAVE_NUEVA = "ClaveNueva9!"


def _login(client, correo="asesor@pacifico.co", contrasena=CLAVE_ASESOR):
    return client.post(
        "/api/auth/login",
        json={"correo": correo, "contrasena": contrasena},
    )


def _id_asesor() -> str:
    return uuid.uuid5(uuid.NAMESPACE_DNS, "asesor@pacifico.co").hex


def _sembrar_recuperacion(token_plano: str, *, expira_en, usado=False) -> None:
    with SessionLocal() as db:
        db.execute(
            text(
                "INSERT INTO token_recuperacion (id_usuario, token_hash, "
                "expira_en, usado) VALUES (:u, :h, :e, :usado)"
            ),
            {
                "u": _id_asesor(),
                "h": hashlib.sha256(token_plano.encode()).hexdigest(),
                "e": expira_en,
                "usado": 1 if usado else 0,
            },
        )
        db.commit()


def _contar(tabla: str, where: str = "") -> int:
    with SessionLocal() as db:
        return db.execute(
            text(f"SELECT COUNT(*) FROM {tabla} {where}")
        ).scalar_one()


# --------------------------- D125: refresh ---------------------------


def test_login_emite_refresh_token(client, usuarios_prueba):
    respuesta = _login(client)

    assert respuesta.status_code == 200
    assert respuesta.json()["refresh_token"]
    assert _contar("refresh_token") == 1


def test_refresh_rota_y_el_viejo_muere(client, usuarios_prueba):
    login = _login(client).json()
    token_viejo = login["refresh_token"]

    respuesta = client.post(
        "/api/auth/refresh", json={"refresh_token": token_viejo}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["refresh_token"] != token_viejo
    assert respuesta.json()["access_token"]
    assert respuesta.json()["usuario"]["correo"] == "asesor@pacifico.co"

    # Reuso del token ya rotado → 401 (antireplay).
    reuso = client.post(
        "/api/auth/refresh", json={"refresh_token": token_viejo}
    )
    assert reuso.status_code == 401

    # El nuevo sigue vivo.
    assert (
        client.post(
            "/api/auth/refresh",
            json={"refresh_token": respuesta.json()["refresh_token"]},
        ).status_code
        == 200
    )


def test_refresh_token_inventado_da_401(client):
    respuesta = client.post(
        "/api/auth/refresh", json={"refresh_token": "x" * 60}
    )
    assert respuesta.status_code == 401


def test_refresh_expirado_da_401(client, usuarios_prueba):
    token = _login(client).json()["refresh_token"]
    with SessionLocal() as db:
        db.execute(
            text(
                "UPDATE refresh_token SET expira_en = :pasado "
                "WHERE token_hash = :h"
            ),
            {
                "pasado": datetime.now(UTC) - timedelta(minutes=1),
                "h": hashlib.sha256(token.encode()).hexdigest(),
            },
        )
        db.commit()

    respuesta = client.post(
        "/api/auth/refresh", json={"refresh_token": token}
    )
    assert respuesta.status_code == 401


def test_logout_revoca_la_sesion(client, usuarios_prueba):
    token = _login(client).json()["refresh_token"]

    respuesta = client.post(
        "/api/auth/logout", json={"refresh_token": token}
    )
    assert respuesta.status_code == 200

    # La sesión ya no se puede renovar.
    assert (
        client.post(
            "/api/auth/refresh", json={"refresh_token": token}
        ).status_code
        == 401
    )
    # Idempotente: repetir el logout no revienta.
    assert (
        client.post(
            "/api/auth/logout", json={"refresh_token": token}
        ).status_code
        == 200
    )
    assert _contar("auditoria_usuario", "WHERE accion='logout'") == 1


def test_logout_sin_token_no_revienta(client):
    assert (
        client.post("/api/auth/logout", json={}).status_code == 200
    )


def test_cambiar_clave_mata_los_refresh(client, usuarios_prueba):
    token = _login(client).json()["refresh_token"]
    access = _login(client).json()["access_token"]

    client.post(
        "/api/auth/cambiar-clave",
        json={
            "contrasena_actual": CLAVE_ASESOR,
            "contrasena_nueva": CLAVE_NUEVA,
        },
        headers={"Authorization": f"Bearer {access}"},
    )

    assert (
        client.post(
            "/api/auth/refresh", json={"refresh_token": token}
        ).status_code
        == 401
    )


# --------------------- D124: recuperación por correo ------------------


def test_recuperar_correo_desconocido_responde_igual(client):
    respuesta = client.post(
        "/api/auth/recuperar-clave", json={"correo": "nadie@pacifico.co"}
    )

    # Misma respuesta que para un correo real: sin enumeración.
    assert respuesta.status_code == 200
    assert _contar("token_recuperacion") == 0


def test_recuperar_correo_real_genera_token(client, usuarios_prueba):
    respuesta = client.post(
        "/api/auth/recuperar-clave",
        json={"correo": "ASESOR@PACIFICO.CO"},
    )

    assert respuesta.status_code == 200
    assert _contar("token_recuperacion") == 1
    assert (
        _contar(
            "auditoria_usuario", "WHERE accion='recuperacion_solicitada'"
        )
        == 1
    )


def test_recuperar_invalida_enlaces_anteriores(client, usuarios_prueba):
    for _ in range(2):
        client.post(
            "/api/auth/recuperar-clave",
            json={"correo": "asesor@pacifico.co"},
        )

    # Dos solicitudes → un solo enlace vigente (el último).
    assert _contar("token_recuperacion", "WHERE usado = 0") == 1


def test_restablecer_con_token_valido(client, usuarios_prueba):
    token = "token-recuperacion-de-prueba"
    _sembrar_recuperacion(
        token, expira_en=datetime.now(UTC) + timedelta(minutes=30)
    )

    respuesta = client.post(
        "/api/auth/restablecer-clave",
        json={"token": token, "contrasena_nueva": CLAVE_NUEVA},
    )

    assert respuesta.status_code == 200
    # El token quedó consumido.
    assert _contar("token_recuperacion", "WHERE usado = 0") == 0
    # La clave nueva sirve para entrar.
    assert (
        _login(client, contrasena=CLAVE_NUEVA).status_code == 200
    )
    assert (
        _contar("auditoria_usuario", "WHERE accion='clave_restaurada'")
        == 1
    )


def test_restablecer_cierra_sesiones_abiertas(client, usuarios_prueba):
    refresh = _login(client).json()["refresh_token"]
    token = "token-que-cierra-sesiones"
    _sembrar_recuperacion(
        token, expira_en=datetime.now(UTC) + timedelta(minutes=30)
    )

    client.post(
        "/api/auth/restablecer-clave",
        json={"token": token, "contrasena_nueva": CLAVE_NUEVA},
    )

    assert (
        client.post(
            "/api/auth/refresh", json={"refresh_token": refresh}
        ).status_code
        == 401
    )


def test_restablecer_token_usado_o_inventado_da_400(client):
    token = "token-ya-usado"
    _sembrar_recuperacion(
        token,
        expira_en=datetime.now(UTC) + timedelta(minutes=30),
        usado=True,
    )

    for t in (token, "token-inexistente"):
        assert (
            client.post(
                "/api/auth/restablecer-clave",
                json={"token": t, "contrasena_nueva": CLAVE_NUEVA},
            ).status_code
            == 400
        )


def test_restablecer_token_vencido_da_400(client):
    token = "token-vencido"
    _sembrar_recuperacion(
        token, expira_en=datetime.now(UTC) - timedelta(minutes=1)
    )

    respuesta = client.post(
        "/api/auth/restablecer-clave",
        json={"token": token, "contrasena_nueva": CLAVE_NUEVA},
    )
    assert respuesta.status_code == 400
