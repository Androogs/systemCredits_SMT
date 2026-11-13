"""Cierre de la venta de contado: hoja de negocio (vehículo +
liquidación + 'facturar a'), paquete físico de documentos de la
entrega y verificación de la factura contra el facturado."""

import uuid
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path

import pytest

from backend.config import get_settings
from backend.db_models import session as db_session
from backend.db_models.models import (
    Ciudad,
    Cliente,
    ProductoVehiculo,
    SolicitudContactoVivienda,
    SolicitudCredito,
)

from .test_factura import _factura_pdf


@pytest.fixture
def evid_dir(client, tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDENCIAS_DIR", str(tmp_path / "evid"))
    get_settings.cache_clear()
    return tmp_path / "evid"


def _solicitud_contado(db, cedula: str = "14704104",
                       estado: str = "creada",
                       linea: str = "Contado") -> uuid.UUID:
    """Contado recién radicada con el contacto mínimo que necesita el
    paquete de documentos (correo/teléfono/ciudad del acta)."""
    ciudad = Ciudad(nombre="PALMIRA", departamento="Valle del Cauca")
    db.add(ciudad)
    db.flush()
    cliente = Cliente(
        tipo_documento="1",
        num_cedula=cedula,
        nombre_completo="PALACIOS ORBES MILTON ALBERTO",
        primer_apellido="PALACIOS",
        fecha_nacimiento=date(1990, 5, 15),
        ocupacion="empleado",
    )
    db.add(cliente)
    db.flush()
    solicitud = SolicitudCredito(
        id_cliente=cliente.id_cliente,
        estado=estado,
        decision=None,
        num_solicitud=88,
        linea_credito=linea,
        destino_credito="Motocicleta",
    )
    db.add(solicitud)
    db.flush()
    db.add(
        SolicitudContactoVivienda(
            id_solicitud=solicitud.id_solicitud,
            correo="cliente@correo.com",
            telefono="3001234567",
            id_ciudad=ciudad.id_ciudad,
            direccion="CL 40 9 15",
            estrato=3,
        )
    )
    db.commit()
    return solicitud.id_solicitud


_PAYLOAD = {
    "asesor_externo": "RONALDO AYALA",
    "facturar_a_documento": "900123456",
    "facturar_a_nombre": "INVERSIONES LOPEZ SAS",
    "facturar_a2_documento": "1111",
    "facturar_a2_nombre": "SEGUNDO FACTURADO",
    "observaciones": "INCLUYE SOAT Y MATRICULA",
    "vehiculo": {
        "producto_a_financiar": "Motocicleta",
        "marca": "SUZUKI",
        "referencia": "DR-160X",
        "modelo": "2026",
        "color": "NEGRO",
        "valor_moto_iva": 14350000,
        "descuento": 0,
        "matricula": 660000,
        "soat": 1050000,
        "impuestos": 430000,
        "accesorios": 0,
    },
    "numero_motor": "EG3R01*AKX001028",
    "numero_chasis": "LC6PCKG39R0011420",
    "vin": "LC6PCKG39R0011420",
    "ciudad_matricula": "PALMIRA",
    "anticipo": 11000000,
    "retoma": 0,
    "otros_gastos": 0,
}


def _put(client, id_solicitud, payload=_PAYLOAD):
    return client.put(
        f"/api/solicitudes/{id_solicitud}/venta-contado", json=payload
    )


def test_204_persiste_hoja_de_negocio(client, evid_dir):
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_contado(db)
    finally:
        db.close()

    r = _put(client, id_solicitud)
    assert r.status_code == 204, r.text

    detalle = client.get(f"/api/solicitudes/{id_solicitud}").json()
    assert detalle["facturar_a_documento"] == "900123456"
    assert detalle["facturar_a_nombre"] == "INVERSIONES LOPEZ SAS"
    assert detalle["facturar_a2_nombre"] == "SEGUNDO FACTURADO"
    assert detalle["asesor_externo"] == "RONALDO AYALA"
    assert detalle["observaciones_venta"] == "INCLUYE SOAT Y MATRICULA"
    v = detalle["vehiculo"]
    assert v["marca"] == "SUZUKI"
    assert v["numero_motor"] == "EG3R01*AKX001028"
    assert v["numero_chasis"] == "LC6PCKG39R0011420"
    assert float(v["anticipo"]) == 11000000
    assert v["ciudad_matricula"] == "PALMIRA"


def test_422_solicitud_de_credito(client, evid_dir):
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_contado(db, linea="Credito")
    finally:
        db.close()
    assert _put(client, id_solicitud).status_code == 422


def test_409_estado_no_admite(client, evid_dir):
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_contado(db, estado="cancelada")
    finally:
        db.close()
    assert _put(client, id_solicitud).status_code == 409


def test_paquete_cuatro_documentos_con_acta(client, evid_dir):
    """Guardar la venta genera el paquete físico de la entrega:
    autorizaciones + transferencia + acta (sin sello OTP)."""
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_contado(db)
    finally:
        db.close()

    assert _put(client, id_solicitud).status_code == 204

    destino = Path(evid_dir) / "legalizacion" / str(id_solicitud)
    nombres = sorted(p.name for p in destino.glob("*.docx"))
    assert len(nombres) == 4
    assert any("Acta de entrega" in n for n in nombres)

    # El acta trae motor/chasis de la hoja de negocio.
    import docx

    acta = docx.Document(str(destino / nombres[-1]))
    texto = "\n".join(
        c.text
        for t in acta.tables
        for row in t.rows
        for c in row.cells
    )
    assert "EG3R01*AKX001028" in texto
    assert "LC6PCKG39R0011420" in texto
    assert "SUZUKI" in texto

    # Registradas como evidencias del proceso.
    r = client.get(f"/api/solicitudes/{id_solicitud}/legalizacion.zip")
    assert r.status_code == 200
    with zipfile.ZipFile(BytesIO(r.content)) as z:
        assert len([n for n in z.namelist() if n.endswith(".docx")]) == 4


def test_factura_verifica_contra_facturar_a(client, evid_dir):
    """Con 'facturar a' diligenciado la factura se compara contra ese
    documento (el comprador puede ser un tercero), no la cédula del
    cliente."""
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_contado(db)
    finally:
        db.close()

    assert _put(
        client, id_solicitud,
        {**_PAYLOAD, "facturar_a_documento": "14704104"},
    ).status_code == 204

    r = client.post(
        f"/api/solicitudes/{id_solicitud}/factura",
        files={
            "archivo": (
                "factura.pdf", _factura_pdf("14704104"), "application/pdf"
            )
        },
    )
    assert r.status_code == 201, r.text
    assert client.get(
        f"/api/solicitudes/{id_solicitud}"
    ).json()["estado"] == "facturada"
