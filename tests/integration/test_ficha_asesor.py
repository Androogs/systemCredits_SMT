"""Ficha del asesor: cédula/celular obligatorios, ciudad de la sede,
historial de cambios y alcance por cédula.

La cuenta (correo corporativo) es permanente; la persona puede cambiar.
Cada solicitud guarda la foto del radicador (nombre + cédula) para que
la atribución sobreviva al cambio de persona: quien hereda la cuenta ve
solo lo que él radica — las del predecesor desaparecen, con foto o
legadas sin foto (`persona_desde` marca el corte del titular).
"""

import uuid

from sqlalchemy import text

from backend.db_models.session import SessionLocal
from tests.integration.conftest import _id_usuario
from tests.integration.test_alcance import (
    SEDE_ASESOR,
    _asesor_id,
    _concesionario_id,
    _radicar,
)
from tests.integration.test_api import SOLICITUD


def _sede() -> int:
    with SessionLocal() as db:
        return _concesionario_id(SEDE_ASESOR, db)


def _payload_asesor(**extra) -> dict:
    return {
        "correo": "ficha.asesor@pacifico.co",
        "nombre": "Persona Uno",
        "contrasena": "ClaveSegura9!",
        "roles": ["asesor"],
        "id_concesionario": _sede(),
        "cedula": "80000777",
        "telefono": "3006665544",
        **extra,
    }


# ------------------------------------------------------------------
# Creación: la ficha es obligatoria
# ------------------------------------------------------------------


def test_crear_asesor_sin_ficha_responde_422(client):
    sede = _sede()
    for faltantes in (
        {"cedula": None},
        {"telefono": None},
        {"cedula": None, "telefono": None},
        {"id_concesionario": None},
    ):
        payload = _payload_asesor(**faltantes)
        payload["correo"] = f"sin.ficha.{uuid.uuid4().hex[:6]}@pacifico.co"
        respuesta = client.post("/api/usuarios", json=payload)
        assert respuesta.status_code == 422, faltantes


def test_concesionario_crear_asesor_sin_ficha_responde_422(
    client_concesionario,
):
    payload = _payload_asesor(cedula=None, telefono=None)
    payload["correo"] = "sin.ficha.sede@pacifico.co"
    respuesta = client_concesionario.post("/api/usuarios", json=payload)
    assert respuesta.status_code == 422


def test_ficha_devuelve_cedula_celular_y_ciudad_de_la_sede(client):
    respuesta = client.post("/api/usuarios", json=_payload_asesor())
    assert respuesta.status_code == 201, respuesta.text
    creado = respuesta.json()
    assert creado["cedula"] == "80000777"
    assert creado["telefono"] == "3006665544"
    # La ciudad la pone la sede, no el formulario.
    assert creado["concesionario"]["id_concesionario"] == _sede()
    with SessionLocal() as db:
        ciudad_sede = db.execute(
            text(
                "SELECT id_ciudad FROM concesionario "
                "WHERE id_concesionario=:s"
            ),
            {"s": _sede()},
        ).scalar_one()
        ciudad_asesor = db.execute(
            text(
                "SELECT id_ciudad FROM asesor WHERE id_usuario=:u"
            ),
            {"u": uuid.UUID(creado["id_usuario"]).hex},
        ).scalar_one()
    assert ciudad_asesor == ciudad_sede


# ------------------------------------------------------------------
# Historial de cambios
# ------------------------------------------------------------------


def test_editar_ficha_deja_historial_con_antes_y_despues(client):
    creado = client.post("/api/usuarios", json=_payload_asesor()).json()
    id_usuario = creado["id_usuario"]

    respuesta = client.put(
        f"/api/usuarios/{id_usuario}",
        json={
            "nombre": "Persona Dos",
            "cedula": "80000888",
            "telefono": "3005554433",
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["cedula"] == "80000888"

    historial = client.get(f"/api/usuarios/{id_usuario}/historial").json()
    assert len(historial) == 1
    cambios = historial[0]["cambios"]
    assert cambios["nombre"] == {
        "antes": "Persona Uno",
        "despues": "Persona Dos",
    }
    assert cambios["cedula"] == {"antes": "80000777", "despues": "80000888"}
    assert cambios["celular"] == {
        "antes": "3006665544",
        "despues": "3005554433",
    }
    assert historial[0]["nombre_quien"]


def test_historial_registra_estado_y_sede(client):
    creado = client.post("/api/usuarios", json=_payload_asesor()).json()
    id_usuario = creado["id_usuario"]
    client.put(
        f"/api/usuarios/{id_usuario}", json={"estado": "inactivo"}
    )
    historial = client.get(f"/api/usuarios/{id_usuario}/historial").json()
    assert historial[0]["cambios"]["estado"] == {
        "antes": "activo",
        "despues": "inactivo",
    }


def test_historial_acotado_para_concesionario(client, client_concesionario):
    creado = client.post("/api/usuarios", json=_payload_asesor()).json()
    id_usuario = creado["id_usuario"]
    # De su sede: puede leer el historial.
    assert (
        client_concesionario.get(
            f"/api/usuarios/{id_usuario}/historial"
        ).status_code
        == 200
    )
    # Usuario que no es asesor de su sede: ni siquiera existe para él.
    assert (
        client_concesionario.get(
            f"/api/usuarios/{_id_usuario('admin')}/historial"
        ).status_code
        == 404
    )


def test_historial_asesor_sin_ficha_devuelve_lista_vacia(client):
    assert client.get(
        f"/api/usuarios/{_id_usuario('admin')}/historial"
    ).json() == []


# ------------------------------------------------------------------
# Alcance por cédula: la solicitud queda ligada a la persona
# ------------------------------------------------------------------


def test_snapshot_del_radicador_en_la_solicitud(client, client_asesor):
    respuesta = client_asesor.post("/api/solicitudes", json=SOLICITUD)
    assert respuesta.status_code == 201, respuesta.text
    id_solicitud = respuesta.json()["id_solicitud"]
    with SessionLocal() as db:
        fila = db.execute(
            text(
                "SELECT asesor_nombre, asesor_cedula FROM "
                "solicitud_credito WHERE id_solicitud=:s"
            ),
            {"s": uuid.UUID(id_solicitud).hex},
        ).one()
    # La foto es del asesor del fixture (cédula '80000001' del seed).
    assert fila.asesor_cedula == "80000001"
    assert fila.asesor_nombre == "Asesor Prueba"


def test_cambio_de_persona_despega_las_solicitudes_anteriores(
    client, client_asesor
):
    """La misma cuenta cambia de persona (renuncia): el sucesor solo
    ve lo que él radique — las del predecesor desaparecen de su vista,
    con foto de cédula o legadas sin foto (corte `persona_desde`)."""
    # 1) El asesor radica una solicitud con su cédula actual.
    radicada = client_asesor.post("/api/solicitudes", json=SOLICITUD)
    assert radicada.status_code == 201, radicada.text
    id_radicada = radicada.json()["id_solicitud"]
    # 2) Una solicitud legada sin foto (como las del backfill histórico).
    legada = _radicar(_sede(), "80000999", id_asesor=_asesor_id())

    # 3) Cambia la persona detrás del correo: nombre + cédula + celular.
    edicion = client.put(
        f"/api/usuarios/{_id_usuario('asesor')}",
        json={
            "nombre": "Persona Relevo",
            "cedula": "80000123",
            "telefono": "3004443322",
        },
    )
    assert edicion.status_code == 200, edicion.text

    # 4) La vista del sucesor: ni la radicada por el predecesor ni la
    # legada (creada antes del cambio de titular) aparecen.
    ids = {
        fila["id_solicitud"]
        for fila in client_asesor.get("/api/solicitudes").json()
    }
    assert id_radicada not in ids
    assert str(legada) not in ids
    # Ni el detalle las revela.
    assert (
        client_asesor.get(f"/api/solicitudes/{id_radicada}").status_code
        == 404
    )
    assert (
        client_asesor.get(f"/api/solicitudes/{legada}").status_code == 404
    )
    # El historial dejó constancia del cambio de persona.
    historial = client.get(
        f"/api/usuarios/{_id_usuario('asesor')}/historial"
    ).json()
    assert historial[0]["cambios"]["cedula"] == {
        "antes": "80000001",
        "despues": "80000123",
    }


def test_completar_cedula_del_mismo_titular_no_corta_legadas(
    client, client_asesor
):
    """Llenar la cédula faltante del MISMO titular (nombre intacto) no
    es cambio de persona: sus legadas sin foto le siguen perteneciendo.
    Es el caso de las fichas reales que llegaron sin cédula."""
    with SessionLocal() as db:
        db.execute(
            text("UPDATE asesor SET num_cedula=NULL WHERE id_usuario=:u"),
            {"u": _id_usuario("asesor")},
        )
        db.commit()
    legada = _radicar(_sede(), "80000999", id_asesor=_asesor_id())

    edicion = client.put(
        f"/api/usuarios/{_id_usuario('asesor')}",
        json={"cedula": "80000123"},
    )
    assert edicion.status_code == 200, edicion.text
    ids = {
        fila["id_solicitud"]
        for fila in client_asesor.get("/api/solicitudes").json()
    }
    assert str(legada) in ids


def test_solicitud_del_sucesor_si_aparece(client, client_asesor):
    """Tras el cambio de persona, lo que radique el sucesor lleva la
    nueva cédula y sí le pertenece."""
    client.put(
        f"/api/usuarios/{_id_usuario('asesor')}",
        json={"cedula": "80000123"},
    )
    radicada = client_asesor.post("/api/solicitudes", json=SOLICITUD)
    assert radicada.status_code == 201, radicada.text
    ids = {
        fila["id_solicitud"]
        for fila in client_asesor.get("/api/solicitudes").json()
    }
    assert radicada.json()["id_solicitud"] in ids


def test_filtro_admin_por_asesor_muestra_solo_al_titular_actual(
    client, client_asesor
):
    """El filtro del panel por asesor es por PERSONA: tras el cambio de
    titular, 'asesor X' muestra lo del titular actual (su cédula o
    legadas posteriores al corte), no la producción del predecesor."""
    radicada = client_asesor.post("/api/solicitudes", json=SOLICITUD)
    assert radicada.status_code == 201, radicada.text
    id_predecesor = radicada.json()["id_solicitud"]
    legada = _radicar(_sede(), "80000999", id_asesor=_asesor_id())

    # Cambio de titular (nombre + cédula) y una radicación del sucesor.
    client.put(
        f"/api/usuarios/{_id_usuario('asesor')}",
        json={
            "nombre": "Persona Relevo",
            "cedula": "80000123",
            "telefono": "3004443322",
        },
    )
    nueva = client_asesor.post("/api/solicitudes", json=SOLICITUD)
    assert nueva.status_code == 201, nueva.text

    ids = {
        fila["id_solicitud"]
        for fila in client.get(
            f"/api/solicitudes?id_asesor={_asesor_id()}"
        ).json()
    }
    # Solo la del titular actual: ni la radicada por el predecesor con
    # su cédula vieja ni la legada previa al corte.
    assert ids == {nueva.json()["id_solicitud"]}
    assert id_predecesor not in ids
    assert str(legada) not in ids
    # Sin filtro, admin sigue viendo toda la cuenta (auditoría).
    todas = {
        fila["id_solicitud"] for fila in client.get("/api/solicitudes").json()
    }
    assert {id_predecesor, str(legada)} <= todas


def test_concesionario_ve_todo_su_sede_sin_importar_cedula(
    client, client_asesor, client_concesionario
):
    """El concesionario ve la sede completa: cambiar la persona del
    asesor no le esconde nada — su alcance es por sede, no por cédula."""
    radicada = client_asesor.post("/api/solicitudes", json=SOLICITUD)
    assert radicada.status_code == 201, radicada.text
    id_radicada = radicada.json()["id_solicitud"]
    client.put(
        f"/api/usuarios/{_id_usuario('asesor')}",
        json={"cedula": "80000123"},
    )
    ids = {
        fila["id_solicitud"]
        for fila in client_concesionario.get("/api/solicitudes").json()
    }
    assert id_radicada in ids
