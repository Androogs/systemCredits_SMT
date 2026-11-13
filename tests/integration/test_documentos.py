"""Paquete de legalización: los documentos se generan con los datos de
la solicitud una vez el cliente firma (OTP verificado)."""

import hashlib
import re
import uuid
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

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
from backend.services.documento_service import DocumentoService, _fmt
from backend.services.letras import numero_a_letras


def _texto_docx(ruta: Path) -> str:
    """Texto plano del documento (sin tags XML) para aserciones."""
    with zipfile.ZipFile(ruta) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    xml = re.sub(r"<w:tab[^>]*/>", " ", xml)
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


def _crear_solicitud_firmada(db) -> uuid.UUID:
    ciudad = Ciudad(nombre="PALMIRA", departamento="Valle del Cauca")
    db.add(ciudad)
    db.flush()
    cliente = Cliente(
        tipo_documento="1",
        num_cedula="1015464714",
        nombre_completo="RUBIO URREGO EDDY SLEIDER",
        primer_apellido="RUBIO",
        fecha_nacimiento=date(1996, 11, 21),
        fecha_expedicion=date(2015, 2, 10),
        id_ciudad_expedicion=ciudad.id_ciudad,
        id_ciudad_nacimiento=ciudad.id_ciudad,
        ocupacion="empleado",
    )
    db.add(cliente)
    db.flush()
    solicitud = SolicitudCredito(
        id_cliente=cliente.id_cliente,
        estado="aprobada",
        num_solicitud=41,
        plazo_deseado_meses=48,
        fecha_hora_firma=datetime(2026, 3, 15, tzinfo=UTC),
        uuid_firma=uuid.uuid4(),
        autenticacion="otp_email",
    )
    db.add(solicitud)
    db.flush()
    db.add(
        SolicitudContactoVivienda(
            id_solicitud=solicitud.id_solicitud,
            correo="cliente@correo.com",
            telefono="3001234567",
            id_ciudad=ciudad.id_ciudad,
            direccion="BLV 52 # 52 - 52",
            barrio="Los Rosales",
            estrato=4,
            tipo_vivienda="Familiar",
            zona_rural=False,
            estado_civil="Divorciado",
            num_hijos=3,
            personas_a_cargo=3,
            es_cabeza_familia=True,
            cuenta_bienes_raices=True,
            cuenta_vehiculo=True,
            tiene_moto=False,
            primera_moto=True,
            tiene_carro=True,
            estoy_financiando=True,
        )
    )
    db.add(
        DatosLaborales(
            id_solicitud=solicitud.id_solicitud,
            tipo_contrato="indefinido",
            meses_continuidad=41,
            ingreso_mensual=10_060_000,
            otros_ingresos=0,
            nombre_empresa="shipt inc",
            fecha_ingreso=date(2022, 10, 4),
            nivel_educativo="Universitario",
            profesion="Salud",
            cargo="Medico",
            actividad_comercial="Servicios sociales",
            anios_camara_comercio=0,
        )
    )
    aliado = AliadoFinanciero(nit="890000", nombre="Inversiones Pacifico", tipo="propio", es_propio=True)
    db.add(aliado)
    db.flush()
    producto = AliadoProducto(
        id_aliado=aliado.id_aliado, nombre="Libranza moto",
        tasa_min=1.5, tasa_max=2.2, monto_min=1, monto_max=20_000_000,
    )
    db.add(producto)
    db.flush()
    db.add(
        OfertaCredito(
            id_solicitud=solicitud.id_solicitud,
            id_aliado_producto=producto.id_aliado_producto,
            elegible=True,
            seleccionada=True,
            # El saldo que el cliente decidió financiar; coincide con la
            # composición de la hoja de negocio del vehículo de abajo:
            # 12.349.050 neto + 1.339.000 adicionales + 864.434 aval.
            monto_aprobado=14_552_484,
            plazo_ofrecido=48,
            tasa_ofrecida=2.0,
            cuota_mensual=434_716,
        )
    )
    db.add(
        ProductoVehiculo(
            id_solicitud=solicitud.id_solicitud,
            producto_a_financiar="Motocicleta",
            marca="Fratelli", referencia="RFR", modelo="2026", color="Verde",
            valor_moto_iva=12_999_000,
            descuento_pct=5,
            accesorios=169_000,
            matricula=485_000,
            soat=685_000,
            aval_pct=7,
        )
    )
    db.commit()
    return solicitud.id_solicitud


def test_paquete_genera_los_trece_documentos(client, tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDENCIAS_DIR", str(tmp_path / "evid"))
    get_settings.cache_clear()
    db = db_session.SessionLocal()
    try:
        id_solicitud = _crear_solicitud_firmada(db)
        docs = DocumentoService(db).generar_paquete(id_solicitud)
        db.commit()

        assert len(docs) == 13
        tipos = {d.tipo for d in docs}
        assert tipos == {
            "doc_autorizacion", "doc_carta_aprobacion",
            "doc_autorizacion_datos", "doc_pagare",
            "doc_instrucciones", "doc_prenda", "doc_asegurabilidad",
            "doc_solicitud", "doc_compromiso", "doc_amortizacion",
            "doc_compra_venta", "doc_dacion", "doc_transferencia",
        }
        for doc in docs:
            ruta = tmp_path / "evid" / doc.ruta
            assert ruta.exists(), f"Falta el archivo de {doc.tipo}"
            assert doc.hash_sha256
    finally:
        db.close()


def test_todos_los_documentos_llevan_el_uuid_de_firma(
    client, tmp_path, monkeypatch
):
    """El uuid_firma (OTP) identifica el acto de firma: se estampa en
    cada pieza legal del paquete, no solo en la autorización."""
    monkeypatch.setenv("EVIDENCIAS_DIR", str(tmp_path / "evid"))
    get_settings.cache_clear()
    db = db_session.SessionLocal()
    try:
        id_solicitud = _crear_solicitud_firmada(db)
        firma_uuid = db.get(SolicitudCredito, id_solicitud).uuid_firma
        docs = DocumentoService(db).generar_paquete(id_solicitud)
        db.commit()

        for doc in docs:
            texto = _texto_docx(tmp_path / "evid" / doc.ruta)
            assert "Identificador único de firma electrónica" in texto, doc.tipo
            assert str(firma_uuid) in texto, doc.tipo
    finally:
        db.close()


# Huellas SHA-256 del QR y la rúbrica de la firma electrónica de la
# solicitud de muestra 735 (artefactos removidos de la plantilla; ver
# scripts/generar_plantilla_solicitud.py).
HUELLAS_FIRMA_MUESTRA = {
    "05fb103c9a6f76995cd41d4506e6a4ab28423f39caf9af3b0a336e7e7ee3760f",
    "ca61fbbb9807d07c6c81116f7d0cd0443b83e011b68e1bdf54b8cc94892b8eeb",
}


def _qrs_decodificados(ruta: Path) -> list[str]:
    """Decodifica los QR embebidos en las imágenes del DOCX."""
    import cv2
    import numpy as np

    detector = cv2.QRCodeDetector()
    decodificados = []
    with zipfile.ZipFile(ruta) as z:
        for nombre in z.namelist():
            if "media" not in nombre:
                continue
            img = cv2.imdecode(
                np.frombuffer(z.read(nombre), np.uint8),
                cv2.IMREAD_GRAYSCALE,
            )
            if img is None:
                continue
            # El detector varía por versión de OpenCV y por el patrón del
            # propio QR: upscale + binarización recuperan los que a
            # tamaño nativo no decodifica.
            _, binaria = cv2.threshold(
                img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
            variantes = [img, binaria] + [
                cv2.resize(v, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
                for v in (img, binaria)
                for f in (3, 4)
            ]
            for variante in variantes:
                texto, _, _ = detector.detectAndDecode(variante)
                if texto:
                    decodificados.append(texto)
                    break
    return decodificados


def _huellas_media(ruta: Path) -> set[str]:
    with zipfile.ZipFile(ruta) as z:
        return {
            hashlib.sha256(z.read(n)).hexdigest()
            for n in z.namelist()
            if "media" in n
        }


def test_cada_documento_lleva_qr_con_su_uuid_firma(
    client, tmp_path, monkeypatch
):
    """El QR estampado en cada pieza legal codifica el uuid_firma real
    de la solicitud — no el QR fijo de la muestra 735."""
    monkeypatch.setenv("EVIDENCIAS_DIR", str(tmp_path / "evid"))
    get_settings.cache_clear()
    db = db_session.SessionLocal()
    try:
        id_solicitud = _crear_solicitud_firmada(db)
        firma_uuid = str(db.get(SolicitudCredito, id_solicitud).uuid_firma)
        docs = DocumentoService(db).generar_paquete(id_solicitud)
        db.commit()

        url_esperada = f"/verificar-firma/{firma_uuid}"
        for doc in docs:
            ruta = tmp_path / "evid" / doc.ruta
            qrs = _qrs_decodificados(ruta)
            assert any(url_esperada in q for q in qrs), doc.tipo
            assert not (HUELLAS_FIRMA_MUESTRA & _huellas_media(ruta)), doc.tipo
    finally:
        db.close()


def test_plantilla_solicitud_sin_artefactos_de_muestra():
    """La plantilla del doc 7 no arrastra el QR ni la rúbrica de la
    solicitud 735 — solo logo y cláusula legal."""
    plantilla = (
        Path(__file__).resolve().parents[2]
        / "backend" / "documentos" / "plantillas" / "solicitud_credito.docx"
    )
    assert not (HUELLAS_FIRMA_MUESTRA & _huellas_media(plantilla))
    assert not _qrs_decodificados(plantilla)


def test_solicitud_credito_se_llena_con_los_datos(client, tmp_path, monkeypatch):
    """Documento 7: el formato 'Solicitud de crédito' queda diligenciado
    con los datos del último paso (vehículo + formalización)."""
    monkeypatch.setenv("EVIDENCIAS_DIR", str(tmp_path / "evid"))
    get_settings.cache_clear()
    db = db_session.SessionLocal()
    try:
        id_solicitud = _crear_solicitud_firmada(db)
        DocumentoService(db).generar_paquete(id_solicitud)
        db.commit()
        salida = (
            tmp_path / "evid" / "legalizacion" / str(id_solicitud)
            / "7. Solicitud de credito - 1015464714.docx"
        )
        texto = _texto_docx(salida)

        # Sin tokens ni datos de muestra.
        assert "{{" not in texto
        assert "jtobon" not in texto
        assert "12.999.000" in texto  # VALOR MOTO CON IVA
        # Encabezado: número y fecha de la solicitud.
        assert "No. SOLICITUD: 41" in texto
        assert "2026/03/15" in texto
        # Titular
        assert "RUBIO URREGO EDDY SLEIDER" in texto
        assert "CEDULA DE CIUDADANIA" in texto
        assert "1015464714" in texto
        assert "2015/02/10" in texto  # fecha de expedición
        assert "1996/11/21" in texto  # fecha de nacimiento
        assert "PALMIRA" in texto
        # Contacto y residencia
        assert "3001234567" in texto
        assert "cliente@correo.com" in texto
        assert "BLV 52 # 52 - 52" in texto
        assert "Los Rosales" in texto
        assert "Divorciado" in texto
        # Laboral
        assert "Empleado" in texto
        assert "Indefinido" in texto
        assert "shipt inc" in texto
        assert "10.060.000" in texto
        # Crédito y hoja de negocio
        assert "Fratelli" in texto
        assert "RFR" in texto
        assert "Verde" in texto
        assert "12.349.050" in texto   # TOTAL MOTO (valor - 5% desc.)
        assert "864.434" in texto      # FONDO DE GARANTÍA (7% del neto)
        assert "14.552.484" in texto   # SALDO A FINANCIAR
        assert "474.438" in texto      # CUOTA TOTAL = anualidad del saldo
    finally:
        db.close()


def test_pagare_lleva_los_datos_de_la_solicitud(client, tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDENCIAS_DIR", str(tmp_path / "evid"))
    get_settings.cache_clear()
    db = db_session.SessionLocal()
    try:
        id_solicitud = _crear_solicitud_firmada(db)
        DocumentoService(db).generar_paquete(id_solicitud)
        db.commit()

        salida = (
            tmp_path / "evid" / "legalizacion" / str(id_solicitud)
            / "12. Pagare - 1015464714.docx"
        )
        texto = _texto_docx(salida)
        assert "RUBIO URREGO EDDY SLEIDER" in texto
        assert "1015464714" in texto
        assert "14.552.484" in texto
        assert "CATORCE MILLONES" in texto
        assert "434.716" in texto
        assert "CUATROCIENTOS TREINTA Y CUATRO MIL" in texto
        # Primera cuota: día 20 del mes siguiente a la firma (15/03 → 20/04)
        assert "20/04/2026" in texto
        # La tasa del motor llena el blanco (____%) del pagaré real.
        assert "(2%)" in texto
        # El consecutivo (num_solicitud) reemplaza “Consecutivo”.
        assert "“Consecutivo”" not in texto
        assert re.search(r"No\.\s*41", texto)
        # La identificación usa TIPO_ID + CÉDULA, no el nombre repetido.
        assert "RUBIO URREGO EDDY SLEIDER RUBIO URREGO" not in texto
        assert "CC 1015464714" in texto
        assert "MERGEFIELD" not in texto
    finally:
        db.close()


def test_literales_de_las_otras_plantillas(client, tmp_path, monkeypatch):
    """Los textos fijos de muestra se reemplazan con los de la solicitud."""
    monkeypatch.setenv("EVIDENCIAS_DIR", str(tmp_path / "evid"))
    get_settings.cache_clear()
    db = db_session.SessionLocal()
    try:
        id_solicitud = _crear_solicitud_firmada(db)
        DocumentoService(db).generar_paquete(id_solicitud)
        db.commit()
        base = tmp_path / "evid" / "legalizacion" / str(id_solicitud)

        carta = _texto_docx(base / "2. Carta de aprobacion - 1015464714.docx")
        assert "XXXX" not in carta
        assert "No. 41" in carta
        assert "NOMBRE ASESOR" not in carta
        assert "NÚMERO CELULAR" not in carta

        instrucciones = _texto_docx(
            base / "4. Carta de instrucciones - 1015464714.docx"
        )
        assert "No 001" not in instrucciones
        assert "No. 41" in instrucciones

        compromiso = _texto_docx(base / "9. Politicas de cartera - 1015464714.docx")
        assert "DIANA" not in compromiso
        assert "28549365" not in compromiso
        assert "RUBIO URREGO EDDY SLEIDER" in compromiso
        assert "1015464714" in compromiso

        asegurabilidad = _texto_docx(
            base / "14. Declaracion asegurabilidad - 1015464714.docx"
        )
        assert "DEUDORFirma" not in asegurabilidad
        assert "CC 1015464714" in asegurabilidad

        # Autorización: canales de contacto capturados + id de firma OTP.
        autorizacion = _texto_docx(
            base / "1. Autorizacion consulta centrales - 1015464714.docx"
        )
        assert "cliente@correo.com" in autorizacion
        assert "3001234567" in autorizacion
        assert "Identificador único de firma electrónica" in autorizacion

        # Prenda: los datos de la moto capturados en la formalización.
        prenda = _texto_docx(base / "13. Prenda sin tenencia - 1015464714.docx")
        assert "Fratelli" in prenda
        assert "RFR" in prenda
        assert "2026" in prenda
        assert "Verde" in prenda
    finally:
        db.close()


def test_sin_firma_no_hay_paquete(client, tmp_path, monkeypatch):
    """Sin OTP verificado (fecha_hora_firma None) no se genera nada."""
    monkeypatch.setenv("EVIDENCIAS_DIR", str(tmp_path / "evid"))
    get_settings.cache_clear()
    db = db_session.SessionLocal()
    try:
        cliente = Cliente(
            tipo_documento="1", num_cedula="999",
            nombre_completo="SIN FIRMA", fecha_nacimiento=date(1990, 1, 1),
        )
        db.add(cliente)
        db.flush()
        solicitud = SolicitudCredito(id_cliente=cliente.id_cliente, estado="aprobada")
        db.add(solicitud)
        db.commit()

        assert DocumentoService(db).generar_paquete(solicitud.id_solicitud) == []
    finally:
        db.close()


def test_numero_a_letras_formato_legal():
    assert numero_a_letras(12_781_665) == (
        "DOCE MILLONES SETECIENTOS OCHENTA Y UNO MIL "
        "SEISCIENTOS SESENTA Y CINCO PESOS M/CTE"
    )
    assert numero_a_letras(434_716) == (
        "CUATROCIENTOS TREINTA Y CUATRO MIL "
        "SETECIENTOS DIECISÉIS PESOS M/CTE"
    )


def test_tabla_amortizacion_lleva_datos_y_cuadra(
    client, tmp_path, monkeypatch
):
    """La tabla de amortización trae los datos del cliente y el plan de
    pagos cuadra: 48 filas, saldo inicial = monto aprobado y saldo final 0."""
    from decimal import Decimal

    from docx import Document

    from backend.services.finanzas import cuota_anualidad

    monkeypatch.setenv("EVIDENCIAS_DIR", str(tmp_path / "evid"))
    get_settings.cache_clear()
    db = db_session.SessionLocal()
    try:
        id_solicitud = _crear_solicitud_firmada(db)
        docs = DocumentoService(db).generar_paquete(id_solicitud)
        db.commit()
        amort = next(d for d in docs if d.tipo == "doc_amortizacion")
        ruta = tmp_path / "evid" / amort.ruta
        assert ruta.name == "15. Tabla de amortizacion - 1015464714.docx"

        texto = _texto_docx(ruta)
        assert "RUBIO URREGO EDDY SLEIDER" in texto
        assert "1015464714" in texto
        assert "14.552.484" in texto
        assert "2% mensual" in texto
        assert "48 meses" in texto

        doc = Document(str(ruta))
        tabla = doc.tables[-1]  # la primera es la tarjeta-resumen
        # 1 encabezado + 48 cuotas + 1 fila de totales
        assert len(tabla.rows) == 50
        celdas = [[c.text for c in f.cells] for f in tabla.rows]
        assert celdas[1][0] == "1"
        assert celdas[1][2] == "14.552.484"  # saldo inicial primera cuota
        cuota = cuota_anualidad(Decimal("14552484"), Decimal("2"), 48)
        assert celdas[1][3] == _fmt(cuota)
        assert celdas[48][0] == "48"
        assert celdas[48][8] == "0"  # saldo final en cero
        assert celdas[49][1] == "TOTALES"
    finally:
        db.close()


def test_endpoint_verificacion_firma(client, tmp_path, monkeypatch):
    """GET /api/firmas/{uuid}: el destino del QR devuelve solo lo impreso
    en el documento (firmante, cédula, solicitud, fecha) + 404 ajeno."""
    monkeypatch.setenv("EVIDENCIAS_DIR", str(tmp_path / "evid"))
    get_settings.cache_clear()
    db = db_session.SessionLocal()
    try:
        id_solicitud = _crear_solicitud_firmada(db)
        uuid_firma = str(db.get(SolicitudCredito, id_solicitud).uuid_firma)
        DocumentoService(db).generar_paquete(id_solicitud)
        db.commit()
    finally:
        db.close()

    r = client.get(f"/api/firmas/{uuid_firma}")
    assert r.status_code == 200
    datos = r.json()
    assert datos["uuid_firma"] == uuid_firma
    assert datos["firmante"] == "RUBIO URREGO EDDY SLEIDER"
    assert datos["documento_identidad"] == "CC 1015464714"
    assert datos["num_solicitud"] == 41
    assert datos["documentos"] == 13
    assert datos["fecha_hora_firma"].startswith("2026-03-15")

    assert client.get(f"/api/firmas/{uuid.uuid4()}").status_code == 404
