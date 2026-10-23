"""Alcance de las solicitudes por rol: el asesor solo ve las que
radicó él, el aliado las de sus concesionarios vigentes (con filtro
por asesor para comisiones) y el admin todo."""

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.db_models.models import Cliente, SolicitudCredito
from backend.db_models.session import SessionLocal
from tests.integration.conftest import _id_usuario, _token_rol

SEDE_ASESOR = "CONCESIONARIO AUTH PRUEBA"
OTRA_SEDE = "SEDE AJENA PRUEBA"


def _concesionario_id(nombre: str, db: Session) -> int:
    db.execute(
        text("INSERT OR IGNORE INTO concesionario (nombre) VALUES (:n)"),
        {"n": nombre},
    )
    return db.execute(
        text("SELECT id_concesionario FROM concesionario WHERE nombre=:n"),
        {"n": nombre},
    ).scalar_one()


def _asesor_id(usuario: str = "asesor") -> int:
    with SessionLocal() as db:
        return db.execute(
            text("SELECT id_asesor FROM asesor WHERE id_usuario=:u"),
            {"u": _id_usuario(usuario)},
        ).scalar_one()


def _crear_colega_misma_sede() -> int:
    """Segundo asesor de la misma sede (usuario + ficha): sus
    radicaciones no son visibles para el asesor de prueba."""
    with SessionLocal() as db:
        db.execute(
            text(
                "INSERT OR IGNORE INTO usuario (id_usuario, correo, "
                "hash_contrasena, estado, nombre_completo) VALUES "
                "(:u, 'asesor2@pacifico.co', :h, 'activo', "
                "'Asesor Colega')"
            ),
            {
                "u": _id_usuario("asesor2"),
                "h": "$2b$12$kgMN4JFNA8mB9ak/aftAueZ2djG5QcixL5cchV5iolgYo9dkt8fQa",
            },
        )
        db.execute(
            text(
                "INSERT OR IGNORE INTO usuario_rol (id_usuario, id_rol) "
                "SELECT :u, id_rol FROM rol WHERE nombre='asesor'"
            ),
            {"u": _id_usuario("asesor2")},
        )
        db.execute(
            text(
                "INSERT OR IGNORE INTO asesor (id_usuario, nombre, "
                "id_concesionario) SELECT :u, 'Asesor Colega', "
                "id_concesionario FROM concesionario "
                "WHERE nombre='CONCESIONARIO AUTH PRUEBA'"
            ),
            {"u": _id_usuario("asesor2")},
        )
        db.commit()
        return db.execute(
            text("SELECT id_asesor FROM asesor WHERE id_usuario=:u"),
            {"u": _id_usuario("asesor2")},
        ).scalar_one()


def _radicar(
    id_concesionario: int | None,
    cedula: str,
    id_asesor: int | None = None,
) -> uuid.UUID:
    with SessionLocal() as db:
        cliente = Cliente(
            tipo_documento="CC",
            num_cedula=cedula,
            nombre_completo=f"Cliente {cedula}",
            fecha_nacimiento=date(1990, 1, 1),
        )
        db.add(cliente)
        db.flush()
        solicitud = SolicitudCredito(
            id_cliente=cliente.id_cliente,
            id_concesionario=id_concesionario,
            id_asesor=id_asesor,
            estado="creada",
        )
        db.add(solicitud)
        db.commit()
        return solicitud.id_solicitud


@pytest.fixture
def solicitudes_de_dos_sedes(client):
    """En la sede del asesor: una radicada por él y otra por un colega.
    En una sede ajena: una tercera. El asesor solo alcanza la propia."""
    with SessionLocal() as db:
        propia = _concesionario_id(SEDE_ASESOR, db)
        ajena = _concesionario_id(OTRA_SEDE, db)
        db.commit()
    colega = _crear_colega_misma_sede()
    return {
        "propia": _radicar(propia, "80000001", id_asesor=_asesor_id()),
        "colega": _radicar(propia, "80000003", id_asesor=colega),
        "colega_asesor_id": colega,
        "ajena": _radicar(ajena, "80000002"),
    }


def test_asesor_solo_ve_las_que_radic(client_asesor, solicitudes_de_dos_sedes):
    ids = {fila["id_solicitud"] for fila in client_asesor.get("/api/solicitudes").json()}
    assert str(solicitudes_de_dos_sedes["propia"]) in ids
    # Ni la del colega de la misma sede ni la de la sede ajena.
    assert str(solicitudes_de_dos_sedes["colega"]) not in ids
    assert str(solicitudes_de_dos_sedes["ajena"]) not in ids


def test_asesor_sin_ficha_no_ve_nada(client_asesor, solicitudes_de_dos_sedes):
    """Un asesor autenticado sin registro en `asesor` no ve ni las
    solicitudes de su (inexistente) sede: alcance fail-closed."""
    with SessionLocal() as db:
        db.execute(
            text("DELETE FROM asesor WHERE id_usuario=:u"),
            {"u": _id_usuario("asesor")},
        )
        db.commit()
    assert client_asesor.get("/api/solicitudes").json() == []


def test_aliado_solo_ve_concesionarios_vinculados(client_aliado, solicitudes_de_dos_sedes):
    ids = {fila["id_solicitud"] for fila in client_aliado.get("/api/solicitudes").json()}
    # El aliado sí ve TODAS las de la sede vinculada: propia y colega.
    assert str(solicitudes_de_dos_sedes["propia"]) in ids
    assert str(solicitudes_de_dos_sedes["colega"]) in ids
    assert str(solicitudes_de_dos_sedes["ajena"]) not in ids


def test_aliado_filtra_por_asesor(client_aliado, solicitudes_de_dos_sedes):
    """Filtro dimensional para comisiones: solo las del asesor elegido."""
    colega = solicitudes_de_dos_sedes["colega_asesor_id"]
    filas = client_aliado.get(f"/api/solicitudes?id_asesor={colega}").json()
    ids = {f["id_solicitud"] for f in filas}
    assert str(solicitudes_de_dos_sedes["colega"]) in ids
    assert str(solicitudes_de_dos_sedes["propia"]) not in ids


def test_resumen_expone_asesor_y_sede(client_aliado, solicitudes_de_dos_sedes):
    """La fila del listado dice quién radicó y desde qué sede: la base
    del reporte de comisiones del aliado."""
    filas = {
        f["id_solicitud"]: f
        for f in client_aliado.get("/api/solicitudes").json()
    }
    propia = filas[str(solicitudes_de_dos_sedes["propia"])]
    colega = filas[str(solicitudes_de_dos_sedes["colega"])]
    assert propia["nombre_asesor"] == "Asesor Prueba"
    assert colega["nombre_asesor"] == "Asesor Colega"
    assert propia["nombre_concesionario"] == SEDE_ASESOR


def test_admin_ve_todas(client, solicitudes_de_dos_sedes):
    ids = {fila["id_solicitud"] for fila in client.get("/api/solicitudes").json()}
    assert str(solicitudes_de_dos_sedes["propia"]) in ids
    assert str(solicitudes_de_dos_sedes["colega"]) in ids
    assert str(solicitudes_de_dos_sedes["ajena"]) in ids


def test_detalle_fuera_de_alcance_responde_404(client_asesor, client_aliado, solicitudes_de_dos_sedes):
    ajena = solicitudes_de_dos_sedes["ajena"]
    for c in (client_asesor, client_aliado):
        assert c.get(f"/api/solicitudes/{ajena}").status_code == 404
        assert c.get(f"/api/solicitudes/{ajena}/ofertas").status_code == 404


def test_asesor_no_abre_la_del_colega(client_asesor, solicitudes_de_dos_sedes):
    """Misma sede, otro radicador: 404 sin revelar existencia."""
    colega = solicitudes_de_dos_sedes["colega"]
    assert client_asesor.get(f"/api/solicitudes/{colega}").status_code == 404
    assert client_asesor.get(f"/api/solicitudes/{colega}/ofertas").status_code == 404


def test_mutacion_fuera_de_alcance_responde_404(client_asesor, solicitudes_de_dos_sedes):
    for objetivo in (
        solicitudes_de_dos_sedes["ajena"],
        solicitudes_de_dos_sedes["colega"],
    ):
        assert client_asesor.post(
            f"/api/solicitudes/{objetivo}/cancelar",
            json={"motivo": "Cliente desiste de la compra"},
        ).status_code == 404
        assert client_asesor.post(
            f"/api/solicitudes/{objetivo}/otp", json={"accion": "firma_pagare"}
        ).status_code == 404


def test_evidencias_fuera_de_alcance_responden_404(client_asesor, solicitudes_de_dos_sedes):
    for objetivo in (
        solicitudes_de_dos_sedes["ajena"],
        solicitudes_de_dos_sedes["colega"],
    ):
        assert client_asesor.get(f"/api/solicitudes/{objetivo}/evidencias").status_code == 404
        assert client_asesor.get(f"/api/solicitudes/{objetivo}/legalizacion.zip").status_code == 404


def test_asesor_crea_y_hereda_su_sede(client_asesor):
    """La radicación toma asesor+concesionario de la sesión, no del payload."""
    from tests.integration.test_api import SOLICITUD

    respuesta = client_asesor.post("/api/solicitudes", json=SOLICITUD)
    assert respuesta.status_code == 201, respuesta.text
    with SessionLocal() as db:
        fila = db.execute(
            text(
                "SELECT s.id_concesionario, a.id_usuario FROM solicitud_credito s "
                "LEFT JOIN asesor a ON a.id_asesor = s.id_asesor "
                "WHERE s.id_solicitud = :id"
            ),
            {"id": respuesta.json()["id_solicitud"].replace("-", "")},
        ).one()
        sede = db.execute(
            text("SELECT id_concesionario FROM concesionario WHERE nombre=:n"),
            {"n": SEDE_ASESOR},
        ).scalar_one()
        assert fila[0] == sede
        assert fila[1].replace("-", "") == _id_usuario("asesor")


def test_asesor_sin_sede_no_puede_radicar(tmp_path, monkeypatch):
    """Fail-closed: sin concesionario asignado, crear responde 422."""
    from tests.integration.conftest import _app_client, _cerrar_app, _configurar_entorno, _sembrar_identidad
    from tests.integration.test_api import SOLICITUD

    _configurar_entorno(tmp_path, monkeypatch)
    app_client = _app_client()
    with app_client as c:
        _sembrar_identidad()
        c.headers["Authorization"] = (
            f"Bearer {_token_rol('asesor', 'asesor_sinsede@pacifico.co')}"
        )
        respuesta = c.post("/api/solicitudes", json=SOLICITUD)
    _cerrar_app(app_client.app)
    assert respuesta.status_code == 422


def test_embudo_acotado_al_alcance(client_asesor, solicitudes_de_dos_sedes):
    embudo = client_asesor.get("/api/solicitudes/metricas/embudo").json()
    # Solo cuenta la solicitud que radicó él, no la del colega.
    assert embudo["radicadas"] == 1


def test_embudo_aliado_no_muestra_otros_aliados(client_aliado):
    embudo = client_aliado.get("/api/solicitudes/metricas/embudo").json()
    nombres = {fila["aliado"] for fila in embudo["por_aliado"]}
    # Como máximo su propio aliado; nunca los competidores.
    assert nombres <= {"ALIADO AUTH PRUEBA"}


def test_embudo_aliado_filtra_por_asesor(client_aliado, solicitudes_de_dos_sedes):
    colega = solicitudes_de_dos_sedes["colega_asesor_id"]
    embudo = client_aliado.get(
        f"/api/solicitudes/metricas/embudo?id_asesor={colega}"
    ).json()
    assert embudo["radicadas"] == 1


def test_catalogo_filtros_acotado_al_alcance(client_asesor, client_aliado, client):
    """El catálogo que alimenta los filtros del panel respeta el alcance:
    aliado solo ve sus sedes y sus asesores; el asesor solo se ve a sí
    mismo; el admin lo ve todo."""
    colega = _crear_colega_misma_sede()
    propio = _asesor_id()

    opciones_asesor = client_asesor.get("/api/catalogos/opciones-filtro").json()
    assert {a["id_asesor"] for a in opciones_asesor["asesores"]} == {propio}
    assert len(opciones_asesor["concesionarios"]) == 1

    opciones_aliado = client_aliado.get("/api/catalogos/opciones-filtro").json()
    nombres_sedes = {c["nombre"] for c in opciones_aliado["concesionarios"]}
    ids_asesores = {a["id_asesor"] for a in opciones_aliado["asesores"]}
    assert nombres_sedes == {SEDE_ASESOR}
    assert ids_asesores == {propio, colega}

    opciones_admin = client.get("/api/catalogos/opciones-filtro").json()
    assert OTRA_SEDE in {
        c["nombre"] for c in opciones_admin["concesionarios"]
    } or len(opciones_admin["concesionarios"]) >= 1
    assert propio in {a["id_asesor"] for a in opciones_admin["asesores"]}


def _ultima_auditoria(accion: str):
    from backend.db_models.auth_models import AuditoriaUsuario

    with SessionLocal() as db:
        return (
            db.query(AuditoriaUsuario)
            .filter(AuditoriaUsuario.accion == accion)
            .order_by(AuditoriaUsuario.id_auditoria.desc())
            .first()
        )


def test_detalle_queda_auditado(client, solicitudes_de_dos_sedes):
    """D116: leer el detalle de una solicitud deja rastro con IP y usuario."""
    id_sol = str(solicitudes_de_dos_sedes["propia"])
    assert client.get(f"/api/solicitudes/{id_sol}").status_code == 200
    fila = _ultima_auditoria("acceso_solicitud")
    assert fila is not None
    assert "detalle solicitud" in (fila.descripcion or "")
    assert fila.ip is not None


def test_acceso_fuera_de_alcance_queda_auditado(client_asesor, solicitudes_de_dos_sedes):
    """El intento del asesor por abrir una solicitud ajena queda como
    acceso_denegado aunque la respuesta sea 404."""
    ajena = str(solicitudes_de_dos_sedes["ajena"])
    assert client_asesor.get(f"/api/solicitudes/{ajena}").status_code == 404
    fila = _ultima_auditoria("acceso_denegado")
    assert fila is not None
    assert ajena in (fila.descripcion or "")
