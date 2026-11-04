"""Rol `concesionario` (administrador de sede — D122).

Opera todas las solicitudes de su concesionario (no solo las que
radicó un asesor), filtra por asesor, radica a nombre de un asesor
propio y gestiona los usuarios-asesor de su sede. No ve otras sedes,
no toca usuarios ajenos ni accede a las funciones globales del admin
(parámetros del motor, auditoría interna).
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.db_models.session import SessionLocal
from tests.integration.conftest import _id_usuario
from tests.integration.test_alcance import (
    OTRA_SEDE,
    SEDE_ASESOR,
    _asesor_id,
    _concesionario_id,
    _crear_colega_misma_sede,
    _radicar,
    solicitudes_de_dos_sedes,  # noqa: F401  (fixture reexportada)
)
from tests.integration.test_api import SOLICITUD


def _id_asesor_de_otra_sede() -> int:
    """Asesor de una sede ajena: objetivo inválido para radicar y
    para gestionar usuarios."""
    with SessionLocal() as db:
        sede = _concesionario_id(OTRA_SEDE, db)
        db.execute(
            text(
                "INSERT OR IGNORE INTO usuario (id_usuario, correo, "
                "hash_contrasena, estado, nombre_completo) VALUES "
                "(:u, 'asesor_ajeno@sumoto.com.co', :h, 'activo', "
                "'Asesor Ajeno')"
            ),
            {
                "u": _id_usuario("asesor_ajeno"),
                "h": "$2b$12$kgMN4JFNA8mB9ak/aftAueZ2djG5QcixL5cchV5iolgYo9dkt8fQa",
            },
        )
        db.execute(
            text(
                "INSERT OR IGNORE INTO usuario_rol (id_usuario, id_rol) "
                "SELECT :u, id_rol FROM rol WHERE nombre='asesor'"
            ),
            {"u": _id_usuario("asesor_ajeno")},
        )
        db.execute(
            text(
                "INSERT OR IGNORE INTO asesor (id_usuario, nombre, "
                "id_concesionario) VALUES (:u, 'Asesor Ajeno', :sede)"
            ),
            {"u": _id_usuario("asesor_ajeno"), "sede": sede},
        )
        db.commit()
        return db.execute(
            text("SELECT id_asesor FROM asesor WHERE id_usuario=:u"),
            {"u": _id_usuario("asesor_ajeno")},
        ).scalar_one()


def _id_usuario_db(correo_rol: str) -> str:
    return _id_usuario(correo_rol)


# ------------------------------------------------------------------
# Alcance de solicitudes
# ------------------------------------------------------------------


def test_concesionario_ve_toda_su_sede(
    client_concesionario, solicitudes_de_dos_sedes
):
    ids = {
        fila["id_solicitud"]
        for fila in client_concesionario.get("/api/solicitudes").json()
    }
    # Propia y la del colega: la sede completa, no solo las suyas.
    assert str(solicitudes_de_dos_sedes["propia"]) in ids
    assert str(solicitudes_de_dos_sedes["colega"]) in ids
    # La sede ajena queda fuera.
    assert str(solicitudes_de_dos_sedes["ajena"]) not in ids


def test_concesionario_filtra_por_asesor(
    client_concesionario, solicitudes_de_dos_sedes
):
    colega = solicitudes_de_dos_sedes["colega_asesor_id"]
    filas = client_concesionario.get(
        f"/api/solicitudes?id_asesor={colega}"
    ).json()
    ids = {f["id_solicitud"] for f in filas}
    assert str(solicitudes_de_dos_sedes["colega"]) in ids
    assert str(solicitudes_de_dos_sedes["propia"]) not in ids


def test_concesionario_filtro_por_asesor_ajeno_devuelve_vacio(
    client_concesionario, solicitudes_de_dos_sedes
):
    ajeno = _id_asesor_de_otra_sede()
    filas = client_concesionario.get(
        f"/api/solicitudes?id_asesor={ajeno}"
    ).json()
    assert filas == []


def test_concesionario_detalle_y_mutacion_de_su_sede(
    client_concesionario, solicitudes_de_dos_sedes
):
    colega = str(solicitudes_de_dos_sedes["colega"])
    assert (
        client_concesionario.get(f"/api/solicitudes/{colega}").status_code
        == 200
    )


def test_concesionario_fuera_de_sede_responde_404(
    client_concesionario, solicitudes_de_dos_sedes
):
    ajena = str(solicitudes_de_dos_sedes["ajena"])
    assert (
        client_concesionario.get(f"/api/solicitudes/{ajena}").status_code
        == 404
    )
    assert (
        client_concesionario.post(
            f"/api/solicitudes/{ajena}/cancelar",
            json={"motivo": "Cliente desiste"},
        ).status_code
        == 404
    )


def test_catalogo_filtros_concesionario_acotado(
    client_concesionario, solicitudes_de_dos_sedes
):
    opciones = client_concesionario.get(
        "/api/catalogos/opciones-filtro"
    ).json()
    assert {c["nombre"] for c in opciones["concesionarios"]} == {
        SEDE_ASESOR
    }
    assert {a["id_asesor"] for a in opciones["asesores"]} == {
        _asesor_id(),
        solicitudes_de_dos_sedes["colega_asesor_id"],
    }


# ------------------------------------------------------------------
# Radicación a nombre de un asesor de la sede
# ------------------------------------------------------------------


def test_concesionario_radia_a_nombre_de_asesor(client_concesionario):
    respuesta = client_concesionario.post(
        "/api/solicitudes",
        json={**SOLICITUD, "id_asesor": _asesor_id()},
    )
    assert respuesta.status_code == 201, respuesta.text
    with SessionLocal() as db:
        fila = db.execute(
            text(
                "SELECT id_concesionario, id_asesor FROM solicitud_credito "
                "WHERE id_solicitud = :id"
            ),
            {"id": respuesta.json()["id_solicitud"].replace("-", "")},
        ).one()
        sede = db.execute(
            text(
                "SELECT id_concesionario FROM concesionario "
                "WHERE nombre=:n"
            ),
            {"n": SEDE_ASESOR},
        ).scalar_one()
        assert fila[0] == sede
        assert fila[1] == _asesor_id()


def test_concesionario_sin_asesor_no_radia(client_concesionario):
    respuesta = client_concesionario.post("/api/solicitudes", json=SOLICITUD)
    assert respuesta.status_code == 422


def test_concesionario_no_radia_a_nombre_ajeno(client_concesionario):
    respuesta = client_concesionario.post(
        "/api/solicitudes",
        json={**SOLICITUD, "id_asesor": _id_asesor_de_otra_sede()},
    )
    assert respuesta.status_code == 422


def test_concesionario_no_radia_sede_ajena_en_payload(client_concesionario):
    """Aunque pida otra sede en el payload, la titularidad manda la
    sesión — queda en su concesionario."""
    with SessionLocal() as db:
        ajena = _concesionario_id(OTRA_SEDE, db)
        db.commit()
    respuesta = client_concesionario.post(
        "/api/solicitudes",
        json={
            **SOLICITUD,
            "id_asesor": _asesor_id(),
            "id_concesionario": ajena,
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    with SessionLocal() as db:
        sede_real = db.execute(
            text(
                "SELECT id_concesionario FROM solicitud_credito "
                "WHERE id_solicitud = :id"
            ),
            {"id": respuesta.json()["id_solicitud"].replace("-", "")},
        ).scalar_one()
        propia = db.execute(
            text(
                "SELECT id_concesionario FROM concesionario "
                "WHERE nombre=:n"
            ),
            {"n": SEDE_ASESOR},
        ).scalar_one()
        assert sede_real == propia


# ------------------------------------------------------------------
# Gestión de usuarios acotada a la sede
# ------------------------------------------------------------------


def test_concesionario_lista_solo_asesores_de_su_sede(client_concesionario):
    _id_asesor_de_otra_sede()
    usuarios = client_concesionario.get("/api/usuarios").json()
    correos = {u["correo"] for u in usuarios}
    assert "asesor@sumoto.com.co" in correos
    # Ni el asesor de otra sede, ni el admin, ni el aliado.
    assert "asesor_ajeno@sumoto.com.co" not in correos
    assert "admin@sumoto.com.co" not in correos
    assert "aliado@sumoto.com.co" not in correos


def test_opciones_usuarios_acotadas(client_concesionario):
    opciones = client_concesionario.get("/api/usuarios/opciones").json()
    assert [r["nombre"] for r in opciones["roles"]] == ["asesor"]
    assert {c["nombre"] for c in opciones["concesionarios"]} == {
        SEDE_ASESOR
    }
    assert opciones["aliados"] == []


def test_concesionario_crea_asesor_de_su_sede(client_concesionario):
    respuesta = client_concesionario.post(
        "/api/usuarios",
        json={
            "nombre": "Asesor Nuevo Sede",
            "correo": "asesor.nuevo@sumoto.com.co",
            "contrasena": "Temporal123!",
            "roles": ["asesor"],
            # El backend fuerza la sede de la sesión — aunque pidiera
            # otra, queda en la propia.
            "id_concesionario": None,
            "id_aliado": None,
            # Ficha obligatoria de la persona detrás del correo.
            "cedula": "80000666",
            "telefono": "3007778899",
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    creado = respuesta.json()
    assert creado["roles"] == ["asesor"]
    assert creado["concesionario"]["nombre"] == SEDE_ASESOR
    assert creado["requiere_cambio_password"] is True
    assert creado["cedula"] == "80000666"


def test_concesionario_no_puede_crear_otros_roles(client_concesionario):
    for roles in (["admin"], ["aliado"], ["concesionario"], ["asesor", "admin"]):
        respuesta = client_concesionario.post(
            "/api/usuarios",
            json={
                "nombre": "Intruso",
                "correo": "intruso@sumoto.com.co",
                "contrasena": "Temporal123!",
                "roles": roles,
            },
        )
        assert respuesta.status_code == 422, roles


def test_concesionario_no_toca_usuarios_ajenos(client_concesionario):
    _id_asesor_de_otra_sede()
    for objetivo in (
        _id_usuario_db("admin"),
        _id_usuario_db("aliado"),
        _id_usuario_db("asesor_ajeno"),
        _id_usuario_db("concesionario"),  # ni él mismo (no es asesor)
    ):
        assert (
            client_concesionario.put(
                f"/api/usuarios/{objetivo}",
                json={"estado": "inactivo"},
            ).status_code
            == 404
        )
        assert (
            client_concesionario.post(
                f"/api/usuarios/{objetivo}/restablecer-clave",
                json={"contrasena": "OtraTemporal123!"},
            ).status_code
            == 404
        )


def test_concesionario_gestiona_asesor_propio(client_concesionario):
    objetivo = _id_usuario_db("asesor")
    respuesta = client_concesionario.put(
        f"/api/usuarios/{objetivo}",
        json={"nombre": "Asesor Prueba Editado", "estado": "inactivo"},
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "inactivo"
    # Y puede restablecerle la clave.
    assert (
        client_concesionario.post(
            f"/api/usuarios/{objetivo}/restablecer-clave",
            json={"contrasena": "NuevaTemporal123!"},
        ).status_code
        == 204
    )


def test_concesionario_no_mueve_asesor_de_sede(client_concesionario):
    with SessionLocal() as db:
        ajena = _concesionario_id(OTRA_SEDE, db)
        db.commit()
    respuesta = client_concesionario.put(
        f"/api/usuarios/{_id_usuario_db('asesor')}",
        json={"id_concesionario": ajena},
    )
    assert respuesta.status_code == 422


def test_admin_crea_usuario_concesionario_con_sede(client):
    """El alta de un administrador de sede escribe `concesionario_usuario`
    — no `asesor`, porque no radica."""
    with SessionLocal() as db:
        sede = _concesionario_id(SEDE_ASESOR, db)
        db.commit()
    respuesta = client.post(
        "/api/usuarios",
        json={
            "nombre": "Admin Sede Dos",
            "correo": "admin.sede@sumoto.com.co",
            "contrasena": "Temporal123!",
            "roles": ["concesionario"],
            "id_concesionario": sede,
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    creado = respuesta.json()
    assert creado["roles"] == ["concesionario"]
    assert creado["concesionario"]["nombre"] == SEDE_ASESOR
    with SessionLocal() as db:
        asesor = db.execute(
            text(
                "SELECT id_asesor FROM asesor WHERE id_usuario=:u"
            ),
            {"u": creado["id_usuario"].replace("-", "")},
        ).one_or_none()
        assert asesor is None
        vinculo = db.execute(
            text(
                "SELECT id_concesionario FROM concesionario_usuario "
                "WHERE id_usuario=:u"
            ),
            {"u": creado["id_usuario"].replace("-", "")},
        ).scalar_one()
        assert vinculo == sede


# ------------------------------------------------------------------
# Perímetro: funciones de admin quedan fuera
# ------------------------------------------------------------------


def test_concesionario_no_llega_a_funciones_admin(client_concesionario):
    assert client_concesionario.get("/api/parametros").status_code == 403
    assert client_concesionario.get("/api/auditoria").status_code == 403
