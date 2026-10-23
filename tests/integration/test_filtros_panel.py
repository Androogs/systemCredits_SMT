"""Filtros dimensionales del panel: admin filtra por concesionario y
asesor; la intersección con el alcance mantiene fail-closed el resto
de roles; `orden=prioridad` pone pendientes primero antes del límite."""

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.db_models.models import Cliente, SolicitudCredito
from backend.db_models.session import SessionLocal
from tests.integration.conftest import _id_usuario

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


def _asesor_id() -> int:
    with SessionLocal() as db:
        return db.execute(
            text("SELECT id_asesor FROM asesor WHERE id_usuario=:u"),
            {"u": _id_usuario("asesor")},
        ).scalar_one()


def _radicar(
    id_concesionario: int | None,
    cedula: str,
    *,
    id_asesor: int | None = None,
    estado: str = "creada",
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
            estado=estado,
        )
        db.add(solicitud)
        db.commit()
        return solicitud.id_solicitud


@pytest.fixture
def solicitudes_dos_sedes(client):
    with SessionLocal() as db:
        propia = _concesionario_id(SEDE_ASESOR, db)
        ajena = _concesionario_id(OTRA_SEDE, db)
        db.commit()
    return {
        "propia_id": propia,
        "ajena_id": ajena,
        "propia": _radicar(propia, "81000001"),
        "ajena": _radicar(ajena, "81000002"),
    }


def test_admin_filtra_por_concesionario(client, solicitudes_dos_sedes):
    ids = {
        f["id_solicitud"]
        for f in client.get(
            f"/api/solicitudes?id_concesionario={solicitudes_dos_sedes['ajena_id']}"
        ).json()
    }
    assert str(solicitudes_dos_sedes["ajena"]) in ids
    assert str(solicitudes_dos_sedes["propia"]) not in ids


def test_admin_filtra_por_asesor(client):
    asesor = _asesor_id()
    con_asesor = _radicar(None, "81000003", id_asesor=asesor)
    sin_asesor = _radicar(None, "81000004")
    ids = {
        f["id_solicitud"]
        for f in client.get(f"/api/solicitudes?id_asesor={asesor}").json()
    }
    assert str(con_asesor) in ids
    assert str(sin_asesor) not in ids


def test_asesor_no_amplia_su_alcance(client_asesor, solicitudes_dos_sedes):
    """El filtro se intersecta con el scope: pedir la sede ajena devuelve
    vacío, no las solicitudes de esa sede."""
    ids = {
        f["id_solicitud"]
        for f in client_asesor.get(
            f"/api/solicitudes?id_concesionario={solicitudes_dos_sedes['ajena_id']}"
        ).json()
    }
    assert str(solicitudes_dos_sedes["ajena"]) not in ids


def test_orden_prioridad_pone_pendientes_primero(client):
    pendiente = _radicar(None, "81000005", estado="creada")
    resuelta = _radicar(None, "81000006", estado="desembolsada")
    filas = client.get("/api/solicitudes?orden=prioridad").json()
    pos = {str(s): i for i, f in enumerate(filas) for s in [f["id_solicitud"]]}
    assert pos[str(pendiente)] < pos[str(resuelta)]


def test_orden_invalido_422(client):
    assert client.get("/api/solicitudes?orden=alfabetico").status_code == 422


def test_embudo_filtra_por_concesionario(client, solicitudes_dos_sedes):
    embudo = client.get(
        f"/api/solicitudes/metricas/embudo"
        f"?id_concesionario={solicitudes_dos_sedes['ajena_id']}"
    ).json()
    assert embudo["radicadas"] == 1


def test_embudo_filtra_por_asesor(client):
    asesor = _asesor_id()
    _radicar(None, "81000007", id_asesor=asesor)
    _radicar(None, "81000008")
    embudo = client.get(
        f"/api/solicitudes/metricas/embudo?id_asesor={asesor}"
    ).json()
    assert embudo["radicadas"] == 1


def test_opciones_incluye_asesores(client):
    opciones = client.get("/api/usuarios/opciones").json()
    asesores = {a["id_asesor"]: a for a in opciones["asesores"]}
    esperado = _asesor_id()
    assert esperado in asesores
    assert "nombre" in asesores[esperado]
    assert "id_concesionario" in asesores[esperado]
