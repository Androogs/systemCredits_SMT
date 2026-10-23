"""Administración de usuarios: CRUD solo para admin, vínculos
asesor→sede y usuario→aliado, protección del propio administrador."""

import uuid

from sqlalchemy import text

from backend.db_models.session import SessionLocal


def _login(client, correo, clave):
    return client.post(
        "/api/auth/login", json={"correo": correo, "contrasena": clave}
    )


def _admin_id(client) -> str:
    return client.get("/api/auth/login") and "" or ""


def test_solo_admin_lista_usuarios(client, client_asesor, client_sin_auth):
    assert client_sin_auth.get("/api/usuarios").status_code == 401
    assert client_asesor.get("/api/usuarios").status_code == 403
    filas = client.get("/api/usuarios").json()
    assert isinstance(filas, list) and len(filas) >= 3
    correos = {f["correo"] for f in filas}
    assert "admin@pacifico.co" in correos


def test_opciones_devuelven_catalogos(client):
    opciones = client.get("/api/usuarios/opciones").json()
    assert {r["nombre"] for r in opciones["roles"]} >= {
        "admin",
        "asesor",
        "aliado",
    }
    nombres_sede = {c["nombre"] for c in opciones["concesionarios"]}
    assert "CONCESIONARIO AUTH PRUEBA" in nombres_sede
    nombres_aliado = {a["nombre"] for a in opciones["aliados"]}
    assert "ALIADO AUTH PRUEBA" in nombres_aliado


def test_crear_asesor_con_sede_y_login(client):
    sede = client.get("/api/usuarios/opciones").json()["concesionarios"][0]
    respuesta = client.post(
        "/api/usuarios",
        json={
            "correo": "nuevo.asesor@pacifico.co",
            "nombre": "Asesor Nuevo",
            "contrasena": "ClaveSegura9!",
            "roles": ["asesor"],
            "id_concesionario": sede["id_concesionario"],
            "cedula": "80000222",
            "telefono": "3009998877",
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    creado = respuesta.json()
    assert creado["estado"] == "activo"
    assert creado["roles"] == ["asesor"]
    assert creado["concesionario"]["id_concesionario"] == sede["id_concesionario"]
    # La ficha se guarda completa y la ciudad se hereda de la sede.
    assert creado["cedula"] == "80000222"
    assert creado["telefono"] == "3009998877"

    login = _login(client, "nuevo.asesor@pacifico.co", "ClaveSegura9!")
    assert login.status_code == 200
    assert login.json()["usuario"]["concesionario"]["id_concesionario"] == (
        sede["id_concesionario"]
    )


def test_crear_correo_duplicado_responde_conflicto(client):
    respuesta = client.post(
        "/api/usuarios",
        json={
            "correo": "admin@pacifico.co",
            "nombre": "Otro Admin",
            "contrasena": "ClaveSegura9!",
            "roles": ["admin"],
        },
    )
    assert respuesta.status_code == 409


def test_crear_rol_inexistente_responde_422(client):
    respuesta = client.post(
        "/api/usuarios",
        json={
            "correo": "rol.malo@pacifico.co",
            "nombre": "Rol Malo",
            "contrasena": "ClaveSegura9!",
            "roles": ["superpoder"],
        },
    )
    assert respuesta.status_code == 422


def test_actualizar_roles_y_estado(client):
    sede = client.get("/api/usuarios/opciones").json()["concesionarios"][0]
    creado = client.post(
        "/api/usuarios",
        json={
            "correo": "cambia@pacifico.co",
            "nombre": "Cambia Rol",
            "contrasena": "ClaveSegura9!",
            "roles": ["asesor"],
            "id_concesionario": sede["id_concesionario"],
            "cedula": "80000333",
            "telefono": "3009998866",
        },
    ).json()
    id_usuario = creado["id_usuario"]

    r = client.put(f"/api/usuarios/{id_usuario}", json={"roles": ["aliado"]})
    assert r.status_code == 200
    assert r.json()["roles"] == ["aliado"]

    r = client.put(f"/api/usuarios/{id_usuario}", json={"estado": "bloqueado"})
    assert r.status_code == 200
    # Bloqueado no entra aunque la clave sea correcta.
    assert _login(client, "cambia@pacifico.co", "ClaveSegura9!").status_code == 403

    r = client.put(f"/api/usuarios/{id_usuario}", json={"estado": "activo"})
    assert r.status_code == 200
    assert _login(client, "cambia@pacifico.co", "ClaveSegura9!").status_code == 200


def test_restablecer_clave_permite_nuevo_ingreso(client):
    sede = client.get("/api/usuarios/opciones").json()["concesionarios"][0]
    creado = client.post(
        "/api/usuarios",
        json={
            "correo": "resetea@pacifico.co",
            "nombre": "Resetea Clave",
            "contrasena": "ClaveVieja1!",
            "roles": ["asesor"],
            "id_concesionario": sede["id_concesionario"],
            "cedula": "80000444",
            "telefono": "3009998855",
        },
    ).json()
    r = client.post(
        f"/api/usuarios/{creado['id_usuario']}/restablecer-clave",
        json={"contrasena": "ClaveNueva7!"},
    )
    assert r.status_code == 204
    assert _login(client, "resetea@pacifico.co", "ClaveVieja1!").status_code == 401
    assert _login(client, "resetea@pacifico.co", "ClaveNueva7!").status_code == 200


def test_admin_no_puede_desactivarse(client):
    with SessionLocal() as db:
        admin_id = db.execute(
            text("SELECT id_usuario FROM usuario WHERE correo='admin@pacifico.co'")
        ).scalar_one()
    r = client.put(f"/api/usuarios/{admin_id}", json={"estado": "inactivo"})
    assert r.status_code == 422
    r = client.put(f"/api/usuarios/{admin_id}", json={"roles": ["asesor"]})
    assert r.status_code == 422


def test_usuario_inexistente_responde_404(client):
    r = client.put(
        f"/api/usuarios/{uuid.uuid4()}", json={"nombre": "Nadie"}
    )
    assert r.status_code == 404


def _token_de(client, correo, clave) -> str:
    r = _login(client, correo, clave)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_cambiar_clave_self_service(client):
    """Alta con clave temporal → login expone el flag → el usuario la
    cambia → el flag se apaga y la clave vieja deja de servir."""
    sede = client.get("/api/usuarios/opciones").json()["concesionarios"][0]
    client.post(
        "/api/usuarios",
        json={
            "correo": "cambia@pacifico.co",
            "nombre": "Cambia Clave",
            "contrasena": "Temporal1!",
            "roles": ["asesor"],
            "id_concesionario": sede["id_concesionario"],
            "cedula": "80000555",
            "telefono": "3009998844",
        },
    )
    login = _login(client, "cambia@pacifico.co", "Temporal1!")
    assert login.json()["usuario"]["requiere_cambio_password"] is True
    cab = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Clave actual incorrecta → 400, el flag sigue en pie.
    r = client.post(
        "/api/auth/cambiar-clave",
        json={"contrasena_actual": "Erronea9!", "contrasena_nueva": "NuevaSegura2!"},
        headers=cab,
    )
    assert r.status_code == 400

    # Nueva igual a la actual → 400.
    r = client.post(
        "/api/auth/cambiar-clave",
        json={"contrasena_actual": "Temporal1!", "contrasena_nueva": "Temporal1!"},
        headers=cab,
    )
    assert r.status_code == 400

    # Cambio válido: flag apagado, clave vieja muere, la nueva entra.
    r = client.post(
        "/api/auth/cambiar-clave",
        json={
            "contrasena_actual": "Temporal1!",
            "contrasena_nueva": "NuevaSegura2!",
        },
        headers=cab,
    )
    assert r.status_code == 200, r.text
    assert r.json()["requiere_cambio_password"] is False
    assert _login(client, "cambia@pacifico.co", "Temporal1!").status_code == 401
    nuevo = _login(client, "cambia@pacifico.co", "NuevaSegura2!")
    assert nuevo.json()["usuario"]["requiere_cambio_password"] is False


def test_cambiar_clave_requiere_sesion(client, client_sin_auth):
    r = client_sin_auth.post(
        "/api/auth/cambiar-clave",
        json={"contrasena_actual": "x", "contrasena_nueva": "NuevaSegura2!"},
    )
    assert r.status_code == 401
