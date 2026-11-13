"""Cargue masivo RNGM: archivo plano .txt de la guía RUNTPRO GM Fase II.

Siembra una solicitud facturada con su prenda completa y valida el
layout del archivo (control + PRN/GRV/DEU/VEH), el nombre
<NIT>RGM<consecutivo><AAAAMMDD>.txt, la marca de exportadas y la
vista previa de advertencias.
"""

import uuid
from datetime import date, datetime

import pytest

from backend.db_models import session as db_session
from backend.db_models.models import (
    Ciudad,
    Cliente,
    OfertaCredito,
    AliadoProducto,
    ProductoVehiculo,
    SolicitudContactoVivienda,
    SolicitudCredito,
)


def _sembrar_facturada(db, *, cedula: str = "1032448999") -> SolicitudCredito:
    ciudad = Ciudad(nombre="Palmira", departamento="Valle del Cauca")
    db.add(ciudad)
    db.flush()
    cliente = Cliente(
        tipo_documento="1",
        num_cedula=cedula,
        nombre_completo="MARIA FERNANDA RUIZ PAEZ",
        primer_apellido="RUIZ",
        fecha_nacimiento=date(1995, 3, 8),
        ocupacion="empleado",
    )
    db.add(cliente)
    db.flush()
    solicitud = SolicitudCredito(
        id_solicitud=uuid.uuid4(),
        num_solicitud=990001,
        id_cliente=cliente.id_cliente,
        fecha_hora=datetime(2026, 11, 3),
        estado="facturada",
        moneda="COP",
        plazo_deseado_meses=24,
        origen="flujo",
    )
    db.add(solicitud)
    db.flush()
    db.add(
        SolicitudContactoVivienda(
            id_solicitud=solicitud.id_solicitud,
            correo="mafer@correo.com",
            telefono="573205550011",
            direccion="KR 17 A # 55 - 55",
            id_ciudad=ciudad.id_ciudad,
        )
    )
    db.add(
        ProductoVehiculo(
            id_solicitud=solicitud.id_solicitud,
            producto_a_financiar="Motocicleta",
            marca="Suzuki",
            referencia="GN 125",
            vin="JS1AB12A3BC456789",
        )
    )
    from backend.db_models.models import AliadoFinanciero

    aliado = db.query(AliadoFinanciero).filter_by(es_propio=True).first()
    producto = AliadoProducto(
        id_aliado=aliado.id_aliado,
        nombre="CREDIMOTO PRUEBA",
        activo=True,
    )
    db.add(producto)
    db.flush()
    db.add(
        OfertaCredito(
            id_solicitud=solicitud.id_solicitud,
            id_aliado_producto=producto.id_aliado_producto,
            elegible=True,
            plazo_ofrecido=24,
            monto_aprobado=6_000_000,
            seleccionada=True,
        )
    )
    db.commit()
    return solicitud


def _filas(txt: str) -> list[str]:
    return [l for l in txt.split("\n") if l]


def test_descarga_archivo_plano(client):
    db = db_session.SessionLocal()
    _sembrar_facturada(db)
    db.close()

    r = client.get("/api/cargas/garantias-runtpro")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/plain")
    nombre = r.headers["content-disposition"]
    # El aliado propio del fixture: nit 999000999.
    assert "999000999RGM001" in nombre and nombre.endswith('.txt"')
    assert r.headers["X-Garantias-Exportadas"] == "1"
    assert r.headers["X-Registros"] == "4"

    filas = _filas(r.text)
    assert len(filas) == 5
    # Control: 4 registros | fecha de corte DDMMAAAA.
    assert filas[0].startswith("4|") and len(filas[0].split("|")[1]) == 8
    assert filas[1] == "PRN|R|N|999000999"
    grv = filas[2].split("|")
    assert grv[0] == "GRV" and grv[3] == "6000000" and grv[4] == "COP" and grv[5] == "1"
    deu = filas[3].split("|")
    assert deu[:3] == ["DEU", "C", "1032448999"]
    assert deu[3:7] == ["MARIA", "FERNANDA", "RUIZ", "PAEZ"]
    assert deu[8] == "CO" and deu[9] == "76" and deu[10] == "76520"
    assert deu[14] == "3205550011" and deu[15] == "NUEVO" and deu[16] == "Deudor"
    veh = filas[4].split("|")
    assert veh == ["VEH", "RNA", "JS1AB12A3BC456789", "JS1AB12A3BC456789"]


def test_segunda_generacion_no_repite(client):
    db = db_session.SessionLocal()
    _sembrar_facturada(db)
    db.close()

    r1 = client.get("/api/cargas/garantias-runtpro")
    assert r1.status_code == 200
    # Ya exportada: sin incluir_exportadas no hay pendientes.
    r2 = client.get("/api/cargas/garantias-runtpro")
    assert r2.status_code == 404
    # Regenerar incluye la misma prenda y consume el consecutivo 002.
    r3 = client.get("/api/cargas/garantias-runtpro?incluir_exportadas=true")
    assert r3.status_code == 200
    assert "RGM002" in r3.headers["content-disposition"]


def test_advertencias_preview_no_marca(client):
    db = db_session.SessionLocal()
    _sembrar_facturada(db, cedula="900111222")
    db.close()

    r = client.get("/api/cargas/garantias-runtpro/advertencias")
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["pendientes"] == 1
    # Sin buró en el fixture: el género falta y se reporta.
    assert any("género" in a["mensaje"] for a in cuerpo["advertencias"])
    # La prenda sigue pendiente (la vista previa no marca).
    r2 = client.get("/api/cargas/garantias-runtpro")
    assert r2.status_code == 200


def test_sin_pendientes_404(client):
    r = client.get("/api/cargas/garantias-runtpro")
    assert r.status_code == 404


def test_formato_excel_no_marca(client):
    db = db_session.SessionLocal()
    _sembrar_facturada(db)
    db.close()

    r = client.get("/api/cargas/garantias-runtpro?formato=excel")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    # El Excel es la hoja de revisión: la prenda sigue pendiente.
    r2 = client.get("/api/cargas/garantias-runtpro")
    assert r2.status_code == 200


def test_rol_sin_permiso(client_asesor):
    assert client_asesor.get("/api/cargas/garantias-runtpro").status_code == 403
