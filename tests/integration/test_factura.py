"""Factura del vehículo: carga multipart, verificación contra la
solicitud (documento del comprador), pre-llenado de la prenda y ciclo
comercial aprobada → facturada."""

import io
import uuid
import zipfile
import re
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from backend.config import get_settings
from backend.db_models import session as db_session
from backend.db_models.models import (
    AliadoFinanciero,
    AliadoProducto,
    Ciudad,
    Cliente,
    DatosLaborales,
    OfertaCredito,
    ProductoVehiculo,
    SolicitudContactoVivienda,
    SolicitudCredito,
)


# Texto extraído de una factura electrónica SUMOTO real (formato
# 'sumoto' del parser): comprador + cédula, número MTEC, VIN+marca+
# color, motor partido en dos líneas y totales en formato en-US.
LINEAS_FACTURA = [
    "PALACIOS ORBES MILTON ALBERTO",
    "Cédula de ciudadanía  14704104",
    "CL 40 9 15",
    "Palmira",
    "MTEC 2434",
    "2027 124",
    "9F2C91252V5009278 AKT GRIS MATE",
    "ZS154FMI-",
    "38V102908",
    "5,453,781.51 AK125FLEX-2027 5,117,647.06",
    "RESOLUCION DIAN No. 18764099982895 DEL 10 DE 10 DE 2025 AUTORIZA "
    "DEL MTEC 1663 AL MTEC 10000",
    "5,453,781.51",
    "972,352.94",
    "6,090,000.00",
]


def _pdf_con_texto(lineas: list[str]) -> bytes:
    """PDF mínimo de una página con texto extraíble (sin reportlab)."""
    ops = ["BT /F1 10 Tf"]
    for i, linea in enumerate(lineas):
        esc = (
            linea.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        ops.append(f"1 0 0 1 40 {760 - i * 14} Tm ({esc}) Tj")
    ops.append("ET")
    writer = PdfWriter()
    pagina = writer.add_blank_page(width=612, height=792)
    contenido = DecodedStreamObject()
    contenido.set_data("\n".join(ops).encode("latin-1"))
    pagina[NameObject("/Contents")] = contenido
    pagina[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): DictionaryObject(
                        {
                            NameObject("/Type"): NameObject("/Font"),
                            NameObject("/Subtype"): NameObject("/Type1"),
                            NameObject("/BaseFont"): NameObject("/Helvetica"),
                        }
                    )
                }
            )
        }
    )
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _factura_pdf(cedula: str = "14704104") -> bytes:
    lineas = [
        ("Cédula de ciudadanía  " + cedula)
        if "Cédula de ciudadanía" in l
        else l
        for l in LINEAS_FACTURA
    ]
    return _pdf_con_texto(lineas)


# PNG mínimo válido (1x1 transparente): MIME permitido pero sin texto
# legible → la factura se acepta con parseada=false.
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000d49444154789c626001000000ffff030000060005"
    "57bfabd40000000049454e44ae426082"
)


@pytest.fixture
def evid_dir(client, tmp_path, monkeypatch):
    """evidencias_dir aislado por test; se fija después del client (que
    ya hizo cache_clear con el entorno base)."""
    monkeypatch.setenv("EVIDENCIAS_DIR", str(tmp_path / "evid"))
    get_settings.cache_clear()
    return tmp_path / "evid"


def _solicitud_firmada(
    db,
    *,
    estado: str = "aprobada",
    decision: str = "aprobado",
    firmada: bool = True,
    cedula: str = "14704104",
) -> uuid.UUID:
    """Cadena completa para que el paquete legal también pueda
    regenerarse: cliente + contacto + laboral + aliado/oferta + moto."""
    ciudad = Ciudad(nombre="PALMIRA", departamento="Valle del Cauca")
    db.add(ciudad)
    db.flush()
    cliente = Cliente(
        tipo_documento="1",
        num_cedula=cedula,
        nombre_completo="PALACIOS ORBES MILTON ALBERTO",
        primer_apellido="PALACIOS",
        fecha_nacimiento=date(1990, 5, 15),
        fecha_expedicion=date(2010, 2, 10),
        id_ciudad_expedicion=ciudad.id_ciudad,
        id_ciudad_nacimiento=ciudad.id_ciudad,
        ocupacion="empleado",
    )
    db.add(cliente)
    db.flush()
    solicitud = SolicitudCredito(
        id_cliente=cliente.id_cliente,
        estado=estado,
        decision=decision,
        num_solicitud=42,
        plazo_deseado_meses=24,
        fecha_hora_firma=(
            datetime(2026, 7, 30, tzinfo=UTC) if firmada else None
        ),
        uuid_firma=uuid.uuid4() if firmada else None,
        autenticacion="otp_email" if firmada else None,
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
            barrio="Centro",
            estrato=3,
            tipo_vivienda="Familiar",
            zona_rural=False,
            estado_civil="Soltero",
            num_hijos=0,
            personas_a_cargo=0,
            es_cabeza_familia=False,
            cuenta_bienes_raices=False,
            cuenta_vehiculo=True,
            tiene_moto=False,
            primera_moto=True,
            tiene_carro=False,
            estoy_financiando=False,
        )
    )
    db.add(
        DatosLaborales(
            id_solicitud=solicitud.id_solicitud,
            tipo_contrato="indefinido",
            meses_continuidad=30,
            ingreso_mensual=3_000_000,
            otros_ingresos=0,
        )
    )
    aliado = AliadoFinanciero(
        nit="890001", nombre="Inversiones Pacifico", tipo="propio", es_propio=True
    )
    db.add(aliado)
    db.flush()
    producto = AliadoProducto(
        id_aliado=aliado.id_aliado,
        nombre="Libranza moto",
        tasa_min=1.5,
        tasa_max=2.2,
        monto_min=1,
        monto_max=20_000_000,
    )
    db.add(producto)
    db.flush()
    db.add(
        OfertaCredito(
            id_solicitud=solicitud.id_solicitud,
            id_aliado_producto=producto.id_aliado_producto,
            elegible=True,
            seleccionada=True,
            monto_aprobado=5_000_000,
            plazo_ofrecido=24,
            tasa_ofrecida=2.0,
            cuota_mensual=260_000,
        )
    )
    db.add(
        ProductoVehiculo(
            id_solicitud=solicitud.id_solicitud,
            producto_a_financiar="Motocicleta",
            marca="AKT",
            referencia="AK125FLEX",
            modelo="2027",
            color="NEGRO",
            valor_moto_iva=6_090_000,
        )
    )
    db.commit()
    return solicitud.id_solicitud


def _subir(client, id_solicitud, contenido, nombre="factura.pdf",
           mime="application/pdf"):
    return client.post(
        f"/api/solicitudes/{id_solicitud}/factura",
        files={"archivo": (nombre, contenido, mime)},
    )


def test_201_mueve_aprobada_a_facturada(client, evid_dir):
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_firmada(db)
    finally:
        db.close()

    r = _subir(client, id_solicitud, _factura_pdf())
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["nombre"] == "factura.pdf"
    assert cuerpo["hash_sha256"]
    assert cuerpo["cargada_por"]

    detalle = client.get(f"/api/solicitudes/{id_solicitud}").json()
    assert detalle["estado"] == "facturada"
    assert detalle["factura"]["nombre"] == "factura.pdf"
    assert (evid_dir / detalle["factura"]["nombre"]).exists() or list(
        evid_dir.rglob("factura.pdf")
    )


def test_get_factura_sirve_el_archivo(client, evid_dir):
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_firmada(db)
    finally:
        db.close()
    pdf = _factura_pdf()
    assert _subir(client, id_solicitud, pdf).status_code == 201

    r = client.get(f"/api/solicitudes/{id_solicitud}/factura")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content == pdf


def test_409_aprobada_sin_firma_otp(client, evid_dir):
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_firmada(db, firmada=False)
    finally:
        db.close()
    assert _subir(client, id_solicitud, _factura_pdf()).status_code == 409


@pytest.mark.parametrize("estado", ["rechazada", "desembolsada"])
def test_409_estado_no_admite_factura(client, evid_dir, estado):
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_firmada(db, estado=estado)
    finally:
        db.close()
    assert _subir(client, id_solicitud, _factura_pdf()).status_code == 409


def test_422_mime_no_permitido(client, evid_dir):
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_firmada(db)
    finally:
        db.close()
    r = _subir(client, id_solicitud, b"hola", "factura.txt", "text/plain")
    assert r.status_code == 422


def test_resubir_reemplaza_el_archivo(client, evid_dir):
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_firmada(db)
    finally:
        db.close()
    assert _subir(client, id_solicitud, _factura_pdf()).status_code == 201
    # Re-subir como imagen: cambia la extensión → el .pdf viejo se borra.
    r = _subir(client, id_solicitud, _PNG, "factura.png", "image/png")
    assert r.status_code == 201

    detalle = client.get(f"/api/solicitudes/{id_solicitud}").json()
    assert detalle["estado"] == "facturada"
    archivos = list(evid_dir.rglob("factura.*"))
    assert [p.suffix for p in archivos] == [".png"]


def test_parseada_pre_llena_la_prenda(client, evid_dir):
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_firmada(db)
    finally:
        db.close()
    r = _subir(client, id_solicitud, _factura_pdf())
    assert r.status_code == 201, r.text

    verif = r.json()["verificacion"]
    assert verif["parseada"] is True
    assert verif["nit_coincide"] is True
    assert verif["datos"]["numero_factura"] == "MTEC-2434"
    assert verif["datos"]["numero_motor"] == "ZS154FMI-38V102908"

    detalle = client.get(f"/api/solicitudes/{id_solicitud}").json()
    vehiculo = detalle["vehiculo"]
    assert vehiculo["numero_motor"] == "ZS154FMI-38V102908"
    assert vehiculo["vin"] == "9F2C91252V5009278"
    assert vehiculo["numero_chasis"] == "9F2C91252V5009278"
    # El color de la factura manda sobre el de la oferta.
    assert vehiculo["color"] == "GRIS MATE"
    # La diferencia de color quedó como advertencia de auditoría.
    assert any("GRIS MATE" in a for a in verif["advertencias"])


def test_nit_de_otro_comprador_422_sin_guardar(client, evid_dir):
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_firmada(db, cedula="999888777")
    finally:
        db.close()
    r = _subir(client, id_solicitud, _factura_pdf())
    assert r.status_code == 422
    assert "otro comprador" in r.json()["detail"]

    detalle = client.get(f"/api/solicitudes/{id_solicitud}").json()
    assert detalle["estado"] == "aprobada"
    assert detalle["factura"] is None
    assert not list(evid_dir.rglob("factura.*"))


def test_factura_ilegible_201_parseada_false(client, evid_dir):
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_firmada(db)
    finally:
        db.close()
    r = _subir(client, id_solicitud, _PNG, "factura.png", "image/png")
    assert r.status_code == 201, r.text
    verif = r.json()["verificacion"]
    assert verif["parseada"] is False
    assert verif["advertencias"]
    assert client.get(f"/api/solicitudes/{id_solicitud}").json()[
        "estado"
    ] == "facturada"


def test_patch_vehiculo_confirma_la_prenda(client, evid_dir):
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_firmada(db)
    finally:
        db.close()
    assert _subir(client, id_solicitud, _factura_pdf()).status_code == 201

    r = client.patch(
        f"/api/solicitudes/{id_solicitud}/vehiculo",
        json={
            "numero_motor": "MOTOR-CORREGIDO-1",
            "vin": "VIN-CORREGIDO-17CH",
            "color": "ROJO",
        },
    )
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["numero_motor"] == "MOTOR-CORREGIDO-1"
    assert cuerpo["vin"] == "VIN-CORREGIDO-17CH"
    assert cuerpo["color"] == "ROJO"


def test_patch_vehiculo_409_fuera_de_facturada(client, evid_dir):
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_firmada(db)
    finally:
        db.close()
    r = client.patch(
        f"/api/solicitudes/{id_solicitud}/vehiculo",
        json={"numero_motor": "X"},
    )
    assert r.status_code == 409


def _solicitud_contado(db, cedula: str = "14704104") -> uuid.UUID:
    """Venta de contado recién radicada: sin decisión del motor ni
    firma OTP — la factura se carga de inmediato."""
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
        estado="creada",
        decision=None,
        num_solicitud=77,
        linea_credito="Contado",
        destino_credito="Motocicleta",
    )
    db.add(solicitud)
    db.commit()
    return solicitud.id_solicitud


def test_contado_201_sin_decision_ni_firma(client, evid_dir):
    """La venta de contado no evalúa ni firma pagaré: la factura cierra
    la venta directo desde 'creada'."""
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_contado(db)
    finally:
        db.close()

    r = _subir(client, id_solicitud, _factura_pdf())
    assert r.status_code == 201, r.text
    assert r.json()["verificacion"]["nit_coincide"] is True

    detalle = client.get(f"/api/solicitudes/{id_solicitud}").json()
    assert detalle["estado"] == "facturada"


def test_contado_409_fuera_de_creada_o_facturada(client, evid_dir):
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_contado(db)
        solicitud = db.get(SolicitudCredito, id_solicitud)
        solicitud.estado = "cancelada"
        db.commit()
    finally:
        db.close()
    assert _subir(client, id_solicitud, _factura_pdf()).status_code == 409


def test_prenda_regenerada_contiene_motor_chasis(client, evid_dir):
    """La prenda firmada quedó sin motor/chasis: tras la factura el
    documento regenerado ya los trae (y el color definitivo)."""
    db = db_session.SessionLocal()
    try:
        id_solicitud = _solicitud_firmada(db)
    finally:
        db.close()
    assert _subir(client, id_solicitud, _factura_pdf()).status_code == 201

    from backend.db_models.evidencia_models import DocumentoEvidencia

    db = db_session.SessionLocal()
    try:
        prenda = (
            db.query(DocumentoEvidencia)
            .filter(
                DocumentoEvidencia.id_solicitud == id_solicitud,
                DocumentoEvidencia.tipo == "doc_prenda",
            )
            .first()
        )
        assert prenda is not None
        ruta = Path(get_settings().evidencias_dir) / prenda.ruta
        assert ruta.exists()
        with zipfile.ZipFile(ruta) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        xml = re.sub(r"<w:tab[^>]*/>", " ", xml)
        texto = re.sub(r"<[^>]+>", "", re.sub(r"</w:p>", "\n", xml))
        assert "ZS154FMI-38V102908" in texto
        assert "9F2C91252V5009278" in texto
        assert "GRIS MATE" in texto
    finally:
        db.close()
